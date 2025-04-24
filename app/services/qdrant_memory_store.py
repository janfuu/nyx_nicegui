"""
Qdrant Memory Store Service
==========================

This module implements a singleton service for storing and retrieving
semantic memories in Qdrant. It handles:
1. Vector storage of memory embeddings
2. Multi-vector storage (text and mood vectors)
3. State context integration
4. Memory type management (thoughts, secrets, fantasies, moments)
5. Tag-based filtering and search

The service ensures consistent storage of memories with associated
state context (mood, appearance, location) and supports multiple
vector types for enhanced semantic search capabilities.
"""

from qdrant_client import QdrantClient, models
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.models import PointStruct
from app.utils.config import Config
from app.core.state_manager import StateManager
import asyncio
import uuid
import time
from datetime import datetime
import logging
import numpy as np

# Use the root logger with our custom name
logger = logging.getLogger('nyx')

class QdrantMemoryStore:
    """
    Singleton service for managing semantic memories in Qdrant.
    
    This class provides:
    1. Multi-vector memory storage
    2. State context integration
    3. Tag-based memory filtering
    4. Semantic similarity search
    
    The store maintains a single collection for memories with support
    for multiple vector types (text, mood) and rich metadata.
    """
    _instance = None
    _client = None
    _collection_name = "nyx_memories"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantMemoryStore, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the Qdrant client connection."""
        if self._client is None:
            config = Config()
            host = config.get("qdrant", "host", "localhost")
            port = config.get("qdrant", "port", 6333)
            self._client = QdrantClient(host=host, port=port)
            logger.debug("QdrantMemoryStore client initialized")
            
    def _ensure_collection(self):
        """
        Ensure the memory collection exists with correct configuration.
        
        This method:
        1. Checks if collection exists
        2. Creates it if necessary
        3. Configures vector parameters for text and mood
        4. Sets up distance metrics
        """
        try:
            collections_list = [c.name for c in self._client.get_collections().collections]
            
            if self._collection_name not in collections_list:
                # Map string distance to enum
                distance_mapping = {
                    "cosine": Distance.COSINE,
                    "euclidean": Distance.EUCLID,
                    "dot": Distance.DOT
                }
                distance = distance_mapping.get(self.distance_str.lower(), Distance.COSINE)
                
                # Create collection with multi-vector configuration
                self._client.recreate_collection(
                    collection_name=self._collection_name,
                    vectors_config={
                        "text_vector": VectorParams(size=self.vector_size, distance=distance),
                        "mood_vector": VectorParams(size=self.vector_size, distance=distance)
                    }
                )
                logger.info(f"Created multi-vector collection: {self._collection_name}")
            else:
                logger.info(f"Collection {self._collection_name} already exists")
        except Exception as e:
            logger.error(f"Error in _ensure_collection: {str(e)}")
            raise

    async def store_memory(self, text: str, vector: list, memory_type: str = "thought",
                         mood: str = None, mood_vector: list = None, tags: list = None,
                         intensity: float = 0.5):
        """
        Store a memory with its embedding vectors in Qdrant.
        
        Args:
            text: The text content of the memory
            vector: The text embedding vector
            memory_type: Type of memory (thought/secret/fantasy/moment)
            mood: The mood associated with the memory
            mood_vector: The mood embedding vector (optional)
            tags: List of tags for the memory
            intensity: Memory intensity value (0-1)
            
        Returns:
            str: ID of the stored memory
        """
        try:
            memory_id = str(uuid.uuid4())
            
            # Get current state context
            current_state = self.state_manager.get_state()
            
            # Prepare payload with state context
            payload = {
                "text": text,
                "type": memory_type,
                "timestamp": datetime.now().isoformat(),
                "mood": mood or current_state.get("mood"),
                "appearance": current_state.get("appearance"),
                "location": current_state.get("location"),
                "tags": tags or [],
                "intensity": intensity
            }
            
            # Prepare vectors
            vectors = {
                "text_vector": vector
            }
            if mood_vector:
                vectors["mood_vector"] = mood_vector
            
            # Store in Qdrant
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.upsert(
                    collection_name=self._collection_name,
                    points=[PointStruct(
                        id=memory_id,
                        vector=vectors,
                        payload=payload
                    )]
                )
            )
            
            return memory_id
            
        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}")
            return None

    async def search_similar(self, query_vector: list, limit: int = 5,
                           score_threshold: float = 0.7, memory_type: str = None):
        """
        Search for similar memories using text vector similarity.
        
        Args:
            query_vector: Vector to search with
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            memory_type: Optional filter by memory type
            
        Returns:
            list: Similar memories with scores and metadata
        """
        try:
            # Prepare filter if memory type specified
            filter_params = None
            if memory_type:
                filter_params = {
                    "must": [
                        {
                            "key": "type",
                            "match": {"value": memory_type}
                        }
                    ]
                }
            
            # Execute search
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._client.search(
                    collection_name=self._collection_name,
                    query_vector=("text_vector", query_vector),
                    query_filter=filter_params,
                    limit=limit,
                    score_threshold=score_threshold
                )
            )
            return results
            
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return []

    async def search_by_mood(self, mood_vector: list, limit: int = 5,
                           score_threshold: float = 0.7):
        """
        Search for memories with similar mood vectors.
        
        Args:
            mood_vector: Mood vector to search with
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            list: Memories with similar mood vectors
        """
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._client.search(
                    collection_name=self._collection_name,
                    query_vector=("mood_vector", mood_vector),
                    limit=limit,
                    score_threshold=score_threshold
                )
            )
            return results
            
        except Exception as e:
            logger.error(f"Error in mood search: {str(e)}")
            return []

    async def get_memories_by_tags(self, tags: list, limit: int = 10):
        """
        Get memories by tags.
        
        Args:
            tags: List of tags to filter by
            limit: Maximum number of results
            
        Returns:
            list: Memories matching the specified tags
        """
        try:
            filter_params = {
                "must": [
                    {
                        "key": "tags",
                        "match": {"any": tags}
                    }
                ]
            }
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._client.scroll(
                    collection_name=self._collection_name,
                    limit=limit,
                    scroll_filter=filter_params,
                    with_payload=True,
                    with_vectors=False
                )
            )
            
            return results[0]  # Returns just the points, not the next page pointer
            
        except Exception as e:
            logger.error(f"Error in tag search: {str(e)}")
            return []

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
                        size=1536,  # OpenAI embedding dimension
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self._collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {str(e)}")
            return False

    @staticmethod
    def format_memories(memories: list) -> str:
        """
        Format a list of memories into a readable string.
        
        Args:
            memories: List of memory dictionaries
            
        Returns:
            str: Formatted string representation of memories
        """
        return "\n".join(
            f"- ({m['type']}, mood: {m.get('mood', 'neutral')}, "
            f"intensity: {m.get('intensity', 0.5):.2f}, "
            f"tags: {', '.join(m.get('tags', []))}): {m['text']}"
            for m in memories
        ) 