import os
from minio import Minio
from typing import Optional
import logging
from app.utils.config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

class ImageStore:
    def __init__(self):
        config = Config()
        self.endpoint_url = config.get("minio", "endpoint_url", "http://localhost:9000")
        self.bucket = config.get("minio", "bucket", "nyxmemories")
        
        # Get credentials from environment variables
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        
        if not self.access_key or not self.secret_key:
            raise ValueError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in environment variables")
        
        # Initialize MinIO client
        self.client = Minio(
            self.endpoint_url.replace('http://', '').replace('https://', ''),
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.endpoint_url.startswith('https://')
        )
        
        # Ensure bucket exists
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Ensure the bucket exists, create it if it doesn't."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket {self.bucket}")
        except Exception as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise
    
    def upload_image(self, file_path: str, object_name: str) -> str:
        """
        Upload an image to MinIO.
        
        Args:
            file_path: Path to the local file to upload
            object_name: Name to give the object in MinIO
            
        Returns:
            URL of the uploaded image
        """
        try:
            # Ensure file_path is a string and exists
            if not isinstance(file_path, str):
                raise ValueError(f"file_path must be a string, got {type(file_path)}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Ensure object_name is a string
            if not isinstance(object_name, str):
                raise ValueError(f"object_name must be a string, got {type(object_name)}")
            
            # Convert to absolute path if needed
            file_path = os.path.abspath(file_path)
            
            self.client.fput_object(
                self.bucket,
                object_name,
                file_path
            )
            return f"{self.endpoint_url}/{self.bucket}/{object_name}"
        except Exception as e:
            logger.error(f"Error uploading image to MinIO: {e}")
            raise 

    def store_image_in_qdrant(self, image_path: str, image_id: str, metadata: dict) -> bool:
        """Store an image in Qdrant with its embedding and metadata"""
        try:
            # Get CLIP embedding
            image_vector = self.embedder.embed_image_from_file(image_path)
            if image_vector is None:
                logger.error("Failed to create image embedding")
                return False

            # Upload to MinIO
            minio_url = self.upload_image(image_path, f"{image_id}.jpg")
            if not minio_url:
                logger.error("Failed to upload image to MinIO")
                return False

            # Prepare payload
            payload = {
                "url": minio_url,
                "image_id": image_id,
                "timestamp": datetime.now().isoformat(),
                **metadata
            }

            # Store in Qdrant
            result = self.qdrant.store_image_embedding(
                image_id=image_id,
                vector=image_vector.tolist(),
                payload=payload
            )

            if not result:
                logger.error("Failed to store image in Qdrant")
                return False

            return True

        except Exception as e:
            logger.error(f"Error storing image in Qdrant: {str(e)}")
            return False 