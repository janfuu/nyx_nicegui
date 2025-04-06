import requests
import os
import base64
from app.utils.config import Config

class ImageGenerator:
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.get("stability_api_key")
        self.image_dir = os.path.join('app', 'assets', 'images', 'generated')
        os.makedirs(self.image_dir, exist_ok=True)
    
    def generate(self, prompt):
        """Generate an image from a prompt using Stability AI's API"""
        try:
            response = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": 7,
                    "height": 512,
                    "width": 512,
                    "samples": 1,
                    "steps": 30,
                },
            )
            
            if response.status_code != 200:
                print(f"Error generating image: {response.text}")
                return None
            
            data = response.json()
            
            # Save the image
            for i, image in enumerate(data["artifacts"]):
                image_data = base64.b64decode(image["base64"])
                file_name = f"image_{int(time.time())}_{i}.png"
                file_path = os.path.join(self.image_dir, file_name)
                
                with open(file_path, "wb") as f:
                    f.write(image_data)
                
                # Return the relative path for the UI
                return f"/assets/images/generated/{file_name}"
                
        except Exception as e:
            print(f"Error in image generation: {e}")
            return None