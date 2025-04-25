from nicegui import ui, events
from app.components.image_rating import ImageRating

class Lightbox:
    """Displays images in a lightbox with navigation"""
    def __init__(self) -> None:
        self.images = []
        self.current_index = 0
        self.dialog = None
        self.image_display = None
        self.prompt_display = None
        self.rating_component = ImageRating()
        
    def add_image(self, image_url: str, original_prompt: str, parsed_prompt: str) -> None:
        """Add an image to the lightbox"""
        self.images.append({
            'url': image_url,
            'original_prompt': original_prompt,
            'parsed_prompt': parsed_prompt
        })
        
    def show(self, image_url: str) -> None:
        """
        Display a specific image in the lightbox.
        
        Args:
            image_url: URL of the image to display
        """
        try:
            # Find the index of the image in our collection
            for i, img in enumerate(self.images):
                if img['url'] == image_url:
                    self.current_index = i
                    self._open()
                    return
                    
            # If image not found, show first image
            if self.images:
                self.current_index = 0
                self._open()
        except Exception as e:
            print(f"Error showing image in lightbox: {e}")
        
    def _open(self) -> None:
        """Open the lightbox dialog"""
        if self.dialog is None:
            with ui.dialog() as self.dialog, ui.card().classes('w-full max-w-4xl'):
                with ui.row().classes('w-full'):
                    # Navigation buttons
                    with ui.column().classes('w-1/12'):
                        ui.button(icon='chevron_left', on_click=self._prev_image).classes('w-full')
                    # Image display
                    with ui.column().classes('w-10/12'):
                        self.image_display = ui.image('').classes('w-full')
                        self.prompt_display = ui.label('').classes('text-white mt-2')
                    with ui.column().classes('w-1/12'):
                        ui.button(icon='chevron_right', on_click=self._next_image).classes('w-full')
                        
                # Rating buttons
                with ui.row().classes('w-full justify-center mt-4'):
                    ui.button(icon='thumb_down', on_click=lambda: self._rate_image(-1)).classes('text-red-500')
                    ui.button(icon='thumbs_up_down', on_click=lambda: self._rate_image(0)).classes('text-yellow-500')
                    ui.button(icon='thumb_up', on_click=lambda: self._rate_image(1)).classes('text-green-500')
                    self.rating_component.status
                    
        self._update_display()
        self.dialog.open()
        
    def _update_display(self) -> None:
        """Update the displayed image and prompts"""
        if not self.images:
            return
            
        current = self.images[self.current_index]
        self.image_display.set_source(current['url'])
        self.prompt_display.text = f"Original: {current['original_prompt']}\nParsed: {current['parsed_prompt']}"
        
    def _prev_image(self) -> None:
        """Show previous image"""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_display()
            
    def _next_image(self) -> None:
        """Show next image"""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._update_display()
            
    async def _rate_image(self, rating: int) -> None:
        """Rate the current image"""
        if not self.images:
            return
            
        current = self.images[self.current_index]
        await self.rating_component.rate_image(
            image_id=current['url'],  # Using URL as ID for now
            image_url=current['url'],
            original_prompt=current['original_prompt'],
            parsed_prompt=current['parsed_prompt'],
            rating_value=rating
        ) 