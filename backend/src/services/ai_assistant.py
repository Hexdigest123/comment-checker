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
from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import (
    AIConversation,
    Classification,
    ClassificationCategory,
    ClassificationSeverity,
    Comment,
    CommentStatus,
)
from ..db.models.ai_conversation import MessageRoleEnum, ToolTypeEnum
from .classification import ClassificationService
from .dashboard import get_dashboard_stats
from .embedding import EmbeddingService

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

# Map tool names onto the persisted ToolTypeEnum values.
TOOL_TO_ENUM = {
    "filter_comments": ToolTypeEnum.SEARCH,
    "semantic_search_comments": ToolTypeEnum.SEARCH,
    "classify_text": ToolTypeEnum.CLASSIFY,
    "get_dashboard_stats": ToolTypeEnum.SUMMARIZE,
}

SYSTEM_PROMPT = """You are the AI assistant of Comment Checker, a system that collects \
comments from social media, classifies them for harmful content (hate speech, threats, \
insults, ...) and clusters the accounts behind them.

You answer questions about the user's data. You have tools:
- filter_comments: structured search returning ALL comments matching exact \
filters (classification category, severity, status, date range, minimum \
harmful score). Use it whenever the question names a category (hate, \
harassment, violence, ...), a severity, a status or a time period — e.g. \
"which hateful comments did we receive in the last month" becomes \
category=hate with date_start/date_end computed from the current date.
- semantic_search_comments: finds comments by MEANING (embeddings), even when no \
keyword matches. Use it when the user looks for comments about a topic by \
meaning. It can be combined with filter_comments (e.g. filter first, then \
semantically rank) when both a category and a topic are given.
- classify_text: classifies a given text through the moderation pipeline \
(category, severity, harmful score, confidence).
- get_dashboard_stats: returns aggregate statistics (totals, flag rate, \
category and status distributions).

Guidelines:
- Prefer tools over guessing; never invent data.
- After a tool call, summarize the result in natural language (short sentences, \
lists where helpful). Do not dump raw JSON.
- When you list comments, include for each one the comment_url (link to the \
original comment) and the author when available, plus any other metadata the \
user asks about (likes, dates, classification scores, ...).
- The comment's date is posted_at (when it was written on the platform). \
created_at is only when it was ingested; never present it as the comment date.
- If a tool returns an error, say so plainly.
- If the answer does not need data (small talk, general questions), just answer.
- Format your replies using Markdown (headings, bullet lists, **bold**, \
inline `code`, tables) when it improves readability; keep prose answers \
plain. Never use raw HTML.
- The current date is {date}."""


def _parse_enum_argument(
    value: Any, enum_cls: type, label: str
) -> tuple[Any, dict[str, Any] | None]:
    """Parse a tool argument into an enum, or return an error payload."""
    if value in (None, ""):
        return None, None
    try:
        return enum_cls(str(value).lower()), None
    except ValueError:
        valid = ", ".join(member.value for member in enum_cls)
        return None, {"error": f"Invalid {label} '{value}'. Valid values: {valid}"}


def _classification_metadata(
    classification: Classification | None,
) -> dict[str, Any] | None:
    """Serialize a classification with all stored fields."""
    if classification is None:
        return None
    return {
        "backend": getattr(classification.backend, "value", classification.backend),
        "category": getattr(classification.category, "value", classification.category),
        "severity": getattr(classification.severity, "value", classification.severity),
        "confidence": classification.confidence,
        "harmful_score": classification.harmful_score,
        "created_at": (
            classification.created_at.isoformat()
            if classification.created_at
            else None
        ),
    }


