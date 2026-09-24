"""
AI Assistant service: per-user chat with Mistral and native tool calling.

Implements an agentic loop:
1. Persist the user message.
2. Build the conversation (system prompt + history + user message).
3. Call Mistral chat completions with tool definitions.
4. While the model requests tools, execute them (semantic comment search,
   classification, dashboard statistics) and feed results back.
5. Persist the final assistant message together with a tool call trace.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import AIConversation
from ..db.models.ai_conversation import MessageRoleEnum, ToolTypeEnum
from .classification import ClassificationService
from .dashboard import get_dashboard_stats
from .embedding import EmbeddingService

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

# Map tool names onto the persisted ToolTypeEnum values.
TOOL_TO_ENUM = {
    "semantic_search_comments": ToolTypeEnum.SEARCH,
    "classify_text": ToolTypeEnum.CLASSIFY,
    "get_dashboard_stats": ToolTypeEnum.SUMMARIZE,
}

SYSTEM_PROMPT = """You are the AI assistant of Comment Checker, a system that collects \
comments from social media, classifies them for harmful content (hate speech, threats, \
insults, ...) and clusters the accounts behind them.

You answer questions about the user's data. You have tools:
- semantic_search_comments: finds comments by MEANING (embeddings), even when no \
keyword matches. Use it whenever the user asks to find, show or look for comments.
- classify_text: classifies a given text through the moderation pipeline \
(category, severity, harmful score, confidence).
- get_dashboard_stats: returns aggregate statistics (totals, flag rate, \
category and status distributions).

