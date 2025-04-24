# app/services/qdrant_memory_store.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.models import PointStruct
from app.utils.config import Config
from app.utils.logger import Logger
import asyncio
import uuid
import time
from datetime import datetime
import logging

class QdrantMemoryStore:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(QdrantMemoryStore, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            config = Config()
            self.logger = Logger()
            self.host = config.get("qdrant", "host", "localhost")
            self.port = config.get("qdrant", "port", 6333)
            
            # Get memory collection configuration
            collections_config = config.get("qdrant", "collections", {})
            memory_config = collections_config.get("memories", {})
            
            self.collection_name = memory_config.get("name", "nyx_memories")
            self.vector_size = memory_config.get("vector_size", 768)  # Restored to 768
            self.distance_str = memory_config.get("distance", "cosine")
            
            self.client = QdrantClient(host=self.host, port=self.port)
            self._ensure_collection()
            self.initialized = True

    def _ensure_collection(self):
        collections_list = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections_list:
            distance_mapping = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "dot": Distance.DOT
            }
            distance = distance_mapping.get(self.distance_str.lower(), Distance.COSINE)
            
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "text_vector": VectorParams(size=self.vector_size, distance=distance),
                    "mood_vector": VectorParams(size=self.vector_size, distance=distance)
                }
            )
            self.logger.info(f"Created multi-vector collection: {self.collection_name}")

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

    async def store_memory(self, text, vector, memory_type="chat", mood=None, mood_vector=None, tags=None):
        """
        Store a memory with its embedding vector in Qdrant
        
        Args:
            text (str): The text of the memory
            vector (list): The embedding vector of the memory
            memory_type (str): Type of memory (chat, reflection, observation, etc.)
            mood (str): The mood associated with the memory
            mood_vector (list): The embedding vector of the mood
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
        
        # Create vectors dictionary
        vectors = {
            "text_vector": vector
        }
        if mood_vector:
            vectors["mood_vector"] = mood_vector
            
        # Run the storage operation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_store, memory_id, vectors, payload)
        
        return memory_id

    def _sync_store(self, memory_id, vectors, payload):
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vectors,
                    payload=payload
                )
            ]
        )

    async def search_similar(self, query_vector, limit=5, score_threshold=0.7):
        """
        Search for similar memories using the text vector
        
        Args:
            query_vector (list): The query vector to search with
            limit (int): Maximum number of results
            score_threshold (float): Minimum similarity score
            
        Returns:
            list: List of similar memories
        """
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.client.search(
                collection_name=self.collection_name,
                query_vector=("text_vector", query_vector),
                limit=limit,
                score_threshold=score_threshold
            )
        )
        return results

    async def search_by_mood(self, mood_vector, limit=5, score_threshold=0.7):
        """
        Search for memories with similar mood
        
        Args:
            mood_vector (list): The mood vector to search with
            limit (int): Maximum number of results
            score_threshold (float): Minimum similarity score
            
        Returns:
            list: List of memories with similar mood
        """
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.client.search(
                collection_name=self.collection_name,
                query_vector=("mood_vector", mood_vector),
                limit=limit,
                score_threshold=score_threshold
            )
        )
        return results

    async def update_memory(self, memory_id, **updates):
        """
        Update an existing memory with additional data
        
        Args:
            memory_id (str): The ID of the memory to update
            **updates: Key-value pairs to update in the memory's payload
        """
        try:
            # Get the current memory
            loop = asyncio.get_event_loop()
            current_memory = await loop.run_in_executor(
                None,
                lambda: self.client.retrieve(
                    collection_name=self.collection_name,
                    ids=[memory_id],
                    with_payload=True,
                    with_vectors=False
                )
            )
            
            if not current_memory:
                self.logger.error(f"Memory {memory_id} not found for update")
                return False
                
            # Update the payload
            current_payload = current_memory[0].payload
            current_payload.update(updates)
            
            # Update the memory
            await loop.run_in_executor(
                None,
                lambda: self.client.set_payload(
                    collection_name=self.collection_name,
                    payload=current_payload,
                    points=[memory_id]
                )
            )
            
            return True
        except Exception as e:
            self.logger.error(f"Error updating memory {memory_id}: {str(e)}")
            return False

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

    @staticmethod
    def format_memories(memories):
        """
        Format a list of memories into a readable string
        
        Args:
            memories (list): List of memory dictionaries with 'type', 'mood', 'text', and 'tags' fields
            
        Returns:
            str: Formatted string of memories
        """
        return "\n".join(
            f"- ({m['type']}, mood: {m.get('mood', 'neutral')}, tags: {', '.join(m.get('tags', []))}): {m['text']}" 
            for m in memories
        ) 