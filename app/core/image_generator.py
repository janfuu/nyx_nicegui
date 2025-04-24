"""
Image Generation Service
=======================

This module provides the core interface for generating images using the Runware API.
It handles:
1. Parallel image generation with proper connection management
2. Configuration-based image generation parameters
3. Image downloading and storage in MinIO
4. Comprehensive error handling and logging

The service is designed to handle multiple image generation requests concurrently
while maintaining proper error handling and resource management. It uses Runware's
official Python SDK for image generation and integrates with MinIO for storage.

Key Features:
- Parallel processing of multiple image requests
- Automatic connection management and retry logic
- Configurable image generation parameters
- Secure image storage in MinIO
- Detailed logging and error tracking
"""

import os
import uuid
import aiohttp
from app.utils.config import Config
from app.utils.logger import Logger
from runware import Runware, IImageInference, RunwareAPIError
import asyncio
from runware.types import ILora
import json
import time
from typing import List, Optional, Dict

class ImageGenerator:
    """
    Core service for generating images using Runware's API.
    
    This class manages the entire image generation pipeline:
    1. Connection management with Runware
    2. Parallel processing of image requests
    3. Image downloading and storage
    4. Error handling and logging
    
    The implementation uses parallel processing to handle multiple image requests
    efficiently while maintaining proper error handling and resource management.
    Each request gets its own Runware connection to prevent concurrency issues.
    
    WARNING: The parallel processing implementation is critical and should not be
    modified as it ensures proper handling of concurrent image generation requests.
    """
    def __init__(self):
        """
        Initialize the image generator service.
        
        Sets up:
        - Configuration management
        - Logging system
        - Local image storage directory
        - Runware connection (lazy initialization)
        """
        self.config = Config()
        self.logger = Logger()
        self.runware = None
        self.images_dir = os.path.join("data", "images")
        os.makedirs(self.images_dir, exist_ok=True)

    async def _ensure_connection(self) -> bool:
        """
        Ensure a valid connection to Runware's API.
        
        This method handles:
        - Initial connection establishment
        - Connection recovery if disconnected
        - Error handling and logging
        
        Returns:
            bool: True if connection is valid, False otherwise
        """
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

    async def _safe_request_image(self, request_id: str, request_image: IImageInference):
        """
        Safely execute a single image generation request.
        
        This method:
        - Creates a new Runware connection for each request
        - Handles API errors gracefully
        - Provides detailed error logging
        - Ensures proper resource cleanup
        
        Args:
            request_id: Unique identifier for the request
            request_image: Image generation parameters
            
        Returns:
            The generated image result or None if generation failed
        """
        try:
            # Create a new Runware connection for this request
            runware = Runware(api_key=self.config.get("image_generation", "runware_api_key"))
            await runware.connect()
            
            try:
                result = await runware.imageInference(requestImage=request_image)
                return result
            except RunwareAPIError as e:
                self.logger.error(f"API Error for request {request_id}: {e}")
                self.logger.error(f"Error Code: {e.code if hasattr(e, 'code') else 'unknown'}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected Error for request {request_id}: {str(e)}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating Runware connection for request {request_id}: {str(e)}")
            return None

    async def generate(self, prompts: list[dict | str], negative_prompt: str = None) -> list[dict]:
        """
        Generate one or more images from scene prompts.
        
        This is the main entry point for image generation. It:
        1. Validates and processes input prompts
        2. Applies configuration settings
        3. Executes parallel image generation
        4. Handles image downloading and storage
        5. Manages errors and timeouts
        
        Args:
            prompts: List of scene prompts, where each prompt can be:
                - A string prompt
                - A dict with 'prompt', 'original_text', 'orientation', and 'frame' keys
            negative_prompt: Optional negative prompt to use
            
        Returns:
            List of dicts containing image URLs and file paths. Will be empty if generation failed.
            Each dict has 'url' and 'file_path' keys.
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
            request_ids = []
            
            for i, prompt in enumerate(prompts):
                # Generate a unique ID for this request
                request_id = f"req_{int(time.time())}_{i}"
                request_ids.append(request_id)
                
                # Extract prompt content and orientation
                if isinstance(prompt, dict):
                    # Use all fields from the parsed scene
                    prompt_content = prompt.get("prompt", "")
                    original_text = prompt.get("original_text", "")
                    orientation = prompt.get("orientation", "portrait")
                    frame = prompt.get("frame", i + 1)
                    
                    # Log the full parsed scene
                    self.logger.info(f"=== Parsed Scene {frame} ===")
                    self.logger.info(f"Original Text: {original_text}")
                    self.logger.info(f"Parsed Prompt: {prompt_content}")
                    self.logger.info(f"Orientation: {orientation}")
                else:
                    prompt_content = prompt
                    original_text = prompt
                    orientation = "portrait"
                    frame = i + 1
                
                # Get size based on orientation
                size_config = self.config.get("image_generation", f"size_{orientation}")
                if not size_config:
                    size_config = self.config.get("image_generation", "size_portrait")  # Fallback to portrait
                width = size_config["width"]
                height = size_config["height"]
                
                # Build the final prompt with prefix and suffix
                if not prompt_content:
                    self.logger.error(f"Empty prompt content for request {request_id}")
                    continue
                    
                final_prompt = f"{prompt_pre}{prompt_content}{prompt_post}".strip()
                self.logger.info(f"Final prompt for request {request_id}: {final_prompt}")
                
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
                
                self.logger.info(f"=== Request Parameters for {orientation} image (ID: {request_id}) ===")
                # Create a copy of request_params for logging, converting ILora to dict
                log_params = request_params.copy()
                if 'lora' in log_params:
                    log_params['lora'] = [{'model': lora.model, 'weight': lora.weight} for lora in log_params['lora']]
                self.logger.info(json.dumps(log_params, indent=2))
                
                requests.append(IImageInference(**request_params))

            # Execute all requests in parallel with timeout
            try:
                # Scale timeout based on number of requests (at least 30 seconds per image)
                timeout_seconds = max(120, 30 * len(requests))  # At least 120 seconds, 30 seconds per image
                self.logger.info(f"Using timeout of {timeout_seconds} seconds for {len(requests)} images")
                
                # Create safe request tasks
                tasks = [self._safe_request_image(request_id, request) 
                         for request_id, request in zip(request_ids, requests)]
                
                all_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout_seconds
                )
                
                self.logger.info("=== API Results ===")
                self.logger.info(f"Raw results: {all_results}")
                
            except asyncio.TimeoutError:
                self.logger.error("Timeout while waiting for image generation")
                return []
            
            except Exception as e:
                self.logger.error(f"Error during image generation: {str(e)}")
                return []

            # Process results
            image_results = []
            for i, (result, request_id) in enumerate(zip(all_results, request_ids)):
                # Check if the result is an exception
                if isinstance(result, Exception):
                    self.logger.error(f"Error generating image {i+1} (ID: {request_id}): {str(result)}")
                    continue
                
                # Handle normal results
                if result and len(result) > 0:
                    image = result[0]
                    # Log the complete image object
                    self.logger.info(f"Image {i+1} (ID: {request_id}) complete result: {image}")
                    
                    # Get the image URL
                    if isinstance(image, dict):
                        image_url = image.get('imageURL', image.get('url'))
                    elif hasattr(image, 'imageURL'):
                        image_url = image.imageURL
                    else:
                        self.logger.error(f"Image object does not have imageURL attribute: {image}")
                        continue
                    
                    if not image_url:
                        self.logger.error(f"No URL found in image object: {image}")
                        continue
                    
                    # Generate a unique ID from the URL
                    try:
                        image_id = image_url.split('/')[-1].split('.')[0]
                    except:
                        image_id = f"img_{int(time.time())}_{i}"
                    
                    # Download and save the image
                    file_path = await self._download_and_save_image(image_url, image_id)
                    
                    # Add result to our list
                    image_results.append({
                        'url': image_url,
                        'file_path': file_path
                    })

            # Log the complete list with repr to ensure nothing is truncated
            self.logger.info(f"All generated image results: {repr(image_results)}")
            
            # Always return the list of results
            return image_results

        except Exception as e:
            self.logger.error(f"Error in image generation: {str(e)}")
            return []

    async def _download_and_save_image(self, image_url: str, image_id: str) -> str:
        """
        Download an image from URL and save it to MinIO.
        
        This method handles:
        1. Image downloading from Runware
        2. Temporary local storage
        3. Upload to MinIO
        4. Cleanup of temporary files
        5. Error handling and logging
        
        Args:
            image_url: The URL of the image to download
            image_id: The unique ID for this image
            
        Returns:
            The MinIO URL where the image was saved, or None if the operation failed
        """
        try:
            # Type checking
            if not isinstance(image_url, str):
                self.logger.error(f"image_url must be a string, got {type(image_url)}: {image_url}")
                return None
                
            if not isinstance(image_id, str):
                self.logger.error(f"image_id must be a string, got {type(image_id)}: {image_id}")
                return None
            
            # Create a file path using the image ID
            file_name = f"{image_id}.jpg"
            file_path = os.path.join(self.images_dir, file_name)
            
            self.logger.info(f"Downloading image from {image_url} to {file_path}")
            
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    response.raise_for_status()
                    content = await response.read()
                    
                    # Save to file temporarily
                    with open(file_path, 'wb') as f:
                        f.write(content)
                        
            self.logger.info(f"Saved image {image_id} to {file_path}")
            
            # Upload to MinIO
            from app.services.store_images import StoreImages
            image_store = StoreImages()
            minio_url = image_store.upload_image(file_path, object_name=file_name)
            
            # Clean up local file
            try:
                os.remove(file_path)
            except Exception as e:
                self.logger.warning(f"Failed to clean up local file {file_path}: {str(e)}")
            
            self.logger.info(f"Uploaded image {image_id} to MinIO: {minio_url}")
            return minio_url
            
        except Exception as e:
            self.logger.error(f"Error downloading/saving image {image_id}: {str(e)}")
            return None