Guidelines:
- Prefer tools over guessing; never invent data.
- After a tool call, summarize the result in natural language (short sentences, \
lists where helpful). Do not dump raw JSON.
- If a tool returns an error, say so plainly.
- If the answer does not need data (small talk, general questions), just answer.
- Format your replies using Markdown (headings, bullet lists, **bold**, \
inline `code`, tables) when it improves readability; keep prose answers \
plain. Never use raw HTML.
- The current date is {date}."""


class AIAssistantService:
    """Per-user chat service backed by the Mistral chat completions API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.model = "mistral-medium-3.5"
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

        self._embedding_service: EmbeddingService | None = None
        self._classification_service: ClassificationService | None = None

        # Mistral function-calling tool definitions
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "semantic_search_comments",
                    "description": (
                        "Semantic search over comments by meaning using "
                        "embeddings. Finds comments about a topic even when no "
                        "keyword matches."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to look for, e.g. 'people insulting the shop owner'",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default 10, max 50)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "classify_text",
                    "description": (
                        "Classify a text through the moderation pipeline: "
                        "returns category, severity, harmful score and confidence."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The text to classify",
                            }
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_dashboard_stats",
                    "description": (
                        "Get aggregate statistics for the comment dataset: "
                        "totals, flag rate, category and status distributions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date_range": {
                                "type": "string",
                                "enum": ["1m", "6m", "1y", "all"],
                                "description": "Time window (default 'all')",
                            }
                        },
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Lazy services
    # ------------------------------------------------------------------

    @property
    def embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(self.db)
        return self._embedding_service

    @property
    def classification_service(self) -> ClassificationService:
        if self._classification_service is None:
            self._classification_service = ClassificationService(self.db)
        return self._classification_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        user_id: str,
        message: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Handle one user turn of the conversation, running tools as needed."""
        if not session_id:
            session_id = str(uuid.uuid4())

        start_time = time.time()

        self.db.add(
            AIConversation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role=MessageRoleEnum.USER,
                content=message,
            )
        )
        await self.db.commit()

        history = await self._get_conversation_history(user_id, session_id)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    date=datetime.now().strftime("%Y-%m-%d")
                ),
            }
        ]
        for conv in history:
            role = getattr(conv.role, "value", conv.role)
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": conv.content})

        tool_trace: list[dict[str, Any]] = []
        response_text = "I'm sorry, I couldn't generate a response."

        async with httpx.AsyncClient(timeout=90.0) as client:
            for _ in range(MAX_TOOL_ROUNDS):
                data = await self._call_mistral(client, messages)
                if data is None:
                    break

                choice = data["choices"][0]["message"]
                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if choice.get("content"):
                    assistant_msg["content"] = choice["content"]

                tool_calls = choice.get("tool_calls")
                if not tool_calls:
                    response_text = choice.get("content") or response_text
                    break

                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                for call in tool_calls:
                    function = call.get("function", {})
                    name = function.get("name", "")
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {"error": "invalid tool arguments JSON"}

                    logger.info("AI tool call %s: %s", name, arguments)
                    try:
                        output = await self._execute_tool(name, arguments)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("AI tool %s failed: %s", name, exc)
                        output = {"error": str(exc)}

                    tool_trace.append(
                        {"tool": name, "input": arguments, "output": output}
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": json.dumps(output, default=str),
                        }
                    )
            else:
                # Tool loop exhausted: force a final answer without tools
                data = await self._call_mistral(client, messages, with_tools=False)
                if data:
                    response_text = (
                        data["choices"][0]["message"].get("content")
                        or response_text
                    )

        latency_ms = int((time.time() - start_time) * 1000)
        primary_tool = tool_trace[0]["tool"] if tool_trace else None

        assistant_conversation = AIConversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=MessageRoleEnum.ASSISTANT,
            content=response_text,
            tool_used=(
                TOOL_TO_ENUM.get(primary_tool, ToolTypeEnum.NONE)
                if primary_tool
                else ToolTypeEnum.NONE
            ),
            tool_input=tool_trace[0]["input"] if tool_trace else None,
            tool_output={"tool_calls": tool_trace} if tool_trace else None,
            response_model=self.model,
            response_tokens=len(response_text.split()),
            latency_ms=latency_ms,
        )
        self.db.add(assistant_conversation)
        await self.db.commit()
        await self.db.refresh(assistant_conversation)

        return {
            "response": response_text,
            "tool_used": primary_tool,
            "tool_input": tool_trace[0]["input"] if tool_trace else None,
            "tool_output": {"tool_calls": tool_trace} if tool_trace else None,
            "tool_calls": tool_trace,
            "conversation_id": assistant_conversation.id,
            "session_id": session_id,
            "model": self.model,
            "tokens": assistant_conversation.response_tokens,
            "latency_ms": latency_ms,
        }

    # ------------------------------------------------------------------
    # Mistral API
    # ------------------------------------------------------------------

    async def _call_mistral(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, Any]],
        with_tools: bool = True,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False,
        }
        if with_tools:
            payload["tools"] = self.tool_definitions
            payload["tool_choice"] = "auto"

        try:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Mistral API error: %s %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Mistral API call failed: %s", exc)
            return None

        data = response.json()
        if data.get("choices"):
            return data
        return None

    async def _get_conversation_history(
        self, user_id: str, session_id: str, limit: int = HISTORY_LIMIT
    ) -> list[AIConversation]:
        result = await self.db.execute(
            select(AIConversation)
            .where(
                AIConversation.user_id == user_id,
                AIConversation.session_id == session_id,
            )
            .order_by(asc(AIConversation.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "semantic_search_comments":
            return await self._tool_semantic_search_comments(arguments)
        if name == "classify_text":
            return await self._tool_classify_text(arguments)
        if name == "get_dashboard_stats":
            return await self._tool_dashboard_stats(arguments)
        return {"error": f"Unknown tool: {name}"}

    async def _tool_semantic_search_comments(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"error": "No search query provided"}

        limit = min(int(arguments.get("limit") or 10), 50)
        results = await self.embedding_service.semantic_search(query, limit=limit)
        return {
            "query": query,
            "total": len(results),
            "results": [
                {
                    "id": comment.id,
                    "text": comment.text,
                    "author": comment.original_author,
                    "platform": comment.source_platform,
                    "status": getattr(comment.status, "value", comment.status),
                    "similarity": round(score, 4),
                }
                for comment, score in results
            ],
        }

    async def _tool_classify_text(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        text = (arguments.get("text") or "").strip()
        if not text:
            return {"error": "No text provided"}

        classification = await self.classification_service.classify_text(text)
        return {"text": text, "classification": classification}

    async def _tool_dashboard_stats(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        date_range = arguments.get("date_range") or "all"
        stats = await get_dashboard_stats(self.db, date_range)
        return stats.model_dump(mode="json")