def _comment_metadata(
    comment: Comment, classification: Classification | None = None
) -> dict[str, Any]:
    """Serialize a comment with all stored metadata, plus its classification."""
    return {
        "id": comment.id,
        "text": comment.text,
        "author": comment.original_author,
        "author_id": comment.original_author_id,
        "author_profile_url": comment.original_author_url,
        "comment_url": comment.source_url,
        "platform": comment.source_platform,
        "platform_comment_id": comment.platform_comment_id,
        "context": comment.context,
        "status": getattr(comment.status, "value", comment.status),
        "priority": getattr(comment.priority, "value", comment.priority),
        "vote_score": comment.vote_score,
        "posted_at": (
            comment.posted_at.isoformat() if comment.posted_at else None
        ),
        "created_at": (
            comment.created_at.isoformat() if comment.created_at else None
        ),
        "metadata": comment.extra_metadata or None,
        "classification": _classification_metadata(classification),
    }


def _parse_filter_date(value: Any, end_of_day: bool) -> datetime | None:
    """Parse an ISO date/datetime argument; bare end dates cover the whole day."""
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        raise ValueError(
            f"Invalid date '{value}'. Use ISO format, e.g. '2026-08-24'."
        ) from None
    if end_of_day and (parsed.hour, parsed.minute, parsed.second, parsed.microsecond) == (
        0,
        0,
        0,
        0,
    ):
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


