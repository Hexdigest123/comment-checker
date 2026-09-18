"""
AI Assistant service for per-user Mistral-powered chat with tool execution.

This service provides:
- Conversational AI using mistral-medium-3.5
- Tool execution: search, classify, export, move (navigation)
- Per-user conversation context
- Integration with existing services
"""

import uuid
import json
import time
import csv
import io
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import httpx
from sqlalchemy import select, desc, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import (
    AIConversation,
    Comment,
    Classification,
    ExternalAccount,
    AccountCluster,
    User,
)
from ..db.models.ai_conversation import MessageRoleEnum, ToolTypeEnum
from .embedding import EmbeddingService
from .clustering import ClusteringService
from .classification import ClassificationService


class AIAssistantService:
    """
    AI Assistant service for per-user chat with Mistral-medium-3.5.
    
    Features:
    - Per-user conversation management
    - Tool execution (search, classify, export, move)
    - Natural language understanding
    - Context-aware responses
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        clustering_service: Optional[ClusteringService] = None,
        classification_service: Optional[ClassificationService] = None
    ):
        self.db = db
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Services (lazy loaded if not provided)
        self._embedding_service = embedding_service
        self._clustering_service = clustering_service
        self._classification_service = classification_service
        
        # Mistral configuration
        self.model = "mistral-medium-3.5"
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        
        # Tool definitions for the AI
        self.tools = {
            "search": {
                "description": "Search through comments, accounts, and clusters using semantic and keyword search",
                "parameters": {
                    "query": "string (required) - Search query",
                    "type": "string (optional) - Search type: comments, accounts, clusters, all (default: all)",
                    "limit": "integer (optional) - Maximum results (default: 10)"
                },
                "examples": [
                    "search for hate speech comments",
                    "find all comments by user john_doe on twitter",
                    "search clusters with high toxicity"
                ]
            },
            "classify": {
                "description": "Classify a comment or text using the classification system",
                "parameters": {
                    "text": "string (required) - Text to classify",
                    "comment_id": "string (optional) - Existing comment ID to reclassify"
                },
                "examples": [
                    "classify this comment as hate speech",
                    "reclassify comment abc123",
                    "what category does this text belong to?"
                ]
            },
            "export": {
                "description": "Export data (comments, classifications, clusters) to CSV or JSON",
                "parameters": {
                    "type": "string (required) - Export type: comments, classifications, clusters, accounts",
                    "format": "string (optional) - Format: csv or json (default: csv)",
                    "filter": "string (optional) - Filter criteria (e.g., 'status=processed', 'category=hate')"
                },
                "examples": [
                    "export all processed comments as CSV",
                    "export hate speech classifications",
                    "export clusters to JSON"
                ]
            },
            "move": {
                "description": "Navigate to specific parts of the application or guide the user",
                "parameters": {
                    "target": "string (required) - Navigation target: dashboard, comments, clusters, accounts, classifications, upload, invites",
                    "action": "string (optional) - Specific action: view, edit, filter, create",
                    "id": "string (optional) - Specific ID to navigate to",
                    "filter": "string (optional) - Filter to apply"
                },
                "examples": [
                    "go to clusters page",
                    "show me cluster xyz123",
                    "filter comments by hate category",
                    "go to upload page"
                ]
            },
            "summarize": {
                "description": "Summarize data or generate reports",
                "parameters": {
                    "type": "string (required) - Summarize type: cluster, account, comments, dashboard",
                    "id": "string (optional) - Specific ID to summarize",
                    "period": "string (optional) - Time period: today, week, month, year, all"
                },
                "examples": [
                    "summarize cluster abc123",
                    "summarize all comments from this week",
                    "give me a report of toxicity by cluster"
                ]
            },
            "analyze": {
                "description": "Analyze patterns in the data",
                "parameters": {
                    "type": "string (required) - Analysis type: toxicity, activity, connections, trends",
                    "target": "string (optional) - Target: cluster, account, platform, all"
                },
                "examples": [
                    "analyze toxicity patterns across clusters",
                    "show me activity trends",
                    "analyze connections between accounts"
                ]
            }
        }
    
    @property
    def embedding_service(self) -> EmbeddingService:
        """Lazy load embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(self.db)
        return self._embedding_service
    
    @property
    def clustering_service(self) -> ClusteringService:
        """Lazy load clustering service."""
        if self._clustering_service is None:
            self._clustering_service = ClusteringService(self.db)
        return self._clustering_service
    
    @property
    def classification_service(self) -> ClassificationService:
        """Lazy load classification service."""
        if self._classification_service is None:
            from .classification import ClassificationService
            self._classification_service = ClassificationService(self.db)
        return self._classification_service
    
    async def chat(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
        use_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Handle a chat message from a user.
        
        This is the main entry point for the AI assistant. It:
        1. Stores the user message
        2. Determines if a tool should be used
        3. Executes the tool if needed
        4. Generates a response with Mistral
        5. Stores the assistant response
        6. Returns the complete response
        
        Args:
            user_id: Internal user ID
            message: User's message
            session_id: Optional session ID for conversation context
            use_tools: Whether to allow tool usage
            
        Returns:
            Dictionary containing:
            - response: Assistant's response text
            - tool_used: Tool that was used (if any)
            - tool_input: Input passed to tool
            - tool_output: Output from tool
            - conversation_id: ID of the assistant's message
            - session_id: Current session ID
        """
        # Generate or use session ID
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Store user message
        user_conversation = AIConversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=MessageRoleEnum.USER,
            content=message,
            tool_used=ToolTypeEnum.NONE
        )
        self.db.add(user_conversation)
        await self.db.commit()
        
        # Get conversation history for context
        history = await self._get_conversation_history(user_id, session_id, limit=10)
        
        # Check if user wants to use a tool
        tool_result = None
        if use_tools:
            tool_result = await self._check_for_tool(message, user_id)
        
        # Generate response
        start_time = time.time()
        
        if tool_result and tool_result.get("should_use"):
            # Execute tool and generate response based on result
            tool_name = tool_result["tool"]
            tool_input = tool_result.get("input", {})
            
            # Execute the tool
            tool_output = await self._execute_tool(tool_name, tool_input, user_id)
            
            # Generate response with tool result
            response_text = await self._generate_response_with_tool(
                message, 
                tool_name, 
                tool_input, 
                tool_output,
                history
            )
            
            # Store assistant message with tool info
            assistant_conversation = AIConversation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role=MessageRoleEnum.ASSISTANT,
                content=response_text,
                tool_used=ToolTypeEnum(tool_name),
                tool_input=tool_input,
                tool_output=tool_output,
                response_model=self.model,
                response_tokens=len(response_text.split()),
                latency_ms=int((time.time() - start_time) * 1000)
            )
            self.db.add(assistant_conversation)
            await self.db.commit()
            await self.db.refresh(assistant_conversation)
            
            return {
                "response": response_text,
                "tool_used": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output,
                "conversation_id": assistant_conversation.id,
                "session_id": session_id,
                "model": self.model,
                "tokens": assistant_conversation.response_tokens,
                "latency_ms": assistant_conversation.latency_ms
            }
        else:
            # Regular chat without tool
            response_text = await self._generate_response(message, history)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Store assistant message
            assistant_conversation = AIConversation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                role=MessageRoleEnum.ASSISTANT,
                content=response_text,
                tool_used=ToolTypeEnum.NONE,
                response_model=self.model,
                response_tokens=len(response_text.split()),
                latency_ms=latency_ms
            )
            self.db.add(assistant_conversation)
            await self.db.commit()
            await self.db.refresh(assistant_conversation)
            
            return {
                "response": response_text,
                "tool_used": None,
                "tool_input": None,
                "tool_output": None,
                "conversation_id": assistant_conversation.id,
                "session_id": session_id,
                "model": self.model,
                "tokens": assistant_conversation.response_tokens,
                "latency_ms": assistant_conversation.latency_ms
            }
    
    async def _check_for_tool(
        self,
        message: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Determine if the user wants to use a tool.
        
        Uses pattern matching and intent detection to identify tool usage.
        
        Args:
            message: User message
            user_id: User ID (for permission checks)
            
        Returns:
            Dictionary with tool info or None if no tool should be used
        """
        message_lower = message.lower().strip()
        
        # Remove common prefixes
        for prefix in ["please", "can you", "could you", "i want to", "i need to", "help me"]:
            if message_lower.startswith(prefix):
                message_lower = message_lower[len(prefix):].strip()
        
        # Check for tool patterns
        for tool_name, tool_info in self.tools.items():
            # Check for explicit tool mentions
            if f"use {tool_name}" in message_lower or f"{tool_name} " in message_lower:
                # Extract parameters
                params = self._extract_tool_parameters(tool_name, message_lower)
                if params is not None:
                    return {
                        "should_use": True,
                        "tool": tool_name,
                        "input": params
                    }
            
            # Check for implicit tool usage via examples
            for example in tool_info.get("examples", []):
                if example in message_lower:
                    params = self._extract_tool_parameters(tool_name, message_lower)
                    return {
                        "should_use": True,
                        "tool": tool_name,
                        "input": params or {}
                    }
        
        # Check for search patterns
        search_triggers = [
            "search",
            "find",
            "look for",
            "show me",
            "list",
            "query"
        ]
        for trigger in search_triggers:
            if message_lower.startswith(trigger):
                # Extract query
                query = message[len(trigger):].strip()
                if query:
                    return {
                        "should_use": True,
                        "tool": "search",
                        "input": {"query": query}
                    }
        
        # Check for classify patterns
        classify_triggers = [
            "classify",
            "categorize",
            "what category",
            "is this",
            "check if"
        ]
        for trigger in classify_triggers:
            if trigger in message_lower:
                return {
                    "should_use": True,
                    "tool": "classify",
                    "input": {"text": message}
                }
        
        # Check for export patterns
        export_triggers = [
            "export",
            "download",
            "save as",
            "generate csv",
            "generate json"
        ]
        for trigger in export_triggers:
            if trigger in message_lower:
                return {
                    "should_use": True,
                    "tool": "export",
                    "input": {}
                }
        
        # Check for move/navigation patterns
        move_triggers = [
            "go to",
            "navigate to",
            "open",
            "show",
            "take me to"
        ]
        for trigger in move_triggers:
            if message_lower.startswith(trigger):
                target = message[len(trigger):].strip()
                return {
                    "should_use": True,
                    "tool": "move",
                    "input": {"target": target}
                }
        
        return None
    
    async def _execute_tool(
        self,
        tool: str,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute a specific tool.
        
        Args:
            tool: Tool name (search, classify, export, move, summarize, analyze)
            input_data: Input parameters for the tool
            user_id: User ID for permission checks
            
        Returns:
            Tool output as dictionary
        """
        try:
            if tool == "search":
                return await self._tool_search(input_data, user_id)
            elif tool == "classify":
                return await self._tool_classify(input_data, user_id)
            elif tool == "export":
                return await self._tool_export(input_data, user_id)
            elif tool == "move":
                return await self._tool_move(input_data, user_id)
            elif tool == "summarize":
                return await self._tool_summarize(input_data, user_id)
            elif tool == "analyze":
                return await self._tool_analyze(input_data, user_id)
            else:
                return {"error": f"Unknown tool: {tool}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_search(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute search tool."""
        query = input_data.get("query", "")
        search_type = input_data.get("type", "all")
        limit = input_data.get("limit", 10)
        
        if not query:
            return {"error": "No search query provided"}
        
        results = []
        
        # Search comments
        if search_type in ["all", "comments"]:
            comment_results = await self._search_comments(query, limit)
            results.extend([
                {"type": "comment", **r} 
                for r in comment_results
            ])
        
        # Search accounts
        if search_type in ["all", "accounts"]:
            account_results = await self._search_accounts(query, limit)
            results.extend([
                {"type": "account", **r} 
                for r in account_results
            ])
        
        # Search clusters
        if search_type in ["all", "clusters"]:
            cluster_results = await self._search_clusters(query, limit)
            results.extend([
                {"type": "cluster", **r} 
                for r in cluster_results
            ])
        
        return {
            "query": query,
            "type": search_type,
            "results": results[:limit],
            "total": len(results),
            "limit": limit
        }
    
    async def _tool_classify(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute classify tool."""
        text = input_data.get("text", "")
        comment_id = input_data.get("comment_id")
        
        if not text and not comment_id:
            return {"error": "No text or comment_id provided"}
        
        if comment_id:
            # Reclassify existing comment
            result = await self.db.execute(
                select(Comment).where(Comment.id == comment_id)
            )
            comment = result.scalar_one_or_none()
            if not comment:
                return {"error": f"Comment {comment_id} not found"}
            text = comment.text
        
        # Use classification service
        classification = await self.classification_service.classify_text(text)
        
        return {
            "text": text,
            "classification": classification,
            "model": self.classification_service.default_backend
        }
    
    async def _tool_export(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute export tool."""
        export_type = input_data.get("type", "comments")
        format_type = input_data.get("format", "csv")
        filter_str = input_data.get("filter", "")
        
        # Parse filter
        filters = self._parse_filter(filter_str)
        
        if export_type == "comments":
            data = await self._export_comments(filters)
        elif export_type == "classifications":
            data = await self._export_classifications(filters)
        elif export_type == "clusters":
            data = await self._export_clusters(filters)
        elif export_type == "accounts":
            data = await self._export_accounts(filters)
        else:
            return {"error": f"Unknown export type: {export_type}"}
        
        # Format data
        if format_type == "csv":
            output = self._format_as_csv(data)
        else:
            output = json.dumps(data, indent=2)
        
        return {
            "type": export_type,
            "format": format_type,
            "data": output,
            "count": len(data)
        }
    
    async def _tool_move(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute move tool for navigation assistance.
        
        This tool guides users to specific parts of the application.
        """
        target = input_data.get("target", "")
        action = input_data.get("action", "view")
        item_id = input_data.get("id")
        filter_str = input_data.get("filter", "")
        
        # Normalize target
        target_lower = target.lower().strip()
        
        # Map common terms to actual routes
        route_map = {
            "dashboard": "/",
            "home": "/",
            "comments": "/comments",
            "comment": "/comments",
            "classifications": "/classifications",
            "classification": "/classifications",
            "clusters": "/clusters",
            "cluster": "/clusters",
            "accounts": "/accounts",
            "account": "/accounts",
            "upload": "/upload",
            "invites": "/invites",
            "settings": "/settings",
            "search": "/search"
        }
        
        # Try to match target
        route = route_map.get(target_lower, "/")
        
        # Build URL
        url = route
        
        # Add filter if provided
        if filter_str:
            url += f"?q={filter_str}"
        
        # Add ID if provided
        if item_id:
            url += f"/{item_id}"
        
        return {
            "action": "navigate",
            "url": url,
            "target": target,
            "message": f"Taking you to {target}..."
        }
    
    async def _tool_summarize(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute summarize tool."""
        summarize_type = input_data.get("type", "dashboard")
        item_id = input_data.get("id")
        period = input_data.get("period", "all")
        
        if summarize_type == "cluster" and item_id:
            return await self._summarize_cluster(item_id)
        elif summarize_type == "account" and item_id:
            return await self._summarize_account(item_id)
        elif summarize_type == "comments":
            return await self._summarize_comments(period)
        elif summarize_type == "dashboard":
            return await self._summarize_dashboard(period)
        else:
            return {"error": f"Cannot summarize {summarize_type}"}
    
    async def _tool_analyze(
        self,
        input_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Execute analyze tool."""
        analysis_type = input_data.get("type", "toxicity")
        target = input_data.get("target", "all")
        
        if analysis_type == "toxicity":
            return await self._analyze_toxicity(target)
        elif analysis_type == "activity":
            return await self._analyze_activity(target)
        elif analysis_type == "connections":
            return await self._analyze_connections(target)
        else:
            return {"error": f"Cannot analyze {analysis_type}"}
    
    async def _generate_response(
        self,
        message: str,
        history: List[AIConversation]
    ) -> str:
        """
        Generate a response using Mistral API.
        
        Args:
            message: User message
            history: Conversation history
            
        Returns:
            Generated response text
        """
        # Build messages list for Mistral
        messages = []
        
        # Add system prompt
        system_prompt = self._get_system_prompt()
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add history
        for conv in history:
            role = "user" if conv.role == MessageRoleEnum.USER else "assistant"
            messages.append({
                "role": role,
                "content": conv.content
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Call Mistral API
        try:
            response = await self.client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.settings.mistral_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract response
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return "I'm sorry, I couldn't generate a response."
                
        except httpx.HTTPStatusError as e:
            return f"I'm sorry, there was an error generating a response: {e.response.status_code}"
        except Exception as e:
            return f"I'm sorry, there was an error: {str(e)}"
    
    async def _generate_response_with_tool(
        self,
        message: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Dict[str, Any],
        history: List[AIConversation]
    ) -> str:
        """
        Generate a response that incorporates tool results.
        
        Args:
            message: User message
            tool_name: Tool that was executed
            tool_input: Input to the tool
            tool_output: Output from the tool
            history: Conversation history
            
        Returns:
            Generated response text
        """
        # Build tool result message
        tool_message = f"\n\n[Tool Result: {tool_name}]\n"
        
        if "error" in tool_output:
            tool_message += f"Error: {tool_output['error']}"
        elif tool_name == "search":
            results = tool_output.get("results", [])
            tool_message += f"Found {tool_output.get('total', 0)} results:\n"
            for r in results[:5]:  # Show first 5
                if r.get("type") == "comment":
                    tool_message += f"- Comment: {r.get('text', '')[:100]}...\n"
                elif r.get("type") == "account":
                    tool_message += f"- Account: {r.get('username', '')} ({r.get('platform', '')})\n"
                elif r.get("type") == "cluster":
                    tool_message += f"- Cluster: {r.get('name', '')} ({r.get('type', '')})\n"
        elif tool_name == "classify":
            classification = tool_output.get("classification", {})
            tool_message += f"Classification: {classification}"
        elif tool_name == "export":
            tool_message += f"Exported {tool_output.get('count', 0)} items"
        elif tool_name == "move":
            tool_message += f"Navigate to: {tool_output.get('url', '')}"
        else:
            tool_message += json.dumps(tool_output, indent=2)
        
        # Build messages list
        messages = []
        
        # Add system prompt
        system_prompt = self._get_system_prompt()
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add history
        for conv in history:
            role = "user" if conv.role == MessageRoleEnum.USER else "assistant"
            messages.append({
                "role": role,
                "content": conv.content
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Add tool result as assistant message
        messages.append({
            "role": "assistant",
            "content": tool_message
        })
        
        # Generate final response
        try:
            response = await self.client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.settings.mistral_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return "I've executed the tool for you. Is there anything else you need?"
                
        except Exception as e:
            return f"Tool executed. Result: {tool_message}\n\nIs there anything else I can help you with?"
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI assistant."""
        return """You are a helpful AI assistant for the Comment Checker application. 
You help users manage and analyze comments from social media platforms.

Your capabilities include:
- Answering questions about comments, classifications, and clusters
- Searching through data using natural language
- Classifying comments for toxicity and categories
- Exporting data to CSV or JSON
- Guiding users through the application (move/navigate)
- Summarizing data and generating reports
- Analyzing patterns and trends

Available tools you can use:
- search: Find comments, accounts, or clusters
- classify: Classify text or comments
- export: Export data to CSV/JSON
- move: Navigate to specific pages in the app
- summarize: Summarize data or generate reports
- analyze: Analyze patterns in the data

When a user asks for something that matches a tool's purpose, use that tool.
Always be helpful, concise, and professional.

Remember:
- You are per-user, so each user has their own conversation context
- Always respect user privacy and data confidentiality
- If you don't know something, say so rather than making it up
- For sensitive operations, guide the user to do it themselves

The current date is {datetime.now().strftime('%Y-%m-%d')}."""
    
    async def _get_conversation_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[AIConversation]:
        """Get conversation history for context."""
        result = await self.db.execute(
            select(AIConversation)
            .where(
                AIConversation.user_id == user_id,
                AIConversation.session_id == session_id
            )
            .order_by(AIConversation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    def _extract_tool_parameters(
        self,
        tool: str,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """Extract parameters for a tool from a message."""
        # Simple implementation - can be enhanced with better parsing
        params = {}
        
        if tool == "search":
            # Extract query
            for prefix in ["search for", "find", "look for", "show me", "search"]:
                if message.startswith(prefix):
                    params["query"] = message[len(prefix):].strip()
                    break
            else:
                params["query"] = message
            
            # Check for type
            if "comments" in message.lower():
                params["type"] = "comments"
            elif "accounts" in message.lower():
                params["type"] = "accounts"
            elif "clusters" in message.lower():
                params["type"] = "clusters"
            else:
                params["type"] = "all"
            
            # Check for limit
            if "limit" in message.lower():
                try:
                    import re
                    match = re.search(r'limit\s+(\d+)', message.lower())
                    if match:
                        params["limit"] = int(match.group(1))
                except:
                    pass
        
        elif tool == "classify":
            params["text"] = message
        
        elif tool == "export":
            if "csv" in message.lower():
                params["format"] = "csv"
            elif "json" in message.lower():
                params["format"] = "json"
            
            if "comments" in message.lower():
                params["type"] = "comments"
            elif "classifications" in message.lower():
                params["type"] = "classifications"
            elif "clusters" in message.lower():
                params["type"] = "clusters"
            elif "accounts" in message.lower():
                params["type"] = "accounts"
        
        return params if params else None
    
    async def _search_comments(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search comments using hybrid search."""
        # Use embedding service for semantic search
        try:
            results = await self.embedding_service.hybrid_search(query, limit)
            return [
                {
                    "id": r[0].id,
                    "text": r[0].text[:200] + "..." if len(r[0].text) > 200 else r[0].text,
                    "score": r[1],
                    "source": r[2] if len(r) > 2 else "unknown"
                }
                for r in results
            ]
        except:
            # Fallback to keyword search
            result = await self.db.execute(
                select(Comment)
                .where(Comment.text.ilike(f"%{query}%"))
                .order_by(desc(Comment.created_at))
                .limit(limit)
            )
            comments = result.scalars().all()
            return [
                {
                    "id": c.id,
                    "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
                    "score": 1.0,
                    "source": "keyword"
                }
                for c in comments
            ]
    
    async def _search_accounts(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search external accounts."""
        result = await self.db.execute(
            select(ExternalAccount)
            .where(
                or_(
                    ExternalAccount.username.ilike(f"%{query}%"),
                    ExternalAccount.display_name.ilike(f"%{query}%"),
                    ExternalAccount.bio.ilike(f"%{query}%")
                )
            )
            .order_by(desc(ExternalAccount.created_at))
            .limit(limit)
        )
        accounts = result.scalars().all()
        return [
            {
                "id": a.id,
                "username": a.username,
                "display_name": a.display_name,
                "platform": a.platform.value,
                "cluster_id": a.cluster_id
            }
            for a in accounts
        ]
    
    async def _search_clusters(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search clusters."""
        result = await self.db.execute(
            select(AccountCluster)
            .where(
                or_(
                    AccountCluster.name.ilike(f"%{query}%"),
                    AccountCluster.description.ilike(f"%{query}%")
                )
            )
            .order_by(desc(AccountCluster.toxicity_score))
            .limit(limit)
        )
        clusters = result.scalars().all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "type": c.cluster_type.value,
                "toxicity_score": c.toxicity_score,
                "comment_count": c.comment_count
            }
            for c in clusters
        ]
    
    def _parse_filter(self, filter_str: str) -> Dict[str, Any]:
        """Parse a filter string into a dictionary."""
        filters = {}
        if not filter_str:
            return filters
        
        # Simple parsing
        parts = filter_str.split(",")
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                filters[key.strip()] = value.strip()
        
        return filters
    
    async def _export_comments(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Export comments data."""
        query = select(Comment)
        
        # Apply filters
        if "status" in filters:
            query = query.where(Comment.status == filters["status"])
        if "category" in filters:
            query = query.join(Comment.classifications)
            query = query.where(
                Classification.category == filters["category"]
            )
        
        result = await self.db.execute(
            query.order_by(desc(Comment.created_at))
        )
        comments = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "text": c.text,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "platform": c.platform,
                "author_name": c.author_name,
                "author_platform": c.author_platform
            }
            for c in comments
        ]
    
    async def _export_classifications(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Export classifications data."""
        query = select(Classification)
        
        if "category" in filters:
            query = query.where(
                Classification.category == filters["category"]
            )
        if "severity" in filters:
            query = query.where(
                Classification.severity == filters["severity"]
            )
        
        result = await self.db.execute(
            query.order_by(desc(Classification.created_at))
        )
        classifications = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "comment_id": c.comment_id,
                "category": c.category,
                "severity": c.severity,
                "confidence": c.confidence,
                "harmful_score": c.harmful_score,
                "backend": c.backend,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in classifications
        ]
    
    async def _export_clusters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Export clusters data."""
        result = await self.db.execute(
            select(AccountCluster)
            .order_by(desc(AccountCluster.toxicity_score))
        )
        clusters = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "name": c.name,
                "type": c.cluster_type.value,
                "description": c.description,
                "toxicity_score": c.toxicity_score,
                "comment_count": c.comment_count,
                "account_count": len(c.accounts) if c.accounts else 0
            }
            for c in clusters
        ]
    
    async def _export_accounts(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Export accounts data."""
        result = await self.db.execute(
            select(ExternalAccount)
            .order_by(desc(ExternalAccount.created_at))
        )
        accounts = result.scalars().all()
        
        return [
            {
                "id": a.id,
                "username": a.username,
                "display_name": a.display_name,
                "platform": a.platform.value,
                "cluster_id": a.cluster_id,
                "follower_count": a.follower_count,
                "verified": a.verified
            }
            for a in accounts
        ]
    
    def _format_as_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format data as CSV string."""
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    async def _summarize_cluster(self, cluster_id: str) -> Dict[str, Any]:
        """Summarize a cluster."""
        result = await self.db.execute(
            select(AccountCluster)
            .where(AccountCluster.id == cluster_id)
            .options(
                selectinload(AccountCluster.accounts),
                selectinload(AccountCluster.connections_out),
                selectinload(AccountCluster.connections_in)
            )
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            return {"error": f"Cluster {cluster_id} not found"}
        
        return {
            "id": cluster.id,
            "name": cluster.name,
            "type": cluster.cluster_type.value,
            "description": cluster.description,
            "account_count": len(cluster.accounts) if cluster.accounts else 0,
            "comment_count": cluster.comment_count,
            "toxicity_score": cluster.toxicity_score,
            "platforms": cluster.platform_distribution,
            "connections": len(cluster.connections_out) + len(cluster.connections_in)
        }
    
    async def _summarize_account(self, account_id: str) -> Dict[str, Any]:
        """Summarize an account."""
        result = await self.db.execute(
            select(ExternalAccount)
            .where(ExternalAccount.id == account_id)
            .options(
                selectinload(ExternalAccount.comments),
                selectinload(ExternalAccount.cluster)
            )
        )
        account = result.scalar_one_or_none()
        
        if not account:
            return {"error": f"Account {account_id} not found"}
        
        return {
            "id": account.id,
            "username": account.username,
            "display_name": account.display_name,
            "platform": account.platform.value,
            "cluster": account.cluster.name if account.cluster else None,
            "comment_count": len(account.comments) if account.comments else 0,
            "follower_count": account.follower_count,
            "verified": account.verified
        }
    
    async def _summarize_comments(self, period: str) -> Dict[str, Any]:
        """Summarize comments for a period."""
        # Get date range
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        if period == "today":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        query = select(Comment)
        if start_date:
            query = query.where(Comment.created_at >= start_date)
        
        result = await self.db.execute(query)
        comments = result.scalars().all()
        
        # Get classifications
        class_result = await self.db.execute(
            select(Classification)
            .join(Comment, Classification.comment_id == Comment.id)
        )
        classifications = class_result.scalars().all()
        
        # Count by category
        category_counts = {}
        for c in classifications:
            category_counts[c.category] = category_counts.get(c.category, 0) + 1
        
        return {
            "period": period,
            "total_comments": len(comments),
            "total_classifications": len(classifications),
            "category_distribution": category_counts
        }
    
    async def _summarize_dashboard(self, period: str) -> Dict[str, Any]:
        """Summarize dashboard data."""
        # Get stats from dashboard service
        from .dashboard import DashboardService
        dashboard_service = DashboardService(self.db)
        stats = await dashboard_service.get_stats()
        
        return {
            "period": period,
            "stats": {
                "in_processing": stats.in_processing,
                "waiting": stats.waiting,
                "processed": stats.processed,
                "failed": stats.failed,
                "total": stats.total
            },
            "category_distribution": stats.category_distribution
        }
    
    async def _analyze_toxicity(self, target: str) -> Dict[str, Any]:
        """Analyze toxicity patterns."""
        if target == "all":
            # Get all clusters with toxicity
            result = await self.db.execute(
                select(AccountCluster)
                .order_by(desc(AccountCluster.toxicity_score))
            )
            clusters = result.scalars().all()
            
            return {
                "type": "toxicity",
                "target": "all",
                "clusters": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "toxicity_score": c.toxicity_score,
                        "comment_count": c.comment_count
                    }
                    for c in clusters
                ]
            }
        else:
            # Analyze specific cluster
            result = await self.db.execute(
                select(AccountCluster).where(AccountCluster.id == target)
            )
            cluster = result.scalar_one_or_none()
            
            if not cluster:
                return {"error": f"Cluster {target} not found"}
            
            # Get comments in cluster
            result = await self.db.execute(
                select(Comment)
                .join(ExternalAccount, Comment.external_account_id == ExternalAccount.id)
                .where(ExternalAccount.cluster_id == cluster.id)
            )
            comments = result.scalars().all()
            
            # Get classifications
            class_result = await self.db.execute(
                select(Classification)
                .where(Classification.comment_id.in_([c.id for c in comments]))
            )
            classifications = class_result.scalars().all()
            
            # Calculate average toxicity
            if classifications:
                avg_toxicity = sum(
                    c.harmful_score for c in classifications
                ) / len(classifications)
            else:
                avg_toxicity = 0
            
            return {
                "type": "toxicity",
                "target": target,
                "cluster_name": cluster.name,
                "average_toxicity": avg_toxicity,
                "comment_count": len(comments),
                "classification_count": len(classifications)
            }
    
    async def _analyze_activity(self, target: str) -> Dict[str, Any]:
        """Analyze activity patterns."""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        
        # Get activity by day for last 30 days
        result = await self.db.execute(
            select(
                func.date_trunc('day', Comment.created_at).label('day'),
                func.count(Comment.id).label('count')
            )
            .where(Comment.created_at >= now - timedelta(days=30))
            .group_by('day')
            .order_by('day')
        )
        
        daily_activity = [
            {"day": row[0].isoformat() if row[0] else None, "count": row[1]}
            for row in result.all()
        ]
        
        return {
            "type": "activity",
            "target": target,
            "daily_activity": daily_activity
        }
    
    async def _analyze_connections(self, target: str) -> Dict[str, Any]:
        """Analyze cluster connections."""
        from .clustering import ClusteringService
        clustering_service = ClusteringService(self.db)
        
        if target == "all":
            graph_data = await clustering_service.get_cluster_graph()
            
            return {
                "type": "connections",
                "target": "all",
                "nodes": len(graph_data["nodes"]),
                "links": len(graph_data["links"]),
                "graph": graph_data
            }
        else:
            # Get connections for specific cluster
            connections, _ = await clustering_service.get_connections(
                cluster_id=target,
                limit=100
            )
            
            return {
                "type": "connections",
                "target": target,
                "connections": [
                    {
                        "id": c.id,
                        "cluster_a": c.cluster_a.name if c.cluster_a else None,
                        "cluster_b": c.cluster_b.name if c.cluster_b else None,
                        "type": c.connection_type.value,
                        "confidence": c.confidence,
                        "status": c.status.value
                    }
                    for c in connections
                ]
            }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
