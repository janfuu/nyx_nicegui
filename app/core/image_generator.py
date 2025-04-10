import os
import uuid
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IImageInference, IPromptEnhance, RunwareAPIError
import asyncio

class ImageGenerator:
    def __init__(self):
        self.config = Config()
        self.logger = Logger()
        self.runware = None

    async def _ensure_connection(self) -> bool:
        """Ensure we have a valid connection to Runware"""
        try:
            if not self.runware:
                self.runware = Runware(api_key=self.config.get("image_generation", "runware_api_key"))
                await self.runware.connect()
                return True
            elif not self.runware.is_connected():
                await self.runware.connect()
                return True
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Runware: {str(e)}")
            self.runware = None
            return False

    async def generate(self, prompt: str, negative_prompt: str = None) -> str:
        """Generate an image from a prompt"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Get configuration
                model = self.config.get("image_generation", "model", "civitai:112902@351306")
                width = self.config.get("image_generation", "width", 1024)
                height = self.config.get("image_generation", "height", 1024)
                steps = self.config.get("image_generation", "steps", 30)
                cfg_scale = self.config.get("image_generation", "cfg_scale", 7.0)
                sampler = self.config.get("image_generation", "sampler", "DPM++ 2M Karras")
                
                # Ensure connection
                if not await self._ensure_connection():
                    retry_count += 1
                    continue
                
                # Generate image
                image_request = IImageInference(
                    positivePrompt=prompt,
                    negativePrompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                #    cfgScale=cfg_scale,
                #    sampler=sampler
                )
                
                self.logger.debug(f"Generating image with prompt: {prompt}")
                self.logger.debug(f"Using model: {model}")
                
                result = await self.runware.imageInference(imageInference=image_request)
                if result and result.images and len(result.images) > 0:
                    image_url = result.images[0].url
                    self.logger.info(f"Image generated successfully: {image_url}")
                    return image_url
                else:
                    self.logger.error("No image URL in response")
                    retry_count += 1
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error generating image (attempt {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(1)  # Wait before retrying
                else:
                    return None
        
        return None

    async def generate_parallel(self, prompts: list[str], negative_prompt: str = None) -> list[str]:
        """Generate multiple images in parallel"""
        try:
            if not await self._ensure_connection():
                return []

            # Get configuration
            model = self.config.get("image_generation", "model", "civitai:112902@351306")
            width = self.config.get("image_generation", "width", 1024)
            height = self.config.get("image_generation", "height", 1024)
            steps = self.config.get("image_generation", "steps", 30)
            cfg_scale = self.config.get("image_generation", "cfg_scale", 7.0)
            sampler = self.config.get("image_generation", "sampler", "DPM++ 2M Karras")

            # Create image requests for each prompt
            requests = []
            for prompt in prompts:
                image_request = IImageInference(
                    positivePrompt=prompt,
                    negativePrompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                #    cfgScale=cfg_scale,
                #    sampler=sampler
                )
                requests.append(image_request)

            # Execute all image generation requests in parallel
            results = await asyncio.gather(
                *[self.runware.imageInference(imageInference=req) for req in requests],
                return_exceptions=True
            )

            # Process results
            image_urls = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1}: {str(result)}")
                    continue
                if result and result.images and len(result.images) > 0:
                    image_urls.append(result.images[0].url)
                    self.logger.info(f"Generated image {i+1}: {result.images[0].url}")

            return image_urls

        except Exception as e:
            self.logger.error(f"Error in parallel generation: {str(e)}", exc_info=True)
            return []