class AIAssistantService:
    """Per-user chat service backed by the Mistral chat completions API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.model = "mistral-medium-3.5"
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

        self._embedding_service: EmbeddingService | None = None
        self._classification_service: ClassificationService | None = None

        # Comments visible to the assistant's tools: None means unrestricted
        # (admin); set per chat() call for regular users.
        self._scope_user_id: int | str | None = None

        # Mistral function-calling tool definitions
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "filter_comments",
                    "description": (
                        "Structured search over comments. Returns all comments "
                        "matching exact filters: classification category, "
                        "severity, status, date range and/or minimum harmful "
                        "score. Prefer this over semantic search whenever the "
                        "question mentions a category (hate, harassment, "
                        "violence, ...), a severity, a status or a time period."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": [c.value for c in ClassificationCategory],
                                "description": "Classification category to match",
                            },
                            "severity": {
                                "type": "string",
                                "enum": [s.value for s in ClassificationSeverity],
                                "description": "Minimum severity level to match",
                            },
                            "status": {
                                "type": "string",
                                "enum": [s.value for s in CommentStatus],
                                "description": "Comment processing status to match",
                            },
                            "date_start": {
                                "type": "string",
                                "description": (
                                    "Inclusive lower bound on the comment date, "
                                    "ISO format, e.g. '2026-08-24'"
                                ),
                            },
                            "date_end": {
                                "type": "string",
                                "description": (
                                    "Inclusive upper bound on the comment date, "
                                    "ISO format; a bare date covers the whole day"
                                ),
                            },
                            "min_harmful_score": {
                                "type": "number",
                                "description": "Minimum harmful score (0-1)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default 20, max 100)",
                            },
                        },
                    },
                },
            },
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
        is_admin: bool = False,
    ) -> dict[str, Any]:
        """Handle one user turn of the conversation, running tools as needed."""
        if not session_id:
            session_id = str(uuid.uuid4())

        self._scope_user_id = None if is_admin else user_id
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
        if name == "filter_comments":
            return await self._tool_filter_comments(arguments)
        if name == "semantic_search_comments":
            return await self._tool_semantic_search_comments(arguments)
        if name == "classify_text":
            return await self._tool_classify_text(arguments)
        if name == "get_dashboard_stats":
            return await self._tool_dashboard_stats(arguments)
        return {"error": f"Unknown tool: {name}"}

    async def _tool_filter_comments(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        category, error = _parse_enum_argument(
            arguments.get("category"), ClassificationCategory, "category"
        )
        if error:
            return error
        severity, error = _parse_enum_argument(
            arguments.get("severity"), ClassificationSeverity, "severity"
        )
        if error:
            return error
        comment_status, error = _parse_enum_argument(
            arguments.get("status"), CommentStatus, "status"
        )
        if error:
            return error

        try:
            date_start = _parse_filter_date(arguments.get("date_start"), end_of_day=False)
            date_end = _parse_filter_date(arguments.get("date_end"), end_of_day=True)
        except ValueError as exc:
            return {"error": str(exc)}

        min_harmful_score = arguments.get("min_harmful_score")
        if min_harmful_score is not None:
            try:
                min_harmful_score = float(min_harmful_score)
            except (TypeError, ValueError):
                return {"error": f"Invalid min_harmful_score: {min_harmful_score!r}"}

        limit = min(int(arguments.get("limit") or 20), 100)

        # The comment's date is when it was written on the platform
        # (posted_at, from the export), not when it was ingested;
        # fall back to created_at for comments without an export date.
        comment_date = func.coalesce(Comment.posted_at, Comment.created_at)

        conditions = []
        if self._scope_user_id is not None:
            conditions.append(Comment.user_id == self._scope_user_id)
        if comment_status is not None:
            conditions.append(Comment.status == comment_status)
        if date_start is not None:
            conditions.append(comment_date >= date_start)
        if date_end is not None:
            conditions.append(comment_date <= date_end)

        classification_conditions = []
        if category is not None:
            classification_conditions.append(Classification.category == category)
        if severity is not None:
            classification_conditions.append(Classification.severity == severity)
        if min_harmful_score is not None:
            classification_conditions.append(
                Classification.harmful_score >= min_harmful_score
            )
        if classification_conditions:
            matching_comment_ids = (
                select(Classification.comment_id).where(
                    and_(*classification_conditions)
                )
            )
            conditions.append(Comment.id.in_(matching_comment_ids))

        query = select(Comment)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(desc(comment_date)).limit(limit)

        result = await self.db.execute(query)
        comments = result.scalars().all()

        # Attach the most harmful classification per comment; when
        # classification filters were applied, only those rows are considered
        # so the attached row always matches the filters.
        classifications_by_comment: dict[int, Classification] = {}
        if comments:
            classification_query = select(Classification).where(
                Classification.comment_id.in_([c.id for c in comments])
            )
            if classification_conditions:
                classification_query = classification_query.where(
                    and_(*classification_conditions)
                )
            class_result = await self.db.execute(
                classification_query.order_by(desc(Classification.harmful_score))
            )
            for classification in class_result.scalars():
                classifications_by_comment.setdefault(
                    classification.comment_id, classification
                )

        items = [
            _comment_metadata(comment, classifications_by_comment.get(comment.id))
            for comment in comments
        ]

        applied = {
            key: getattr(value, "value", value)
            for key, value in {
                "category": category,
                "severity": severity,
                "status": comment_status,
                "date_start": date_start.isoformat() if date_start else None,
                "date_end": date_end.isoformat() if date_end else None,
                "min_harmful_score": min_harmful_score,
            }.items()
            if value is not None
        }
        return {"filters": applied, "total": len(items), "results": items}

    async def _tool_semantic_search_comments(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"error": "No search query provided"}

        limit = min(int(arguments.get("limit") or 10), 50)
        results = await self.embedding_service.semantic_search(
            query, limit=limit, user_id=self._scope_user_id
        )
        classifications_by_comment = await self._top_classifications_by_comment(
            [comment.id for comment, _ in results]
        )
        return {
            "query": query,
            "total": len(results),
            "results": [
                {
                    **_comment_metadata(
                        comment, classifications_by_comment.get(comment.id)
                    ),
                    "similarity": round(score, 4),
                }
                for comment, score in results
            ],
        }

    async def _top_classifications_by_comment(
        self, comment_ids: list[int]
    ) -> dict[int, Classification]:
        """Return the most harmful classification per comment id."""
        if not comment_ids:
            return {}
        result = await self.db.execute(
            select(Classification)
            .where(Classification.comment_id.in_(comment_ids))
            .order_by(desc(Classification.harmful_score))
        )
        top: dict[int, Classification] = {}
        for classification in result.scalars():
            top.setdefault(classification.comment_id, classification)
        return top

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
