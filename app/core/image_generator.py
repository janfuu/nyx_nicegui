import os
import uuid
import aiohttp
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IImageInference, RunwareAPIError
import asyncio
from runware.types import ILora
import json

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

    async def generate(self, prompts: list[dict | str], negative_prompt: str = None) -> list[str]:
        """Generate one or more images from scene prompts
        
        Args:
            prompts: List of scene prompts, where each prompt can be:
                - A string prompt
                - A dict with 'content'/'prompt' and 'orientation' keys
            negative_prompt: Optional negative prompt to use
        Returns:
            List of image URL strings. Will be empty if generation failed.
        """
        try:
            if not await self._ensure_connection():
                return []

            # Get configuration
            model = self.config.get("image_generation", "model")
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
            
            # Log configuration in a single structured entry
            config_dict = {
                "model": model,
                "number_results": number_results,
                "output_format": output_format,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "scheduler": scheduler,
                "output_type": output_type,
                "include_cost": include_cost,
                "prompt_weighting": prompt_weighting,
                "prompt_pre": prompt_pre,
                "prompt_post": prompt_post,
                "lora_configs": lora_configs
            }
            self.logger.info(f"=== Image Generator Configuration ===\n{json.dumps(config_dict, indent=2)}")
            
            # Use default negative prompt if none provided
            if negative_prompt is None:
                negative_prompt = self.config.get("image_generation", "default_negative_prompt")
            self.logger.info(f"Negative Prompt: {negative_prompt}")

            self.logger.info("=== Input Prompts ===")
            self.logger.info(json.dumps(prompts, indent=2))

            # Create image requests for each prompt
            requests = []
            for prompt in prompts:
                # Extract prompt content and orientation
                if isinstance(prompt, dict):
                    # Accept either 'content' or 'prompt' field
                    prompt_content = prompt.get("prompt", prompt.get("content", ""))
                    orientation = prompt.get("orientation", "portrait")
                else:
                    prompt_content = prompt
                    orientation = "portrait"
                
                # Get size based on orientation
                size_config = self.config.get("image_generation", f"size_{orientation}")
                if not size_config:
                    size_config = self.config.get("image_generation", "size_portrait")  # Fallback to portrait
                width = size_config["width"]
                height = size_config["height"]
                
                # Build the final prompt with prefix and suffix
                final_prompt = f"{prompt_pre} {prompt_content} {prompt_post}".strip()
                
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
                
                self.logger.info(f"=== Request Parameters for {orientation} image ===")
                # Create a copy of request_params for logging, converting ILora to dict
                log_params = request_params.copy()
                if 'lora' in log_params:
                    log_params['lora'] = [{'model': lora.model, 'weight': lora.weight} for lora in log_params['lora']]
                self.logger.info(json.dumps(log_params, indent=2))
                
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
                self.logger.info("=== API Results ===")
                self.logger.info(f"Raw results: {all_results}")
            except asyncio.TimeoutError:
                self.logger.error("Timeout while waiting for image generation")
                return []

            # Process results
            image_urls = []
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1}: {str(result)}")
                    continue
                
                if result and len(result) > 0:
                    image = result[0]
                    # Log the complete image object
                    self.logger.info(f"Image {i+1} complete result: {image}")
                    # Add URL to our list
                    image_urls.append(image.imageURL)

            # Log the complete list with repr to ensure nothing is truncated
            self.logger.info(f"All generated image URLs: {repr(image_urls)}")
            
            # Always return the list of URLs
            return image_urls

        except Exception as e:
            self.logger.error(f"Error in image generation: {str(e)}")
            return []