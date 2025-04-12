import os
import uuid
import aiohttp
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IImageInference, RunwareAPIError
import asyncio

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

    async def _download_image(self, image_url: str) -> str:
        """Download an image from a URL and save it locally"""
        try:
            # Generate a unique filename
            filename = f"{uuid.uuid4()}.png"
            local_path = os.path.join(self.images_dir, filename)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        with open(local_path, 'wb') as f:
                            f.write(await response.read())
                        self.logger.info(f"Image saved to {local_path}")
                        return local_path
                    else:
                        self.logger.error(f"Failed to download image: HTTP {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error downloading image: {str(e)}")
            return None

    async def generate(self, prompt: str, negative_prompt: str = None) -> str:
        """Generate an image from a prompt"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
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
                lora = self.config.get("image_generation", "lora")
                
                # Ensure connection
                if not await self._ensure_connection():
                    retry_count += 1
                    continue
                
                # Generate image
                image_request = IImageInference(
                    positivePrompt=prompt,
                    negativePrompt=negative_prompt,
                    model=model,
                    width=width,
                    height=height,
                    numberResults=number_results,
                    outputFormat=output_format,
                    steps=steps,
                    CFGScale=cfg_scale,
                    scheduler=scheduler,
                    outputType=output_type,
                    includeCost=include_cost,
                    lora=lora
                )
                
                self.logger.debug(f"Generating image with prompt: {prompt}")
                self.logger.debug(f"Using model: {model}")
                
                result = await self.runware.imageInference(image_request)
                if result and result.images and len(result.images) > 0:
                    image_url = result.images[0].url
                    # Download and save the image locally
                    local_path = await self._download_image(image_url)
                    if local_path:
                        self.logger.info(f"Image generated and saved successfully: {local_path}")
                        return image_url  # Still return the URL for immediate display
                    else:
                        self.logger.error("Failed to save image locally")
                        retry_count += 1
                        continue
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
            lora = self.config.get("image_generation", "lora")

            # Create image requests for each prompt
            requests = []
            for prompt in prompts:
                image_request = IImageInference(
                    positivePrompt=prompt,
                    negativePrompt=negative_prompt,
                    model=model,
                    width=width,
                    height=height,
                    numberResults=number_results,
                    outputFormat=output_format,
                    steps=steps,
                    CFGScale=cfg_scale,
                    scheduler=scheduler,
                    outputType=output_type,
                    includeCost=include_cost,
                    lora=lora
                )
                requests.append(image_request)

            # Execute all image generation requests in parallel
            results = await asyncio.gather(
                *[self.runware.imageInference(req) for req in requests],
                return_exceptions=True
            )

            # Process results
            image_urls = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1}: {str(result)}")
                    continue
                if result and result.images and len(result.images) > 0:
                    image_url = result.images[0].url
                    # Download and save the image locally
                    local_path = await self._download_image(image_url)
                    if local_path:
                        self.logger.info(f"Generated and saved image {i+1}: {local_path}")
                        image_urls.append(image_url)  # Still return the URL for immediate display
                    else:
                        self.logger.error(f"Failed to save image {i+1} locally")

            return image_urls

        except Exception as e:
            self.logger.error(f"Error in parallel generation: {str(e)}", exc_info=True)
            return []