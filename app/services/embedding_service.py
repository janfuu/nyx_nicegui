# app/services/embedding_service.py
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
import torch
import base64
import io
import logging

class Embedder:
    def __init__(self):
        # Initialize with default settings, no explicit use_fast parameter
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        logging.info("CLIP model and processor initialized")

    def embed_prompt(self, text):
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        return text_features[0].cpu().numpy()

    def embed_image_from_url(self, url):
        image = self._download_image(url)
        if image is None:
            return None, None
        resized, thumbnail_b64 = self._resize_and_encode(image)
        inputs = self.processor(images=resized, return_tensors="pt")
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
        return image_features[0].cpu().numpy(), thumbnail_b64

    def _download_image(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            print(f"Failed to download image: {e}")
            return None

    def _resize_and_encode(self, image, size=200):
        image.thumbnail((size, size))
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return image, b64_str
