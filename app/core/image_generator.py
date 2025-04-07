import os
import time
import requests
import base64
import asyncio
from runware import Runware, IPromptEnhance, IImageInference
from app.utils.config import Config

class ImageGenerator:
    def __init__(self):
        self.config = Config()
        self.image_dir = os.path.join('app', 'assets', 'images', 'generated')
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Get both API keys
        self.stability_api_key = self.config.get("image_generation", "stability_api_key", "")
        self.runware_api_key = self.config.get("image_generation", "runware_api_key", "")
        self.runware_api_base = self.config.get("image_generation", "runware_api_base", "https://api.runware.ai/v1")
        
        # Configure default image settings
        self.default_model = self.config.get("image_generation", "model", "civitai:101055@128078")
        self.default_height = int(self.config.get("image_generation", "height", 512))
        self.default_width = int(self.config.get("image_generation", "width", 512))
        self.default_num_results = int(self.config.get("image_generation", "number_results", 1))
        
    def generate(self, prompt, negative_prompt=None):
        """
        Generate an image from a prompt using Runware
        This is a synchronous wrapper around the async methods
        """
        # If Runware API key is available, use Runware
        if self.runware_api_key:
            return asyncio.run(self._generate_with_runware(prompt, negative_prompt))
        # Fallback to Stability API
        elif self.stability_api_key:
            return self._generate_with_stability(prompt)
        else:
            print("No image generation API keys available")
            return None
            
    async def _generate_with_runware(self, prompt, negative_prompt=None):
        """Generate image using Runware's API with prompt enhancement"""
        try:
            # Initialize Runware client
            runware = Runware(api_key=self.runware_api_key)
            await runware.connect()
            
            # Step 1: Enhance the prompt if needed
            enhanced_prompt = prompt
            try:
                prompt_enhancer = IPromptEnhance(
                    prompt=prompt,
                    promptVersions=3,
                    promptMaxLength=128,
                )
                
                enhanced_prompts = await runware.promptEnhance(promptEnhancer=prompt_enhancer)
                if enhanced_prompts and len(enhanced_prompts) > 0:
                    # Use the first enhanced prompt
                    enhanced_prompt = enhanced_prompts[0].text
                    print(f"Enhanced prompt: {enhanced_prompt}")
            except Exception as e:
                print(f"Prompt enhancement failed, using original prompt: {e}")
                
            # Step 2: Generate the image
            request_image = IImageInference(
                positivePrompt=enhanced_prompt,
                model=self.default_model,
                numberResults=self.default_num_results,
                negativePrompt=negative_prompt or "",
                height=self.default_height,
                width=self.default_width,
            )
            
            images = await runware.imageInference(requestImage=request_image)
            
            if not images or len(images) == 0:
                print("No images were generated")
                return None
                
            # Process the first image
            image_url = images[0].imageURL
            
            # Download the image
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                print(f"Failed to download image: {image_response.status_code}")
                return None
                
            # Save the image locally
            timestamp = int(time.time())
            file_name = f"image_{timestamp}.png"
            file_path = os.path.join(self.image_dir, file_name)
            
            with open(file_path, "wb") as f:
                f.write(image_response.content)
                
            # Close Runware connection
            await runware.close()
            
            # Return the relative path for the UI
            return f"/assets/images/generated/{file_name}"
            
        except Exception as e:
            print(f"Error in Runware image generation: {e}")
            return None
            
    def _generate_with_stability(self, prompt):
        """Generate image using Stability AI's API (fallback method)"""
        try:
            response = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.stability_api_key}"
                },
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": 7,
                    "height": self.default_height,
                    "width": self.default_width,
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
                timestamp = int(time.time())
                file_name = f"image_{timestamp}_{i}.png"
                file_path = os.path.join(self.image_dir, file_name)
                
                with open(file_path, "wb") as f:
                    f.write(image_data)
                
                # Return the relative path for the UI
                return f"/assets/images/generated/{file_name}"
                
        except Exception as e:
            print(f"Error in Stability AI image generation: {e}")
            return None