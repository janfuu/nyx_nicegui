# app/services/qdrant_memory_store.py
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from app.utils.config import Config
from app.utils.logger import Logger
import asyncio
import uuid
import time
from datetime import datetime

class QdrantMemoryStore:
    def __init__(self):
        config = Config()
        self.logger = Logger()
        self.host = config.get("qdrant", "host", "localhost")
        self.port = config.get("qdrant", "port", 6333)
        
        # Get memory collection configuration
        collections_config = config.get("qdrant", "collections", {})
        memory_config = collections_config.get("memories", {})
        
        self.collection_name = memory_config.get("name", "nyx_memories")
        self.vector_size = memory_config.get("vector_size", 1536)
        self.distance_str = memory_config.get("distance", "cosine")
        
        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()

    def _ensure_collection(self):
        collections_list = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections_list:
            # Map string distance to enum
            distance_mapping = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "dot": Distance.DOT
            }
            distance = distance_mapping.get(self.distance_str.lower(), Distance.COSINE)
            
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=distance)
            )
            self.logger.info(f"Created Qdrant collection: {self.collection_name}")

    async def check_health(self):
        """
        Check if Qdrant server is running and responding
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            # Use telemetry or collection list as health check since there's no dedicated health() method
            loop = asyncio.get_event_loop()
            collections = await loop.run_in_executor(None, lambda: self.client.get_collections())
            
            is_healthy = collections is not None and hasattr(collections, 'collections')
            
            if is_healthy:
                self.logger.info(f"Qdrant connection is healthy at {self.host}:{self.port}")
            else:
                self.logger.error(f"Qdrant health check failed")
                
            return is_healthy
        except Exception as e:
            self.logger.error(f"Qdrant connection error: {str(e)}")
            return False

    async def store_memory(self, text, vector, memory_type="chat", mood=None, tags=None):
        """
        Store a memory with its embedding vector in Qdrant
        
        Args:
            text (str): The text of the memory
            vector (list): The embedding vector of the memory
            memory_type (str): Type of memory (chat, reflection, observation, etc.)
            mood (str): The mood associated with the memory
            tags (list): List of tags for the memory
        """
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        payload = {
            "text": text,
            "type": memory_type,
            "timestamp": timestamp,
            "mood": mood,
            "tags": tags or []
        }
        
        # Run the storage operation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_store, memory_id, vector, payload)
        
        return memory_id

    def _sync_store(self, memory_id, vector, payload):
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    async def search_similar(self, query_vector, limit=5, score_threshold=0.7):
        """
        Search for memories similar to the query vector
        
        Args:
            query_vector (list): The query embedding vector
            limit (int): Maximum number of results to return
            score_threshold (float): Minimum similarity score (0-1)
            
        Returns:
            list: List of memories with similarity scores
        """
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(
            None, 
            lambda: self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )
        )
        
        return search_results

    async def get_memories_by_tags(self, tags, limit=10):
        """
        Get memories by tags
        
        Args:
            tags (list): List of tags to filter by
            limit (int): Maximum number of results
            
        Returns:
            list: List of memories matching the tags
        """
        loop = asyncio.get_event_loop()
        
        filter_params = {
            "must": [
                {
                    "key": "tags",
                    "match": {
                        "any": tags
                    }
                }
            ]
        }
        
        search_results = await loop.run_in_executor(
            None,
            lambda: self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                scroll_filter=filter_params,
                with_payload=True,
                with_vectors=False
            )
        )
        
        return search_results[0]  # Returns just the points, not the next page pointer 