# app/services/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from app.utils.config import Config
from app.utils.logger import Logger
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
        """Store an image with its vector embedding and metadata"""
        try:
            self.logger.info(f"Storing image embedding for {image_id}")
            
            # Ensure image_id is a valid UUID string
            if not isinstance(image_id, str):
                self.logger.warning(f"Converting non-string ID {image_id} to string")
                image_id = str(image_id)
                
            # If not a UUID format, generate a new UUID
            try:
                uuid.UUID(image_id)
                self.logger.info(f"Validated image_id {image_id} as valid UUID")
            except ValueError:
                old_id = image_id
                image_id = str(uuid.uuid4())
                self.logger.warning(f"Replaced invalid UUID format {old_id} with {image_id}")
                
            # Validate vector
            if not isinstance(vector, list):
                self.logger.error(f"Vector must be a list, got {type(vector)}")
                return False
                
            if len(vector) != self.vector_size:
                self.logger.error(f"Vector size mismatch: expected {self.vector_size}, got {len(vector)}")
                return False
            
            # Wrap in asyncio-compatible interface if needed
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_store, image_id, vector, payload)
            self.logger.info(f"Successfully stored image {image_id} in Qdrant")
            return True
        except Exception as e:
            self.logger.error(f"Error storing image embedding: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    def _sync_store(self, image_id, vector, payload):
        """Synchronous method to store a point in Qdrant"""
        try:
            self.logger.debug(f"Performing upsert for image {image_id}")
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=image_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            self.logger.debug(f"Upsert completed for image {image_id}")
        except Exception as e:
            self.logger.error(f"Error in _sync_store: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise  # Re-raise to handle in the calling async method

    async def update_rating(self, image_id, rating):
        # Ensure image_id is a valid UUID string
        try:
            uuid.UUID(image_id)
        except ValueError:
            self.logger.error(f"Invalid UUID format for update_rating: {image_id}")
            return False
            
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._sync_update_rating, image_id, rating)
            return True
        except Exception as e:
            # Check if this is a 404 error (point not found)
            if "404" in str(e) or "Not found" in str(e):
                # This is expected when updating a non-existent point
                self.logger.debug(f"Point {image_id} not found for rating update - likely new image")
                return False
            else:
                # Log unexpected errors
                self.logger.error(f"Failed to update rating: {str(e)}")
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
