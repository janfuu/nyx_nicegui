"""
Controls Content Component
=========================

This module provides a testing interface for image generation and preview.
It focuses on:
1. Image generation testing
2. Image preview and lightbox functionality
3. Image rating and storage in Qdrant

The component is used for development and testing of the image generation system.
"""

from nicegui import ui, events
from app.core.image_scene_parser import ImageSceneParser
from app.core.image_generator import ImageGenerator
from app.services.qdrant_image_store import QdrantImageStore
from app.services.embedder import get_embedder
from app.services.store_images import StoreImages
import asyncio
import uuid
import time
import requests
import os

class Lightbox:
    """
    A modal image gallery for previewing and storing generated images.
    
    Features:
    1. Full-screen image viewing
    2. Navigation between images
    3. Basic prompt information display
    4. Image rating and storage in Qdrant
    """
    
    def __init__(self) -> None:
        """
        Initialize the lightbox UI and state.
        
        Creates a full-screen dialog with:
        - Image display area
        - Navigation controls
        - Rating buttons
        - Prompt information display
        """
        # Create a maximized dialog that serves as the lightbox container
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            # Register keyboard event handler for navigation
            ui.keyboard(self._handle_key)
            
            # Main container layout
            with ui.column().classes('w-full h-full items-center justify-between'):
                # Image counter at the top (e.g. "2 / 5")
                self.counter = ui.label().classes('text-white text-h6 mt-2')
                
                # Main content area with navigation controls
                with ui.row().classes('w-full flex-grow'):
                    # Left navigation button
                    with ui.button(on_click=lambda: self._navigate(-1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_left').classes('text-4xl')
                    
                    # Center image container with proper scaling
                    with ui.column().classes('flex-grow items-center justify-center h-[80vh]'):
                        self.large_image = ui.image().props('no-spinner fit=scale-down').classes('max-h-full max-w-full')
                    
                    # Right navigation button
                    with ui.button(on_click=lambda: self._navigate(1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_right').classes('text-4xl')
                
                # Bottom information panel
                with ui.column().classes('w-full bg-gray-900 p-2 rounded-t-lg'):
                    # Prompt information display area
                    with ui.row().classes('w-full'):
                        with ui.column().classes('w-full gap-2'):
                            # Original and parsed prompts as markdown
                            self.original_prompt = ui.markdown("").classes('text-white text-sm')
                            self.parsed_prompt = ui.markdown("").classes('text-white text-sm')
                    
                    # Rating buttons row
                    with ui.row().classes('w-full justify-center items-center gap-4 mt-4'):
                        # Positive rating button
                        self.thumbs_up = ui.button(on_click=self._rate_positive).props('flat round color=green').classes('text-2xl')
                        with self.thumbs_up:
                            ui.icon('thumb_up').classes('text-2xl')
                        
                        # Neutral rating button
                        self.neutral = ui.button(on_click=self._rate_neutral).props('flat round color=blue-grey').classes('text-2xl')
                        with self.neutral:
                            ui.icon('thumbs_up_down').classes('text-2xl')
                        
                        # Negative rating button
                        self.thumbs_down = ui.button(on_click=self._rate_negative).props('flat round color=red').classes('text-2xl')
                        with self.thumbs_down:
                            ui.icon('thumb_down').classes('text-2xl')
                        
                        # Status indicator for operations
                        self.status = ui.label("").classes('text-white ml-4')
        
        # Internal state management
        self.image_list = []         # List of image URLs
        self.prompt_list = []        # List of original prompts
        self.parsed_prompt_list = [] # List of parsed prompts
        self.id_list = []            # List of unique image IDs
        self.current_index = 0       # Current image index being viewed
        self.rating = 0              # Current image rating

    def add_image(self, image_url: str, original_prompt: str = "", parsed_prompt: str = "", image_id: str = None) -> None:
        """
        Add an image to the lightbox collection.
        
        Args:
            image_url: URL of the image to add
            original_prompt: Original text that generated the image
            parsed_prompt: Processed prompt used for generation
            image_id: Unique ID for the image (generates UUID if not provided)
        """
        self.image_list.append(image_url)
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        self.id_list.append(image_id or str(uuid.uuid4()))

    def show(self, image_url: str) -> None:
        """
        Display a specific image in the lightbox.
        
        Args:
            image_url: URL of the image to display
        """
        try:
            # Find the index of the image in our collection
            idx = self.image_list.index(image_url)
            self._open(self.image_list[idx])
        except ValueError:
            print(f"Image URL {image_url} not found in lightbox")

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        """
        Handle keyboard navigation events.
        
        Args:
            event_args: Keyboard event arguments
        
        Supported keys:
        - Escape: Close the lightbox
        - Left Arrow: Previous image
        - Right Arrow: Next image
        """
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        if event_args.key.arrow_left:
            self._navigate(-1)
        if event_args.key.arrow_right:
            self._navigate(1)

    def _navigate(self, direction: int) -> None:
        """
        Navigate between images.
        
        Args:
            direction: Direction to navigate (-1 for previous, 1 for next)
        """
        current_idx = self.current_index
        new_idx = current_idx + direction
        
        # Ensure index is within bounds
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        """
        Open and display an image in the lightbox.
        
        Args:
            url: URL of the image to display
        """
        # Set the image source
        self.large_image.set_source(url)
        
        # Update current index and counter
        current_idx = self.image_list.index(url)
        self.current_index = current_idx
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        
        # Update prompt information
        if current_idx < len(self.prompt_list):
            self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
        
        if current_idx < len(self.parsed_prompt_list):
            self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
        
        # Open the dialog
        self.dialog.open()

    async def _rate_positive(self):
        """Rate current image positively (+1)."""
        await self._rate_image(1)
    
    async def _rate_neutral(self):
        """Rate current image neutrally (0)."""
        await self._rate_image(0)
    
    async def _rate_negative(self):
        """Rate current image negatively (-1)."""
        await self._rate_image(-1)
        
    async def _rate_image(self, rating_value: int) -> None:
        """
        Store an image rating in Qdrant with full context.
        
        This method first checks if the image already exists in Qdrant and 
        updates the rating if it does. Otherwise, it downloads the image,
        uploads it to MinIO, generates an embedding, and stores everything
        in Qdrant with appropriate metadata.
        
        Args:
            rating_value: Rating value (-1 for negative, 0 for neutral, 1 for positive)
        """
        try:
            # Get current image information
            current_idx = self.current_index
            if current_idx < 0 or current_idx >= len(self.id_list):
                return
                
            image_id = self.id_list[current_idx]
            image_url = self.image_list[current_idx]
            original_prompt = self.prompt_list[current_idx]
            parsed_prompt = self.parsed_prompt_list[current_idx]
            
            # Determine the appropriate rating message for user feedback
            if rating_value > 0:
                rating_message = "Positively"
            elif rating_value < 0:
                rating_message = "Negatively" 
            else:
                rating_message = "Neutrally"
                
            self.status.text = f"{rating_message} rating image..."
            
            # Get service instances
            embedder = get_embedder()
            qdrant = QdrantImageStore()
            image_store = StoreImages()
            
            # First check if image already exists in Qdrant
            update_success = False
            try:
                # Attempt to update the rating first
                # If it succeeds, the image is already in Qdrant
                result = await qdrant.update_rating(image_id, rating_value)
                if result:
                    update_success = True
                    self.status.text = f"Rating updated successfully ✓"
                    return
            except Exception as check_e:
                # Only print if it's not a 404 error (expected when image doesn't exist yet)
                if "404" not in str(check_e) and "Not found" not in str(check_e):
                    print(f"Unexpected error checking image in Qdrant: {str(check_e)}")
            
            # If update was successful, we're done
            if update_success:
                return
                
            # If image doesn't exist in Qdrant, download it first
            try:
                response = requests.get(image_url)
                response.raise_for_status()
                image_data = response.content
            except Exception as e:
                self.status.text = f"Failed to download image: {str(e)}"
                return
            
            # Create a temporary file for processing
            temp_file = f"temp_{image_id}.jpg"
            try:
                with open(temp_file, 'wb') as f:
                    f.write(image_data)
            except Exception as e:
                self.status.text = f"Failed to save image: {str(e)}"
                return
            
            # Upload to MinIO storage
            try:
                minio_url = image_store.upload_image(temp_file, f"{image_id}.jpg")
                self.status.text = f"Image uploaded to MinIO..."
            except Exception as e:
                self.status.text = f"Failed to upload to MinIO: {str(e)}"
                # Clean up temp file on error
                try:
                    os.remove(temp_file)
                except:
                    pass
                return
            
            # Generate CLIP embedding for similarity search
            image_vector = embedder.embed_image_from_file(temp_file)
            if image_vector is None:
                self.status.text = "Failed to embed image"
                # Clean up temp file on error
                try:
                    os.remove(temp_file)
                except:
                    pass
                return
            
            # Clean up temporary file
            try:
                os.remove(temp_file)
            except:
                pass
                
            # Prepare payload with all context for Qdrant
            payload = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,
                "url": minio_url,  # Store MinIO URL instead of Runware URL
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "runware",
                "rating": rating_value,
                "image_id": image_id
            }
            
            # Store in Qdrant with full context
            result = await qdrant.store_image(
                image_id=image_id,
                vector=image_vector.tolist(),
                metadata=payload
            )
            
            # Update status based on result
            if result:
                self.status.text = f"Image stored with {rating_value} rating ✓"
            else:
                self.status.text = "Storage failed ✗"
                
        except Exception as e:
            # Log detailed error information
            import traceback
            print(f"Error storing rated image: {str(e)}")
            print(traceback.format_exc())
            self.status.text = f"Error: {str(e)}"

def test_image_generator_parser():
    """
    Test interface for the image generator and scene parser.
    
    This function creates a UI for:
    1. Entering text with visual descriptions
    2. Parsing scenes from the text
    3. Generating images for each scene
    4. Displaying the results with lightbox integration
    """
    # Initialize core components
    image_scene_parser = ImageSceneParser()
    image_generator = ImageGenerator()
    lightbox = Lightbox()
    
    # Create the main testing UI
    with ui.card().classes('w-full p-4'):
        ui.label('Test Image Generation').classes('text-xl font-bold mb-4')
        
        # Input area for testing
        with ui.card().classes('w-full p-3 mb-4 bg-gray-800'):
            ui.label('Enter a response with visual descriptions:').classes('text-sm mb-2')
            test_input = ui.textarea(placeholder='Enter text with visual descriptions...').classes('w-full bg-gray-800 border-none')
        
        # Dynamic results container
        results_container = ui.column().classes('w-full')
        
        async def generate_images(scenes):
            """
            Generate images for each parsed scene in parallel.
            
            Args:
                scenes: List of scene objects from the parser
            """
            with results_container:
                # Display parsed scenes section
                ui.label('Parsed Scenes').classes('text-h6 q-mt-md')
                for scene in scenes:
                    with ui.card().classes('q-mb-sm q-pa-sm bg-dark'):
                        original_text = scene.get('original_text', '') if isinstance(scene, dict) else scene
                        ui.label(original_text).classes('text-body2')
                
                ui.separator()
                
                # Start image generation section
                ui.label('Generated Images').classes('text-h6 q-mt-md')
                with ui.row().classes('q-gutter-md flex-wrap'):
                    tasks = []
                    containers = []
                    
                    # Create UI containers for each scene
                    for scene in scenes:
                        try:
                            scene_prompt = scene.get('prompt', scene) if isinstance(scene, dict) else scene
                            
                            # Build card for each image
                            with ui.card().classes('q-pa-xs'):
                                # Loading spinner (shown during generation)
                                loading = ui.spinner('default', size='xl').props('color=primary')
                                
                                # Image container (clickable for lightbox)
                                container = ui.button().props('flat dense').classes('w-[300px] h-[300px] overflow-hidden')
                                with container:
                                    img = ui.image().props('fit=cover').classes('w-full h-full')
                                    img.visible = False
                                
                                # Description and frame info
                                with ui.row().classes('items-center justify-between q-mt-xs'):
                                    # Truncate long descriptions
                                    original_text = scene.get('original_text', '') if isinstance(scene, dict) else scene
                                    desc = original_text[:30] + "..." if len(original_text) > 30 else original_text
                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                    
                                    # Show frame number if available
                                    frame = scene.get('frame')
                                    if frame:
                                        ui.label(f"[Frame {frame}]").classes('text-caption text-grey-5')
                                
                                # Track task and container for later updates
                                tasks.append({
                                    'scene': scene,
                                    'loading': loading,
                                    'img': img,
                                    'button': container
                                })
                                containers.append(container)
                        except Exception as e:
                            print(f"Error setting up image generation for scene: {scene}")
                            print(f"Error details: {str(e)}")
                            ui.notify(f"Error setting up image generation: {str(e)}", type='negative')
                    
                    try:
                        # Generate all images in parallel
                        print(f"Generating {len(scenes)} images in parallel...")
                        image_urls = await image_generator.generate(scenes)
                        
                        # Update UI after generation completes
                        for task, image_url in zip(tasks, image_urls):
                            if image_url:
                                # Generation successful
                                print(f"Successfully generated image: {image_url}")
                                
                                # Update UI elements
                                task['loading'].visible = False
                                task['img'].set_source(image_url['url'])
                                task['img'].visible = True
                                
                                # Extract prompt information
                                scene_data = task['scene']
                                original_prompt = scene_data.get('original_text', '') if isinstance(scene_data, dict) else str(scene_data)
                                parsed_prompt = scene_data.get('prompt', scene_data) if isinstance(scene_data, dict) else str(scene_data)
                                
                                # Add to lightbox for preview/rating
                                lightbox.add_image(
                                    image_url=image_url['url'],
                                    original_prompt=original_prompt,
                                    parsed_prompt=parsed_prompt
                                )
                                
                                # Setup lightbox click handler
                                task['button'].on('click', lambda url=image_url['url']: lightbox.show(url))
                                
                                ui.notify("Image generated successfully", type='positive')
                            else:
                                # Generation failed
                                task['loading'].visible = False
                                ui.label('Generation failed').classes('text-caption text-negative')
                    
                    except Exception as e:
                        # Handle errors in parallel generation process
                        print(f"Error in parallel generation: {str(e)}")
                        ui.notify(f"Error generating images: {str(e)}", type='negative')
        
        async def run_test(e):
            """
            Run the test with the current input text.
            
            This function:
            1. Parses the input text for visual scenes
            2. Generates images for each scene
            3. Displays the results
            
            Args:
                e: Event object from button click
            """
            try:
                # Clear previous results
                results_container.clear()
                
                # Show initial processing status
                with results_container:
                    status_card = ui.card().classes('w-full p-4')
                    with status_card:
                        with ui.row().classes('items-center gap-4'):
                            ui.spinner('dots').classes('text-primary')
                            ui.label('Processing response...').classes('text-lg')
                
                # Create image context for the parser
                image_context = {
                    "raw_text": test_input.value
                }
                
                try:
                    # Update status to show parsing phase
                    status_card.clear()
                    with status_card:
                        with ui.row().classes('items-center gap-4'):
                            ui.spinner('dots').classes('text-primary')
                            ui.label('Parsing visual scenes...').classes('text-lg')
                    
                    # Parse scenes with timeout protection
                    async def parse_with_timeout():
                        try:
                            return await image_scene_parser.parse_images(image_context)
                        except Exception as e:
                            print(f"Error in scene parsing: {str(e)}")
                            return None
                    
                    try:
                        # Set a timeout to prevent hanging
                        timeout_seconds = 30
                        parsed_scenes = await asyncio.wait_for(parse_with_timeout(), timeout=timeout_seconds)
                        
                        # Handle case with no scenes
                        if parsed_scenes is None or len(parsed_scenes) == 0:
                            status_card.clear()
                            with status_card:
                                ui.label("No visual scenes detected in input").classes('text-warning')
                            return
                            
                    except asyncio.TimeoutError:
                        # Handle timeout case
                        print("Timeout while waiting for scene parsing")
                        status_card.clear()
                        with status_card:
                            ui.label("Scene parsing is taking longer than expected. Please wait or try again.").classes('text-warning')
                        return
                        
                except Exception as e:
                    # Handle general parsing errors
                    print(f"Parser error: {str(e)}")
                    results_container.clear()
                    with results_container:
                        with ui.card().classes('w-full p-4 bg-red-100 dark:bg-red-900'):
                            ui.label('Error during scene parsing. Please try again.').classes('text-red-600 dark:text-red-100')
                    return
                
                # Clear status and proceed to image generation
                results_container.clear()
                
                if parsed_scenes and len(parsed_scenes) > 0:
                    # Generate images for the parsed scenes
                    await generate_images(parsed_scenes)
                else:
                    # Handle case with no visual scenes
                    with results_container:
                        ui.label("No visual scenes found in the input").classes('text-gray-400')
                        
            except Exception as e:
                # Handle unexpected errors
                results_container.clear()
                with results_container:
                    with ui.card().classes('w-full p-4 bg-red-100 dark:bg-red-900'):
                        ui.label(f'Error: {str(e)}').classes('text-red-600 dark:text-red-100')
                print(f"Full error: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # Button to run the test
        ui.button('Run Test', on_click=run_test).props('icon=play_arrow color=purple')

def content() -> None:
    """
    Main content function for the controls interface.
    
    This function creates the top-level UI for the testing interface.
    """
    with ui.card().classes('w-full'):
        ui.markdown("**Image Generation Test**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Test Image Generator & Parser', on_click=test_image_generator_parser).props('color="primary"')
