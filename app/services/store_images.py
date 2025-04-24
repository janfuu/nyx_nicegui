"""
Image Storage Coordinator Service
===============================

This module implements a coordinator service that manages image storage
across multiple backends (MinIO and Qdrant). It handles:
1. Primary file storage in MinIO
2. Metadata and embedding storage in Qdrant via QdrantImageStore
3. URL management and tracking
4. Coordinated storage operations

The service ensures consistent storage and synchronization between
MinIO (for raw files) and Qdrant (for searchable embeddings).
"""

import os
from minio import Minio
from typing import Optional, Dict, Any
import logging
from app.utils.config import Config
from app.services.qdrant_image_store import QdrantImageStore
from app.services.embedder import get_embedder
from datetime import datetime

logger = logging.getLogger(__name__)

class StoreImages:
    """
    Coordinator service for managing image storage across systems.
    
    This class coordinates:
    1. Primary file storage in MinIO
    2. Vector embeddings in Qdrant
    3. URL and metadata management
    4. Storage synchronization
    
    The service ensures that images are consistently stored and
    linked between MinIO (raw files) and Qdrant (searchable embeddings).
    """
    
    def __init__(self):
        """
        Initialize the image storage coordinator.
        
        Sets up:
        1. MinIO client and bucket
        2. Qdrant store connection
        3. Embedder service
        4. Storage configuration
        
        Raises:
            ValueError: If MinIO credentials are not properly configured
        """
        config = Config()
        
        # MinIO configuration
        self.endpoint_url = config.get("minio", "endpoint_url", "http://localhost:9000")
        self.bucket = config.get("minio", "bucket", "nyxmemories")
        
        # Get credentials from environment variables
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        
        if not self.access_key or not self.secret_key:
            raise ValueError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in environment variables")
        
        # Initialize services
        self.client = Minio(
            self.endpoint_url.replace('http://', '').replace('https://', ''),
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.endpoint_url.startswith('https://')
        )
        self.qdrant = QdrantImageStore()
        self.embedder = get_embedder()
        
        # Ensure bucket exists
        self._ensure_bucket()
    
    def _ensure_bucket(self) -> None:
        """
        Ensure the MinIO bucket exists, create it if it doesn't.
        
        This method:
        1. Checks if the configured bucket exists
        2. Creates it if necessary
        3. Logs the operation result
        
        Raises:
            Exception: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket {self.bucket}")
        except Exception as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise
    
    def upload_image(self, file_path: str, object_name: str) -> Optional[str]:
        """
        Upload an image to MinIO primary storage.
        
        This method:
        1. Validates input parameters
        2. Uploads the file to MinIO
        3. Generates and returns the access URL
        
        Args:
            file_path: Path to the local file to upload
            object_name: Name to give the object in MinIO
            
        Returns:
            str: URL of the uploaded image, or None if upload fails
            
        Raises:
            ValueError: If input parameters are invalid
            FileNotFoundError: If the image file doesn't exist
        """
        try:
            # Validate inputs
            if not isinstance(file_path, str):
                raise ValueError(f"file_path must be a string, got {type(file_path)}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not isinstance(object_name, str):
                raise ValueError(f"object_name must be a string, got {type(object_name)}")
            
            # Convert to absolute path
            file_path = os.path.abspath(file_path)
            
            # Upload to MinIO
            self.client.fput_object(
                self.bucket,
                object_name,
                file_path
            )
            
            # Return the access URL
            return f"{self.endpoint_url}/{self.bucket}/{object_name}"
            
        except Exception as e:
            logger.error(f"Error uploading image to MinIO: {e}")
            return None

    async def store_image_in_qdrant(self, image_path: str, image_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Coordinate image storage across MinIO and Qdrant.
        
        This method:
        1. Generates image embedding
        2. Stores raw file in MinIO
        3. Stores embedding and metadata in Qdrant
        4. Ensures consistency between storages
        
        Args:
            image_path: Path to the image file
            image_id: Unique identifier for the image
            metadata: Additional metadata to store with the image
            
        Returns:
            bool: True if storage successful in both systems, False otherwise
        """
        try:
            # Get CLIP embedding
            image_vector = self.embedder.embed_image_from_file(image_path)
            if image_vector is None:
                logger.error("Failed to create image embedding")
                return False

            # Upload to MinIO primary storage
            minio_url = self.upload_image(image_path, f"{image_id}.jpg")
            if not minio_url:
                logger.error("Failed to upload image to MinIO")
                return False

            # Prepare payload with URL and metadata
            payload = {
                "url": minio_url,
                "image_id": image_id,
                "timestamp": datetime.now().isoformat(),
                **metadata
            }

            # Store in Qdrant with state context
            success = await self.qdrant.store_image(
                image_id=image_id,
                vector=image_vector.tolist(),
                metadata=payload
            )

            if not success:
                logger.error("Failed to store image in Qdrant")
                return False

            logger.info(f"Successfully stored image {image_id} in both MinIO and Qdrant")
            return True

        except Exception as e:
            logger.error(f"Error storing image in Qdrant: {str(e)}")
            return False 