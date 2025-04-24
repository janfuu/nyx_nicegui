"""
Qdrant Image Store Service
=========================

This service manages image storage and retrieval in Qdrant, including:
- Storing image embeddings and metadata
- Searching images by similarity
- Managing image collections

The service is implemented as a singleton to ensure consistent
state across the application.
"""

from qdrant_client import QdrantClient, models
from app.utils.config import Config
import numpy as np
import logging
import asyncio
import time

# Use the root logger with our custom name
logger = logging.getLogger('nyx')

class QdrantImageStore:
    _instance = None
    _client = None
    _collection_name = "nyx_images"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantImageStore, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
        
    def _initialize(self):
        """Initialize the Qdrant client connection."""
        if self._client is None:
            config = Config()
            host = config.get("qdrant", "host", "localhost")
            port = config.get("qdrant", "port", 6333)
            self._client = QdrantClient(host=host, port=port)
            logger.debug("QdrantImageStore client initialized")
            
    async def check_health(self) -> bool:
        """
        Check if the Qdrant service and collection are healthy.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            collections = self._client.get_collections()
            has_collection = any(c.name == self._collection_name for c in collections.collections)
            
            if not has_collection:
                # Create collection if it doesn't exist
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=models.VectorParams(
                        size=512,  # CLIP embedding dimension
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self._collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {str(e)}")
            return False
            
    async def store_image(self, image_id: str, vector: list, metadata: dict):
        """
        Store an image embedding with metadata and state context.
        
        Args:
            image_id: Unique identifier for the image
            vector: Image embedding vector
            metadata: Image metadata (prompt, model, etc.)
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            # Get current state context
            current_state = self.state_manager.get_state()
            
            # Combine metadata with state context
            payload = {
                **metadata,
                "mood": current_state.get("mood"),
                "appearance": current_state.get("appearance"),
                "location": current_state.get("location"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            # Create point with vector and payload
            point = models.PointStruct(
                id=image_id,
                vector=vector,
                payload=payload
            )
            
            # Store in Qdrant
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.upsert(
                    collection_name=self._collection_name,
                    points=[point]
                )
            )
            return True
            
        except Exception as e:
            logger.error(f"Error storing image {image_id}: {str(e)}")
            return False

    async def search_similar(self, query_vector: list, limit: int = 5, score_threshold: float = 0.7):
        """
        Search for similar images using vector similarity.
        
        Args:
            query_vector: Vector to search with
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            list: Similar images with scores and metadata
        """
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._client.search(
                    collection_name=self._collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    score_threshold=score_threshold
                )
            )
            return results
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return [] 