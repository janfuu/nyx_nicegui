# app/services/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from app.utils.config import Config
from app.utils.logger import Logger
from app.core.state_manager import StateManager
import asyncio
import time
import traceback
import uuid

class QdrantImageStore:
    def __init__(self):
        config = Config()
        self.logger = Logger()
        self.host = config.get("qdrant", "host", "localhost")
        self.port = config.get("qdrant", "port", 6333)
        self.state_manager = StateManager()  # Add state manager
        
        # Get image collection configuration
        collections_config = config.get("qdrant", "collections", {})
        image_config = collections_config.get("images", {})
        
        self.collection_name = image_config.get("name", "nyx_images")
        self.vector_size = image_config.get("vector_size", 512)
        self.distance = image_config.get("distance", "cosine")
        
        self.logger.info(f"Initializing QdrantImageStore with host={self.host}, port={self.port}, collection={self.collection_name}")
        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.logger.info(f"Checking if collection {self.collection_name} exists")
            collections_list = [c.name for c in self.client.get_collections().collections]
            self.logger.info(f"Found collections: {collections_list}")
            
            if self.collection_name not in collections_list:
                # Map string distance to enum
                distance_mapping = {
                    "cosine": Distance.COSINE,
                    "euclidean": Distance.EUCLID,
                    "dot": Distance.DOT
                }
                distance = distance_mapping.get(self.distance.lower(), Distance.COSINE)
                
                self.logger.info(f"Creating collection {self.collection_name} with vector size {self.vector_size}")
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=distance)
                )
                self.logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                self.logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            self.logger.error(f"Error in _ensure_collection: {str(e)}")
            self.logger.error(traceback.format_exc())

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
            self.logger.error(traceback.format_exc())
            return False

    async def store_image_embedding(self, image_id, vector, payload):
        """Store an image embedding in Qdrant with state context"""
        try:
            # Get current state context
            current_mood = self.state_manager.get_current_mood()
            current_appearance = self.state_manager.get_current_appearance()
            current_location = self.state_manager.get_current_location()
            
            # Update payload with current state
            updated_payload = {
                **payload,
                "mood": current_mood,
                "appearance": current_appearance,
                "location": current_location,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            # Store in Qdrant
            point = PointStruct(
                id=image_id,
                vector=vector,
                payload=updated_payload
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            return True
        except Exception as e:
            self.logger.error(f"Error storing image embedding: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    async def update_rating(self, image_id, rating):
        """Update the rating of an image in Qdrant"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_update_rating, image_id, rating)
            return True
        except Exception as e:
            self.logger.error(f"Error updating rating: {str(e)}")
            return False

    def _sync_update_rating(self, image_id, rating):
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={"rating": rating},
                points=[image_id]
            )
        except Exception as e:
            # Let the calling function handle the error classification
            raise

class QdrantMemoryStore:
    def __init__(self):
        config = Config()
        self.logger = Logger()
        self.host = config.get("qdrant", "host", "localhost")
        self.port = config.get("qdrant", "port", 6333)
        self.state_manager = StateManager()  # Add state manager
        
        # Get memory collection configuration
        collections_config = config.get("qdrant", "collections", {})
        memory_config = collections_config.get("memories", {})
        
        self.collection_name = memory_config.get("name", "nyx_memories")
        self.vector_size = memory_config.get("vector_size", 768)
        self.distance = memory_config.get("distance", "cosine")
        
        self.logger.info(f"Initializing QdrantMemoryStore with host={self.host}, port={self.port}, collection={self.collection_name}")
        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.logger.info(f"Checking if collection {self.collection_name} exists")
            collections_list = [c.name for c in self.client.get_collections().collections]
            self.logger.info(f"Found collections: {collections_list}")
            
            if self.collection_name not in collections_list:
                # Map string distance to enum
                distance_mapping = {
                    "cosine": Distance.COSINE,
                    "euclidean": Distance.EUCLID,
                    "dot": Distance.DOT
                }
                distance = distance_mapping.get(self.distance.lower(), Distance.COSINE)
                
                self.logger.info(f"Creating collection {self.collection_name} with vector size {self.vector_size}")
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=distance)
                )
                self.logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                self.logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            self.logger.error(f"Error in _ensure_collection: {str(e)}")
            self.logger.error(traceback.format_exc())

    async def store_memory(self, memory_id, vector, payload):
        """Store a memory in Qdrant with state context"""
        try:
            # Get current state context
            current_mood = self.state_manager.get_current_mood()
            current_appearance = self.state_manager.get_current_appearance()
            current_location = self.state_manager.get_current_location()
            
            # Update payload with current state
            updated_payload = {
                **payload,
                "mood": current_mood,
                "appearance": current_appearance,
                "location": current_location,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            # Store in Qdrant
            point = PointStruct(
                id=memory_id,
                vector=vector,
                payload=updated_payload
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            return True
        except Exception as e:
            self.logger.error(f"Error storing memory: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
