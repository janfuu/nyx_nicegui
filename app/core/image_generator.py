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

    async def _ensure_connection(self):
        """Ensure we have a connection to Runware"""
        if not self.runware:
            api_key = self.config.get("image_generation", "runware_api_key", "")
            if not api_key:
                self.logger.error("No API key found for Runware")
                return False
            self.runware = Runware(api_key=api_key)
            await self.runware.connect()
        return True

    async def enhance_prompt(self, prompt):
        """Enhance a prompt using Runware's prompt enhancement API"""
        try:
            if not await self._ensure_connection():
                return prompt
                
            prompt_versions = self.config.get("image_generation", "prompt_versions", 1)
            max_length = self.config.get("image_generation", "prompt_max_length", 150)
            
            prompt_enhancer = IPromptEnhance(
                prompt=prompt,
                promptVersions=prompt_versions,
                promptMaxLength=max_length
            )
            
            enhanced_prompts = await self.runware.promptEnhance(promptEnhancer=prompt_enhancer)
            if enhanced_prompts and len(enhanced_prompts) > 0:
                # Return the first enhanced prompt
                self.logger.info(f"Enhanced prompt: {enhanced_prompts[0].text}")
                return enhanced_prompts[0].text
            
            return prompt
        except RunwareAPIError as e:
            self.logger.error(f"Runware API error in prompt enhancement: {e}")
            self.logger.error(f"Error code: {e.code}")
            return prompt
        except Exception as e:
            self.logger.error(f"Error enhancing prompt: {str(e)}")
            return prompt

    async def generate(self, prompt, negative_prompt=""):
        """Generate an image using the configured provider"""
        try:
            if not await self._ensure_connection():
                return None

            if self.config.get("image_generation", "use_prompt_enhancement", True):
                enhanced_prompt = await self.enhance_prompt(prompt)
            else:
                enhanced_prompt = prompt
                
            model = self.config.get("image_generation", "model", "civitai:133005@782002")
            width = self.config.get("image_generation", "width", 512)
            height = self.config.get("image_generation", "height", 512)
            n_results = self.config.get("image_generation", "number_results", 1)
            
            request_image = IImageInference(
                positivePrompt=enhanced_prompt,
                negativePrompt=negative_prompt,
                model=model,
                numberResults=n_results,
                height=height,
                width=width,
                outputType="URL"
            )
            
            self.logger.debug(f"Generating image with prompt: {enhanced_prompt}")
            self.logger.debug(f"Using model: {model}")
            
            images = await self.runware.imageInference(requestImage=request_image)
            
            if images and len(images) > 0:
                image_url = images[0].imageURL
                self.logger.info(f"Image generated successfully: {image_url}")
                return image_url
            else:
                self.logger.error("No images generated")
                return None
                
        except RunwareAPIError as e:
            self.logger.error(f"Runware API error in image generation: {e}")
            self.logger.error(f"Error code: {e.code}")
            return None
        except Exception as e:
            self.logger.error(f"Error in generate: {str(e)}", exc_info=True)
            return None

    async def generate_parallel(self, prompts, negative_prompt=""):
        """Generate multiple images in parallel"""
        try:
            if not await self._ensure_connection():
                return []

            # First enhance all prompts in parallel
            enhanced_prompts = []
            if self.config.get("image_generation", "use_prompt_enhancement", True):
                # Create prompt enhancement tasks
                enhance_tasks = [self.enhance_prompt(prompt) for prompt in prompts]
                # Execute all enhancements in parallel
                enhanced_prompts = await asyncio.gather(*enhance_tasks)
            else:
                enhanced_prompts = prompts

            # Create image requests for each enhanced prompt
            requests = []
            for enhanced_prompt in enhanced_prompts:
                model = self.config.get("image_generation", "model", "civitai:133005@782002")
                width = self.config.get("image_generation", "width", 512)
                height = self.config.get("image_generation", "height", 512)
                
                request_image = IImageInference(
                    positivePrompt=enhanced_prompt,
                    negativePrompt=negative_prompt,
                    model=model,
                    numberResults=1,
                    height=height,
                    width=width,
                    outputType="URL"
                )
                requests.append(request_image)

            # Execute all image generation requests in parallel
            results = await asyncio.gather(
                *[self.runware.imageInference(requestImage=req) for req in requests],
                return_exceptions=True
            )

            # Process results
            image_urls = []
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Error in parallel generation: {str(result)}")
                    continue
                if result and len(result) > 0:
                    image_urls.append(result[0].imageURL)

            return image_urls

        except Exception as e:
            self.logger.error(f"Error in parallel generation: {str(e)}", exc_info=True)
            return []