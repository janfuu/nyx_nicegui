import os
import uuid
import aiohttp
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IImageInference, RunwareAPIError
import asyncio
from runware.types import ILora

class ImageGenerator:
    def __init__(self):
        self.config = Config()
        self.logger = Logger()
        self.runware = None
        self.images_dir = os.path.join("data", "images")
        os.makedirs(self.images_dir, exist_ok=True)

    async def _ensure_connection(self) -> bool:
        """Ensure we have a valid connection to Runware"""
        try:
            if not self.runware:
                self.runware = Runware(api_key=self.config.get("image_generation", "runware_api_key"))
                await self.runware.connect()
                return True
            elif not self.runware.connected:
                await self.runware.connect()
                return True
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Runware: {str(e)}")
            self.runware = None
            return False

    async def generate(self, prompt: str | dict, negative_prompt: str = None) -> str:
        """Generate an image from a prompt
        
        Args:
            prompt: Either a string prompt or a dict with 'content' and 'sequence' keys
            negative_prompt: Optional negative prompt to use
        """
        try:
            # Get configuration
            model = self.config.get("image_generation", "model")
            width = self.config.get("image_generation", "width")
            height = self.config.get("image_generation", "height")
            number_results = self.config.get("image_generation", "number_results")
            output_format = self.config.get("image_generation", "output_format")
            steps = self.config.get("image_generation", "steps")
            cfg_scale = self.config.get("image_generation", "cfg_scale")
            scheduler = self.config.get("image_generation", "scheduler")
            output_type = self.config.get("image_generation", "output_type")
            include_cost = self.config.get("image_generation", "include_cost")
            prompt_weighting = self.config.get("image_generation", "prompt_weighting")
            lora_configs = self.config.get("image_generation", "lora")
            prompt_pre = self.config.get("image_generation", "prompt_pre", "")
            prompt_post = self.config.get("image_generation", "prompt_post", "")
            
            # Use default negative prompt if none provided
            if negative_prompt is None:
                negative_prompt = self.config.get("image_generation", "default_negative_prompt")
            
            # Extract prompt content and sequence if it's a dict
            sequence = None
            if isinstance(prompt, dict):
                prompt_content = prompt.get("content", "")
                sequence = prompt.get("sequence")
            else:
                prompt_content = prompt
            
            # Build the final prompt with prefix and suffix
            final_prompt = f"{prompt_pre} {prompt_content} {prompt_post}".strip()
            
            # Build base request parameters
            request_params = {
                'positivePrompt': final_prompt,
                'model': model,
                'width': width,
                'height': height,
                'numberResults': number_results,
                'outputFormat': output_format,
                'steps': steps,
                'CFGScale': cfg_scale,
                'scheduler': scheduler,
                'outputType': output_type,
                'includeCost': include_cost,
                'promptWeighting': prompt_weighting
            }
            
            if negative_prompt:
                request_params['negativePrompt'] = negative_prompt
                
            # Add LoRA configurations if present
            if lora_configs and len(lora_configs) > 0:
                request_params['lora'] = [ILora(model=lora["model"], weight=lora["weight"]) for lora in lora_configs]
            
            # Create the image request
            image_request = IImageInference(**request_params)
            
            # Ensure connection
            if not await self._ensure_connection():
                return None
            
            self.logger.debug(f"Generating image with prompt: {final_prompt}")
            
            # Get the images with timeout
            try:
                images = await asyncio.wait_for(
                    self.runware.imageInference(image_request),
                    timeout=60  # 60 second timeout
                )
            except asyncio.TimeoutError:
                self.logger.error("Timeout while waiting for image generation")
                return None
            
            if images and len(images) > 0:
                image = images[0]  # Get first image
                return image.imageURL
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating image: {str(e)}")
            return None

    async def generate_parallel(self, prompts: list[str], negative_prompt: str = None) -> list[str]:
        """Generate multiple images in parallel"""
        try:
            if not await self._ensure_connection():
                return []

            # Get configuration
            model = self.config.get("image_generation", "model")
            width = self.config.get("image_generation", "width")
            height = self.config.get("image_generation", "height")
            number_results = self.config.get("image_generation", "number_results")
            output_format = self.config.get("image_generation", "output_format")
            steps = self.config.get("image_generation", "steps")
            cfg_scale = self.config.get("image_generation", "cfg_scale")
            scheduler = self.config.get("image_generation", "scheduler")
            output_type = self.config.get("image_generation", "output_type")
            include_cost = self.config.get("image_generation", "include_cost")
            prompt_weighting = self.config.get("image_generation", "prompt_weighting")
            lora_configs = self.config.get("image_generation", "lora")
            prompt_pre = self.config.get("image_generation", "prompt_pre", "")
            prompt_post = self.config.get("image_generation", "prompt_post", "")
            
            # Use default negative prompt if none provided
            if negative_prompt is None:
                negative_prompt = self.config.get("image_generation", "default_negative_prompt")

            # Create image requests for each prompt
            requests = []
            for prompt in prompts:
                # Build the final prompt with prefix and suffix
                final_prompt = f"{prompt_pre} {prompt} {prompt_post}".strip()
                
                request_params = {
                    'positivePrompt': final_prompt,
                    'model': model,
                    'width': width,
                    'height': height,
                    'numberResults': number_results,
                    'outputFormat': output_format,
                    'steps': steps,
                    'CFGScale': cfg_scale,
                    'scheduler': scheduler,
                    'outputType': output_type,
                    'includeCost': include_cost,
                    'promptWeighting': prompt_weighting
                }
                
                if negative_prompt:
                    request_params['negativePrompt'] = negative_prompt
                
                # Add LoRA configurations if present
                if lora_configs and len(lora_configs) > 0:
                    request_params['lora'] = [ILora(model=lora["model"], weight=lora["weight"]) for lora in lora_configs]
                
                requests.append(IImageInference(**request_params))

            # Execute all requests in parallel with timeout
            try:
                all_results = await asyncio.wait_for(
                    asyncio.gather(
                        *[self.runware.imageInference(req) for req in requests],
                        return_exceptions=True
                    ),
                    timeout=120  # 120 second timeout for all images
                )
            except asyncio.TimeoutError:
                self.logger.error("Timeout while waiting for parallel image generation")
                return []

            # Process results
            image_urls = []
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1}: {str(result)}")
                    continue
                
                if result and len(result) > 0:
                    image = result[0]
                    image_urls.append(image.imageURL)

            return image_urls

        except Exception as e:
            self.logger.error(f"Error in parallel generation: {str(e)}")
            return []