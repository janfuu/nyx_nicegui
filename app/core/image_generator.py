import os
import httpx
import json
import uuid
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IPromptEnhance

class ImageGenerator:
    def __init__(self):
        self.config = Config()
        self.logger = Logger()

    async def enhance_prompt(self, prompt):
        """Enhance a prompt using Runware's prompt enhancement API"""
        try:
            api_key = self.config.get("image_generation", "runware_api_key", "")
            if not api_key:
                self.logger.error("No API key found for Runware prompt enhancement")
                return prompt
                
            runware = Runware(api_key=api_key)
            await runware.connect()
            
            prompt_versions = self.config.get("image_generation", "prompt_versions", 1)
            max_length = self.config.get("image_generation", "prompt_max_length", 150)
            
            prompt_enhancer = IPromptEnhance(
                prompt=prompt,
                promptVersions=prompt_versions,
                promptMaxLength=max_length,
            )
            
            enhanced_prompts = await runware.promptEnhance(promptEnhancer=prompt_enhancer)
            if enhanced_prompts and len(enhanced_prompts) > 0:
                # Return the first enhanced prompt
                self.logger.info(f"Enhanced prompt: {enhanced_prompts[0].text}")
                return enhanced_prompts[0].text
            
            return prompt
        except Exception as e:
            self.logger.error(f"Error enhancing prompt: {str(e)}")
            return prompt

    async def generate(self, prompt, negative_prompt=""):
        """Generate an image using the configured provider"""
        try:
            if self.config.get("image_generation", "use_prompt_enhancement", True):
                # Here you could add prompt enhancement logic
                enhanced_prompt = await self.enhance_prompt(prompt)
            else:
                enhanced_prompt = prompt
                
            return self._generate_with_runware(enhanced_prompt, negative_prompt)
                
        except Exception as e:
            self.logger.error(f"Error in generate: {str(e)}", exc_info=True)
            return None
            
    def _generate_with_runware(self, prompt, negative_prompt=""):
        """Generate an image using the Runware API"""
        api_base = self.config.get("image_generation", "runware_api_base", "https://api.runware.ai/v1")
        api_key = self.config.get("image_generation", "runware_api_key", "")
        
        if not api_key:
            self.logger.error("No API key found for Runware. Set RUNWARE_API_KEY in config or env.")
            return None
        
        model = self.config.get("image_generation", "model", "civitai:133005@782002")
        width = self.config.get("image_generation", "width", 512)
        height = self.config.get("image_generation", "height", 512)
        n_results = self.config.get("image_generation", "number_results", 1)
        
        # Prepare the request
        url = f"{api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Generate a unique task UUID for the request
        task_uuid = str(uuid.uuid4())
        
        payload = {
            "model": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "n": n_results,
            "taskType": "imageInference",
            "taskUUID": task_uuid
        }
        
        self.logger.debug(f"Generating image with prompt: {prompt}")
        self.logger.debug(f"Using model: {model}, taskUUID: {task_uuid}")
        
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            
            result = response.json()
            
            if "data" in result and len(result["data"]) > 0:
                image_url = result["data"][0]["url"]
                self.logger.info(f"Image generated successfully: {image_url}")
                return image_url
            else:
                self.logger.error(f"No image data in response: {result}")
                return None
                
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error during image generation: {e.response.status_code}")
            self.logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"Error generating image: {str(e)}")
            return None