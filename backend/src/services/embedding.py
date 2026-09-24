"""
Embedding service for generating and managing comment embeddings.

Uses Mistral's embedding model (mistral-embed) to generate vector embeddings
for semantic search via PGVector.
"""

import uuid
import asyncio
import logging
from typing import Optional, List, Tuple

import httpx
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import Comment, CommentEmbedding

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingService:
    """Service for generating and managing comment embeddings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.embedding_model = "mistral-embed"
        self.embedding_dimension = 1024
    
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
            result = await self.db.execute(
                select(CommentEmbedding).where(
                    CommentEmbedding.comment_id == comment.id
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return existing
            embedding = await self.generate_embedding(comment.text)
            
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
        batch_size: int = 32
    ) -> List[CommentEmbedding]:
        """
        Generate embeddings for a batch of comments using batched API calls.

        Sends multiple texts per request to the Mistral embeddings endpoint
        (which accepts a list of inputs) instead of one request per comment.
        Falls back to per-comment requests if a batch fails.

        Args:
            comments: List of comments to generate embeddings for
            batch_size: Number of texts per API request

        Returns:
            List of CommentEmbedding instances
        """
        embeddings: List[CommentEmbedding] = []

        if not comments:
            return embeddings

        # Skip comments that already have an embedding
        result = await self.db.execute(
            select(CommentEmbedding).where(
                CommentEmbedding.comment_id.in_([c.id for c in comments])
            )
        )
        existing_ids = {e.comment_id for e in result.scalars().all()}
        pending = [c for c in comments if c.id not in existing_ids]

        for i in range(0, len(pending), batch_size):
            batch = pending[i:i + batch_size]
            try:
                response = await self.client.post(
                    "https://api.mistral.ai/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.settings.mistral_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.embedding_model,
                        "input": [comment.text for comment in batch]
                    }
                )
                response.raise_for_status()
                data = sorted(response.json()["data"], key=lambda d: d["index"])

                for comment, item in zip(batch, data):
                    comment_embedding = CommentEmbedding(
                        id=str(uuid.uuid4()),
                        comment_id=comment.id,
                        embedding=item["embedding"],
                        model=self.embedding_model,
                        dimension=self.embedding_dimension
                    )
                    self.db.add(comment_embedding)
                    embeddings.append(comment_embedding)

                await self.db.commit()

            except Exception as e:
                await self.db.rollback()
                logger.error(
                    f"Batched embedding request failed ({len(batch)} comments), "
                    f"falling back to per-comment requests: {e}"
                )
                for comment in batch:
                    embedding = await self.generate_and_store_embedding(comment)
                    if embedding:
                        embeddings.append(embedding)

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
        return await self.generate_and_store_embedding(comment)
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.0
    ) -> List[Tuple[Comment, float]]:
        """
        Perform semantic search for comments similar to the query.

        Embeddings are stored as float arrays (not pgvector), so cosine
        similarity is computed in Python. Fetches stored embeddings, ranks
        them against the query embedding, and returns the top matches.

        Args:
            query: Search query text
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of (comment, similarity_score) tuples, sorted by similarity
        """
        try:
            query_embedding = await self.generate_embedding(query)

            result = await self.db.execute(
                select(Comment, CommentEmbedding.embedding)
                .join(CommentEmbedding, CommentEmbedding.comment_id == Comment.id)
            )
            rows = result.all()

            scored: List[Tuple[Comment, float]] = []
            for comment, embedding in rows:
                if not embedding:
                    continue
                similarity = _cosine_similarity(query_embedding, embedding)
                if similarity >= min_similarity:
                    scored.append((comment, similarity))

            scored.sort(key=lambda pair: pair[1], reverse=True)
            return scored[:limit]

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
        semantic_results = await self.semantic_search(query, limit)
        
        keyword_results = await self._keyword_search(query, limit)
        
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
