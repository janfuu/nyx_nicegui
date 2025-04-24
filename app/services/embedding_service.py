from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
import torch
import base64
import io
import logging

class Embedder:
    def __init__(self):
        # Text embedding model (sentence-level)
        self.text_model = SentenceTransformer('all-mpnet-base-v2')

        # Image embedding model (CLIP)
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

        logging.info("Text and image embedding models initialized")

    def embed_prompt(self, text):
        return self.text_model.encode(text).tolist()

    def embed_image_from_url(self, url):
        image = self._download_image(url)
        if image is None:
            return None, None
        resized, thumbnail_b64 = self._resize_and_encode(image)
        inputs = self.clip_processor(images=resized, return_tensors="pt")
        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
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
