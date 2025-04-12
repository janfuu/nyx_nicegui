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
            
            # Build base request parameters
            request_params = {
                'positivePrompt': prompt,
                'model': model,
                'width': width,
                'height': height,
                'numberResults': number_results,
                'outputFormat': output_format,
                'steps': steps,
                'CFGScale': cfg_scale,
                'scheduler': scheduler,
                'outputType': output_type,
                'includeCost': include_cost
            }
            
            if negative_prompt:
                request_params['negativePrompt'] = negative_prompt
            
            # Create the image request
            image_request = IImageInference(**request_params)
            
            # Ensure connection
            if not await self._ensure_connection():
                return None
            
            self.logger.debug(f"Generating image with prompt: {prompt}")
            
            # Get the images
            images = await self.runware.imageInference(image_request)
            
            if images and len(images) > 0:
                image = images[0]  # Get first image
                image_url = image.imageURL
                # Download and save the image locally
                local_path = await self._download_image(image_url)
                if local_path:
                    self.logger.info(f"Image generated and saved successfully: {local_path}")
                    return image_url
            
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

            # Create image requests for each prompt
            requests = []
            for prompt in prompts:
                request_params = {
                    'positivePrompt': prompt,
                    'model': model,
                    'width': width,
                    'height': height,
                    'numberResults': number_results,
                    'outputFormat': output_format,
                    'steps': steps,
                    'CFGScale': cfg_scale,
                    'scheduler': scheduler,
                    'outputType': output_type,
                    'includeCost': include_cost
                }
                
                if negative_prompt:
                    request_params['negativePrompt'] = negative_prompt
                
                requests.append(IImageInference(**request_params))

            # Execute all requests in parallel
            all_results = await asyncio.gather(
                *[self.runware.imageInference(req) for req in requests],
                return_exceptions=True
            )

            # Process results
            image_urls = []
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1}: {str(result)}")
                    continue
                
                if result and len(result) > 0:
                    image = result[0]
                    image_url = image.imageURL
                    # Download and save the image locally
                    local_path = await self._download_image(image_url)
                    if local_path:
                        image_urls.append(image_url)

            return image_urls

        except Exception as e:
            self.logger.error(f"Error in parallel generation: {str(e)}")
            return []