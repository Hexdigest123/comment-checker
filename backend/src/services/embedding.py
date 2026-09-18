"""
Embedding service for generating and managing comment embeddings.

Uses Mistral's embedding model (mistral-embed) to generate vector embeddings
for semantic search via PGVector.
"""

import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Tuple

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import Comment, CommentEmbedding

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing comment embeddings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.embedding_model = "mistral-embed"
        self.embedding_dimension = 768
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text using Mistral's embedding model.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        try:
            response = await self.client.post(
                "https://api.mistral.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.settings.mistral_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.embedding_model,
                    "input": text
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract embedding from response
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            else:
                logger.error(f"Unexpected embedding response: {data}")
                raise ValueError("Unexpected embedding response format")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Mistral API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def generate_and_store_embedding(self, comment: Comment) -> Optional[CommentEmbedding]:
        """
        Generate an embedding for a comment and store it in the database.
        
        Args:
            comment: Comment to generate embedding for
            
        Returns:
            CommentEmbedding instance or None if failed
        """
        try:
            # Check if embedding already exists
            result = await self.db.execute(
                select(CommentEmbedding).where(
                    CommentEmbedding.comment_id == comment.id
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return existing
            
            # Generate embedding
            embedding = await self.generate_embedding(comment.text)
            
            # Create and store embedding
            comment_embedding = CommentEmbedding(
                id=str(uuid.uuid4()),
                comment_id=comment.id,
                embedding=embedding,
                model=self.embedding_model,
                dimension=self.embedding_dimension
            )
            self.db.add(comment_embedding)
            await self.db.commit()
            await self.db.refresh(comment_embedding)
            
            return comment_embedding
            
        except Exception as e:
            logger.error(f"Error generating and storing embedding for comment {comment.id}: {e}")
            await self.db.rollback()
            return None
    
    async def generate_embeddings_batch(
        self,
        comments: List[Comment],
        batch_size: int = 10
    ) -> List[CommentEmbedding]:
        """
        Generate embeddings for a batch of comments.
        
        Args:
            comments: List of comments to generate embeddings for
            batch_size: Number of comments to process at once
            
        Returns:
            List of CommentEmbedding instances
        """
        embeddings = []
        
        # Process in batches to avoid rate limiting
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i + batch_size]
            
            # Generate embeddings for batch
            batch_embeddings = []
            for comment in batch:
                embedding = await self.generate_and_store_embedding(comment)
                if embedding:
                    batch_embeddings.append(embedding)
            
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches
            if i + batch_size < len(comments):
                await asyncio.sleep(0.1)
        
        return embeddings
    
    async def get_embedding(self, comment_id: str) -> Optional[CommentEmbedding]:
        """Get an embedding by comment ID."""
        result = await self.db.execute(
            select(CommentEmbedding).where(
                CommentEmbedding.comment_id == comment_id
            )
        )
        return result.scalar_one_or_none()
    
    async def delete_embedding(self, comment_id: str) -> bool:
        """Delete an embedding by comment ID."""
        result = await self.db.execute(
            delete(CommentEmbedding).where(
                CommentEmbedding.comment_id == comment_id
            )
        )
        return result.rowcount > 0
    
    async def regenerate_embedding(self, comment: Comment) -> Optional[CommentEmbedding]:
        """
        Regenerate an embedding for a comment.
        
        Args:
            comment: Comment to regenerate embedding for
            
        Returns:
            CommentEmbedding instance or None if failed
        """
        # Delete existing embedding
        await self.delete_embedding(comment.id)
        
        # Generate new embedding
        return await self.generate_and_store_embedding(comment)
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Tuple[Comment, float]]:
        """
        Perform semantic search for comments similar to the query.
        
        Uses PGVector's similarity operators to find the most similar comments.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of (comment, similarity_score) tuples, sorted by similarity
        """
        try:
            # Generate embedding for query
            query_embedding = await self.generate_embedding(query)
            
            # Execute vector similarity search
            # Using cosine similarity (1 - cosine distance)
            result = await self.db.execute(
                select(
                    Comment,
                    (1 - (CommentEmbedding.embedding.cosine_distance(query_embedding))) 
                )
                .join(CommentEmbedding, CommentEmbedding.comment_id == Comment.id)
                .order_by(
                    (1 - (CommentEmbedding.embedding.cosine_distance(query_embedding))).desc()
                )
                .limit(limit)
            )
            
            rows = result.all()
            return [(row[0], row[1]) for row in rows]
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def hybrid_search(
        self,
        query: str,
        limit: int = 10
    ) -> List[Tuple[Comment, float, str]]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            
        Returns:
            List of (comment, score, source) tuples
            where source is 'semantic' or 'keyword'
        """
        # Get semantic results
        semantic_results = await self.semantic_search(query, limit)
        
        # Get keyword results (full-text search)
        keyword_results = await self._keyword_search(query, limit)
        
        # Combine and deduplicate results
        combined = {}
        
        for comment, score in semantic_results:
            combined[comment.id] = (comment, score, 'semantic')
        
        for comment, score in keyword_results:
            if comment.id not in combined:
                combined[comment.id] = (comment, score, 'keyword')
            else:
                # If already in semantic results, keep semantic score
                existing_comment, existing_score, _ = combined[comment.id]
                if score > existing_score:
                    combined[comment.id] = (comment, score, 'keyword')
        
        # Sort by score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_results[:limit]
    
    async def _keyword_search(
        self,
        query: str,
        limit: int = 10
    ) -> List[Tuple[Comment, float]]:
        """
        Perform keyword-based full-text search.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            
        Returns:
            List of (comment, score) tuples
        """
        # Use PostgreSQL full-text search
        result = await self.db.execute(
            select(
                Comment,
                func.ts_rank(
                    func.to_tsvector('english', Comment.text),
                    func.plainto_tsquery('english', query)
                )
            )
            .where(
                func.to_tsvector('english', Comment.text).match(
                    func.plainto_tsquery('english', query)
                )
            )
            .order_by(
                func.ts_rank(
                    func.to_tsvector('english', Comment.text),
                    func.plainto_tsquery('english', query)
                ).desc()
            )
            .limit(limit)
        )
        
        rows = result.all()
        return [(row[0], row[1] or 0.0) for row in rows]
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
