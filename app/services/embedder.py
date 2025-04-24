"""
Embedder Service
===============

This module provides a singleton service for generating embeddings for both
text and images. It handles:
1. Text embeddings using SentenceTransformer
2. Image embeddings using CLIP
3. Image preprocessing and resizing
4. URL and file-based image loading

The service ensures consistent embedding generation across the application
by maintaining a single instance of the embedding models.
"""

from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
import torch
import base64
import io
import logging
from typing import Optional, Tuple, List, Union

class Embedder:
    """
    Singleton service for generating text and image embeddings.
    
    This class provides:
    1. Text embeddings for semantic search
    2. Image embeddings for visual search
    3. Image preprocessing utilities
    4. Consistent embedding dimensions
    
    The service maintains single instances of the embedding models
    to ensure efficient resource usage.
    """
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern - only one embedder instance exists."""
        if cls._instance is None:
            cls._instance = super(Embedder, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Initialize the embedder service if not already initialized.
        
        Sets up:
        1. Text embedding model (SentenceTransformer)
        2. Image embedding model (CLIP)
        3. Image processor
        """
        if self._initialized:
            return
            
        # Text embedding model (sentence-level)
        self.text_model = SentenceTransformer('all-mpnet-base-v2')

        # Image embedding model (CLIP)
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

        logging.info("Text and image embedding models initialized")
        self._initialized = True

    def embed_prompt(self, text: str) -> List[float]:
        """
        Generate embeddings for text input.
        
        Args:
            text: The text to embed
            
        Returns:
            List of embedding values
        """
        return self.text_model.encode(text).tolist()

    def embed_image_from_url(self, url: str) -> Tuple[Optional[List[float]], Optional[str]]:
        """
        Generate embeddings for an image from URL.
        
        Args:
            url: URL of the image to embed
            
        Returns:
            Tuple of (embedding vector, base64 thumbnail) or (None, None) if failed
        """
        image = self._download_image(url)
        if image is None:
            return None, None
            
        resized, thumbnail_b64 = self._resize_and_encode(image)
        inputs = self.clip_processor(images=resized, return_tensors="pt")
        
        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
            
        return image_features[0].cpu().numpy(), thumbnail_b64

    def embed_image_from_file(self, file_path: str) -> Optional[List[float]]:
        """
        Generate embeddings for an image from local file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Embedding vector or None if failed
        """
        try:
            image = Image.open(file_path).convert("RGB")
            inputs = self.clip_processor(images=image, return_tensors="pt")
            
            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
                
            return image_features[0].cpu().numpy()
            
        except Exception as e:
            logging.error(f"Failed to embed image from file: {e}")
            return None

    def _download_image(self, url: str) -> Optional[Image.Image]:
        """
        Download an image from URL.
        
        Args:
            url: URL of the image to download
            
        Returns:
            PIL Image object or None if download failed
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            logging.error(f"Failed to download image: {e}")
            return None

    def _resize_and_encode(self, image: Image.Image, size: int = 200) -> Tuple[Image.Image, str]:
        """
        Resize an image and encode it to base64.
        
        Args:
            image: PIL Image to process
            size: Target size for thumbnail
            
        Returns:
            Tuple of (resized image, base64 encoded thumbnail)
        """
        image.thumbnail((size, size))
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return image, b64_str

# Global embedder instance
_embedder_instance = None

def get_embedder() -> Embedder:
    """
    Get the global embedder instance.
    
    This function ensures a single embedder instance is used
    across the application, initializing it if needed.
    
    Returns:
        The global Embedder instance
    """
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance 