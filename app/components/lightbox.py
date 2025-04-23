from nicegui import ui, events
import uuid

class Lightbox:
    """A thumbnail gallery where each image can be clicked to enlarge."""
    def __init__(self) -> None:
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            ui.keyboard(self._handle_key)
            with ui.column().classes('w-full h-full items-center justify-between'):
                # Counter at the top
                self.counter = ui.label().classes('text-white text-h6 mt-2')
                
                # Main content area with navigation areas on sides
                with ui.row().classes('w-full flex-grow'):
                    # Left navigation area - full height
                    with ui.button(on_click=lambda: self._navigate(-1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_left').classes('text-4xl')
                    
                    # Center container for image
                    with ui.column().classes('flex-grow items-center justify-center h-[80vh]'):
                        self.large_image = ui.image().props('no-spinner fit=scale-down').classes('max-h-full max-w-full')
                    
                    # Right navigation area - full height
                    with ui.button(on_click=lambda: self._navigate(1)).props('flat color=white').classes('h-full rounded-none flex items-center justify-center w-16 opacity-70 hover:opacity-100'):
                        ui.icon('chevron_right').classes('text-4xl')
                
                # Bottom info and controls
                with ui.column().classes('w-full bg-gray-900 p-2 rounded-t-lg'):
                    # Prompt information
                    with ui.row().classes('w-full'):
                        with ui.column().classes('w-full gap-2'):
                            self.original_prompt = ui.markdown("").classes('text-white text-sm')
                            self.parsed_prompt = ui.markdown("").classes('text-white text-sm')
                    
                    # Rating buttons
                    with ui.row().classes('w-full justify-center items-center gap-4 mt-4'):
                        self.thumbs_up = ui.button(on_click=self._rate_positive).props('flat round color=green').classes('text-2xl')
                        with self.thumbs_up:
                            ui.icon('thumb_up').classes('text-2xl')
                        
                        self.neutral = ui.button(on_click=self._rate_neutral).props('flat round color=blue-grey').classes('text-2xl')
                        with self.neutral:
                            ui.icon('thumbs_up_down').classes('text-2xl')
                        
                        self.thumbs_down = ui.button(on_click=self._rate_negative).props('flat round color=red').classes('text-2xl')
                        with self.thumbs_down:
                            ui.icon('thumb_down').classes('text-2xl')
                        
                        # Storage status indicator
                        self.status = ui.label("").classes('text-white ml-4')
        
        self.image_list = []
        self.prompt_list = []
        self.parsed_prompt_list = []
        self.id_list = []
        self.current_index = 0

    def add_image(self, image_id: str, image_url: str, original_prompt: str = "", parsed_prompt: str = "") -> None:
        """Add an image to the lightbox"""
        self.image_list.append(image_url)
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        self.id_list.append(image_id)

    def show(self, image_id: str) -> None:
        """Show the lightbox with the specified image"""
        try:
            idx = self.id_list.index(image_id)
            self._open(self.image_list[idx])
        except ValueError:
            print(f"Image ID {image_id} not found in lightbox")

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        if event_args.key.arrow_left:
            self._navigate(-1)
        if event_args.key.arrow_right:
            self._navigate(1)

    def _navigate(self, direction: int) -> None:
        """Navigate through images. direction should be -1 for previous or 1 for next."""
        current_idx = self.current_index
        new_idx = current_idx + direction
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        current_idx = self.image_list.index(url)
        self.current_index = current_idx
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        
        # Update prompt information
        if current_idx < len(self.prompt_list):
            self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
        
        if current_idx < len(self.parsed_prompt_list):
            self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
        
        # Reset status
        self.status.text = ""
        
        self.dialog.open()
    
    async def _rate_positive(self):
        """Rate the current image positively and store it in Qdrant"""
        await self._rate_image(1)
    
    async def _rate_neutral(self):
        """Rate the current image neutrally and store in Qdrant with neutral rating"""
        await self._rate_image(0)
    
    async def _rate_negative(self):
        """Rate the current image negatively and store in Qdrant with negative rating"""
        await self._rate_image(-1)
        
    async def _rate_image(self, rating_value):
        """Store image in Qdrant with specified rating"""
        try:
            current_idx = self.current_index
            if current_idx < 0 or current_idx >= len(self.id_list):
                return
                
            image_id = self.id_list[current_idx]
            image_url = self.image_list[current_idx]
            original_prompt = self.prompt_list[current_idx]
            parsed_prompt = self.parsed_prompt_list[current_idx]
            
            # Determine the appropriate rating message
            if rating_value > 0:
                rating_message = "Positively"
            elif rating_value < 0:
                rating_message = "Negatively" 
            else:
                rating_message = "Neutrally"
                
            self.status.text = f"{rating_message} rating image..."
            
            # Get embedder and Qdrant client
            from app.main import get_embedder
            from app.services.qdrant_client import QdrantImageStore
            
            embedder = get_embedder()
            qdrant = QdrantImageStore()
            
            # First check if the image already exists in Qdrant
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
            
            if update_success:
                return
                
            # Get current appearance and mood
            from app.core.memory_system import MemorySystem
            memory_system = MemorySystem()
            current_appearance = memory_system.get_recent_appearances(1)
            current_appearance_text = current_appearance[0]["description"] if current_appearance else None
            current_mood = memory_system.get_current_mood()
            current_location = memory_system.get_recent_locations(1)
            current_location_text = current_location[0]["description"] if current_location else None
            
            # Embed the image
            image_vector, thumbnail_b64 = embedder.embed_image_from_url(image_url)
            if image_vector is None:
                self.status.text = "Failed to embed image"
                return
                
            # Prepare payload
            import time
            payload = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,  # Store both prompts
                "url": image_url,
                "thumbnail_b64": thumbnail_b64,
                "mood": current_mood,
                "appearance": current_appearance_text,
                "location": current_location_text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "runware",
                "rating": rating_value
            }
            
            # Store in Qdrant
            result = await qdrant.store_image_embedding(
                image_id=image_id,
                vector=image_vector.tolist(),
                payload=payload
            )
            
            if result:
                self.status.text = f"Image stored with {rating_value} rating ✓"
            else:
                self.status.text = "Storage failed ✗"
                
        except Exception as e:
            import traceback
            print(f"Error storing rated image: {str(e)}")
            print(traceback.format_exc())
            self.status.text = f"Error: {str(e)}" 