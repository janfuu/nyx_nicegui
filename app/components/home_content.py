from nicegui import ui, app, events
from ..services.chat_pipeline import ChatPipeline
import time
import asyncio
from ..core.memory_system import MemorySystem
import httpx
import json
from typing import List

class Lightbox:
    """A thumbnail gallery where each image can be clicked to enlarge."""
    def __init__(self) -> None:
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            ui.keyboard(self._handle_key)
            with ui.row().classes('w-full h-full items-center justify-between'):
                # Left arrow
                with ui.button(on_click=lambda: self._navigate(-1)).props('flat round color=white').classes('ml-4'):
                    ui.icon('chevron_left').classes('text-4xl')
                
                # Center container for image
                with ui.column().classes('flex-grow items-center justify-center h-full'):
                    self.large_image = ui.image().props('no-spinner fit=scale-down').classes('max-h-[90vh]')
                    self.counter = ui.label().classes('mt-2 text-white')
                
                # Right arrow
                with ui.button(on_click=lambda: self._navigate(1)).props('flat round color=white').classes('mr-4'):
                    ui.icon('chevron_right').classes('text-4xl')
        
        self.image_list: List[str] = []

    def add_image(self, thumb_url: str, orig_url: str) -> ui.image:
        """Place a thumbnail image in the UI and make it clickable to enlarge."""
        self.image_list.append(orig_url)
        with ui.button(on_click=lambda: self._open(orig_url)).props('flat dense square'):
            return ui.image(thumb_url)

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
        current_idx = self.image_list.index(self.large_image.source)
        new_idx = current_idx + direction
        if 0 <= new_idx < len(self.image_list):
            self._open(self.image_list[new_idx])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        current_idx = self.image_list.index(url)
        self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
        self.dialog.open()

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    lightbox = Lightbox()  # Initialize lightbox
    
    # Get initial state from database
    initial_mood = memory_system.get_current_mood()
    initial_thoughts = memory_system.get_recent_thoughts(1)
    initial_appearances = memory_system.get_recent_appearances(1)
    
    # Reference to the portrait image element for updating
    portrait_ref = None
    
    async def set_as_portrait(image_url):
        """Copy the image to the portrait location"""
        try:
            # Download the image
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Save to assets directory
                portrait_path = 'app/assets/images/portrait.jpg'
                with open(portrait_path, 'wb') as f:
                    f.write(response.content)
            
            # Update the portrait in the UI
            if portrait_ref:
                portrait_ref.set_source(portrait_path)
            ui.notify('Portrait updated successfully!', color='positive')
        except Exception as e:
            ui.notify(f'Failed to update portrait: {str(e)}', color='negative')
    
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1 max-w-[512px]'):
            with ui.column().classes('gap-4 w-full'):
                # Store reference to portrait image
                portrait_path = 'app/assets/images/portrait.jpg'
                portrait_ref = ui.image(portrait_path).classes('w-full max-w-[512px] max-h-[512px] rounded-xl')
                
                # Character's current mood display
                ui.label('MOOD').classes('text-blue-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    mood_display = ui.markdown(initial_mood).classes('text-sm')

                # Character's current appearance display
                ui.label('APPEARANCE').classes('text-purple-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    initial_appearance = initial_appearances[0]["description"] if initial_appearances else "A young woman with cybernetic enhancements, circuits glowing faintly beneath her skin..."
                    appearance_display = ui.markdown(initial_appearance).classes('text-sm')

                # Character's thoughts display
                ui.label('THOUGHTS').classes('text-gray-500 text-sm')
                with ui.card().classes('bg-[#1a1a1a] p-3 rounded w-full'):
                    initial_thought = initial_thoughts[0]["content"] if initial_thoughts else "It's... unusual to be addressed so familiarly..."
                    thoughts_display = ui.markdown(initial_thought).classes('text-sm')

        # Center Card
        with ui.card().classes('flex-2 w-[800px]'):
            with ui.column().classes('h-full w-full gap-4'):
                # Chat display area - use a simple scrollable container
                chat_container = ui.scroll_area().classes('h-[600px] w-full')
                with chat_container:
                    chat_box = ui.column().classes('p-6 bg-[#1a1a1a] rounded w-full')
                
                # Function to display image details
                def show_image_details(image_data):
                    lightbox._open(image_data["url"])
                
                # Message input and send button
                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.textarea(placeholder='Type a message...')\
                        .classes('flex-1 bg-[#1f1f1f] text-white')\
                        .props('auto-grow')
                    thinking_indicator = ui.spinner('Thinking...').classes('hidden')
                    
                    def send_message():
                        """Handle the send button click or Enter key"""
                        user_message = msg_input.value
                        if not user_message.strip():
                            return
                        
                        # Clear input immediately
                        current_message = user_message
                        msg_input.value = ""
                        
                        # Display user message immediately
                        with chat_box:
                            user_msg = ui.label(f"You: {current_message}").classes('self-end bg-blue-800 p-2 rounded-lg mb-2 max-w-3/4')
                        
                        # Ensure UI updates before continuing
                        ui.update()
                        
                        # Show thinking indicator
                        thinking_indicator.classes('inline-block')
                        ui.update()  # Force UI update again to show the spinner
                        
                        async def process_message():
                            try:
                                # Get LLM response with timeout
                                response = await asyncio.wait_for(
                                    chat_pipeline.process_message(current_message),
                                    timeout=90  # 90 second timeout for LLM response
                                )
                                
                                # Display assistant response with original formatting
                                with chat_box:
                                    # Create a message container for text and related images
                                    with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500'):
                                        # First show the text response with markdown formatting
                                        ui.markdown(response['text']).classes('text-white')
                                        
                                        # Display any thoughts in a subtle way
                                        if response.get("thoughts"):
                                            ui.separator().classes('my-2')
                                            with ui.expansion('THOUGHTS', icon='psychology').classes('w-full'):
                                                for thought in response["thoughts"]:
                                                    ui.markdown(f"*{thought}*").classes('text-gray-300 text-sm italic pl-4')
                                                    thoughts_display.content = thought
                                        
                                        # Display mood update
                                        if response.get("mood"):
                                            ui.separator().classes('my-2')
                                            with ui.expansion('MOOD', icon='mood').classes('w-full'):
                                                ui.markdown(f"*{response['mood']}*").classes('text-blue-300 text-sm italic pl-4')
                                                mood_display.content = response["mood"]
                                        
                                        # Display appearance changes
                                        if response.get("appearance"):
                                            ui.separator().classes('my-2')
                                            with ui.expansion('APPEARANCE', icon='face').classes('w-full'):
                                                for appearance_change in response["appearance"]:
                                                    ui.markdown(f"*{appearance_change}*").classes('text-purple-300 text-sm italic pl-4')
                                                    appearance_display.content = appearance_change
                                        
                                        # Display generated images if present
                                        if response.get("images") and len(response["images"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.row().classes('q-gutter-md flex-wrap'):
                                                # Create a list to store image generation tasks
                                                tasks = []
                                                containers = []
                                                
                                                # First create all UI containers
                                                for image_data in response["images"]:
                                                    if isinstance(image_data, dict) and "url" in image_data and "description" in image_data:
                                                        try:
                                                            # Create a card for each image
                                                            with ui.card().classes('q-pa-xs'):
                                                                loading = ui.spinner('default', size='xl').props('color=primary')
                                                                container = ui.button().props('flat dense').classes('w-[300px] h-[400px] overflow-hidden')
                                                                with container:
                                                                    img = ui.image().props('fit=cover').classes('w-full h-full')
                                                                    img.visible = False
                                                                
                                                                with ui.row().classes('items-center justify-between q-mt-xs'):
                                                                    desc = image_data["description"][:30] + "..." if len(image_data["description"]) > 30 else image_data["description"]
                                                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                                                
                                                                tasks.append({
                                                                    'scene': image_data["description"],
                                                                    'loading': loading,
                                                                    'img': img,
                                                                    'button': container
                                                                })
                                                                containers.append(container)
                                                        except Exception as e:
                                                            print(f"Error setting up image display: {str(e)}")
                                                            ui.notify(f"Error displaying image: {str(e)}", type='negative')
                                                
                                                # Update UI for all images
                                                for task in tasks:
                                                    try:
                                                        task['loading'].visible = False
                                                        task['img'].set_source(image_data["url"])
                                                        task['img'].visible = True
                                                        lightbox.image_list.append(image_data["url"])
                                                        task['button'].on('click', lambda url=image_data["url"]: lightbox._open(url))
                                                    except Exception as e:
                                                        print(f"Error updating image display: {str(e)}")
                                                        task['loading'].visible = False
                                                        ui.label('Display failed').classes('text-caption text-negative')
                                        
                                        # Add Regenerate button for re-running image generation
                                        ui.separator().classes('my-2')
                                        with ui.row().classes('justify-between w-full'):
                                            regenerate_button = ui.button('Regenerate Images', icon='refresh')\
                                                .props('color=purple').classes('mr-2')
                                            
                                            async def regenerate_images():
                                                regenerate_button.props('loading')
                                                try:
                                                    # Get current appearance and mood for context
                                                    current_appearance = memory_system.get_recent_appearances(1)
                                                    current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                                                    current_mood = memory_system.get_current_mood()
                                                    current_location = memory_system.get_recent_locations(1)
                                                    current_location_text = current_location[0]["description"] if current_location else None
                                                    
                                                    # Extract image tags from response
                                                    import re
                                                    image_pattern = r'<image>(.*?)</image>'
                                                    image_tags = re.findall(image_pattern, response['text'], re.DOTALL)
                                                    
                                                    if not image_tags:
                                                        ui.notify('No <image> tags found in the response', color='warning')
                                                        return
                                                    
                                                    # Format image contents with context and sequence
                                                    image_context = {
                                                        "appearance": current_appearance_text,
                                                        "mood": current_mood,
                                                        "location": current_location_text,
                                                        "images": [{"content": tag.strip(), "sequence": i+1} for i, tag in enumerate(image_tags)]
                                                    }
                                                    
                                                    # Process through image parser
                                                    try:
                                                        # Use timeout for parser
                                                        parsed_scenes = await asyncio.wait_for(
                                                            chat_pipeline.image_scene_parser.parse_images(
                                                                json.dumps(image_context),
                                                                current_appearance=current_appearance_text
                                                            ),
                                                            timeout=60  # 60 second timeout for scene parsing
                                                        )
                                                    except asyncio.TimeoutError:
                                                        ui.notify('Image scene parsing timed out. Please try again.', color='warning')
                                                        regenerate_button.props('loading=false')
                                                        return
                                                    except Exception as e:
                                                        ui.notify(f'Error parsing image scenes: {str(e)}', color='negative')
                                                        regenerate_button.props('loading=false')
                                                        return
                                                    
                                                    if parsed_scenes:
                                                        # Generate all images in parallel
                                                        scene_contents = [{"prompt": scene["prompt"], "orientation": scene["orientation"]} for scene in parsed_scenes]
                                                        print(f"Generating {len(scene_contents)} images in parallel...")
                                                        
                                                        # Generate all images at once with timeout
                                                        image_urls = await asyncio.wait_for(
                                                            chat_pipeline.image_generator.generate(scene_contents),
                                                            timeout=90  # 90 second timeout for all images
                                                        )
                                                        
                                                        if image_urls and len(image_urls) > 0:
                                                            # Clear existing images
                                                            for child in list(chat_box.children):
                                                                if isinstance(child, ui.expansion) and child.text == 'GENERATED IMAGES':
                                                                    chat_box.remove(child)
                                                            
                                                            # Display regenerated images
                                                            with ui.expansion('GENERATED IMAGES', icon='image').classes('w-full'):
                                                                with ui.row().classes('flex-wrap gap-2 w-full'):
                                                                    # Create a list of tuples with original tag, parsed scene, and image URL
                                                                    image_data = list(zip(image_tags, parsed_scenes, image_urls))
                                                                    # Sort by sequence number if available
                                                                    image_data.sort(key=lambda x: x[1].get('sequence', 0) if isinstance(x[1], dict) else 0)
                                                                    
                                                                    for original_tag, scene, image_url in image_data:
                                                                        if image_url:
                                                                            with ui.card().classes('w-[180px] p-1 bg-gray-800'):
                                                                                img = lightbox.add_image(image_url, image_url)
                                                                                img.classes('w-full rounded-lg cursor-pointer')
                                                                                
                                                                                with ui.row().classes('items-center justify-between w-full mt-1'):
                                                                                    short_desc = original_tag[:30] + ("..." if len(original_tag) > 30 else original_tag)
                                                                                    ui.label(short_desc).classes('text-xs italic text-gray-300 truncate max-w-[75%]')
                                                                                    ui.button(icon='search', on_click=lambda url=image_url, tag=original_tag: show_image_details({"url": url, "description": tag}))\
                                                                                        .props('flat dense round').classes('text-xs')
                                                        else:
                                                            ui.notify('Failed to generate images', color='negative')
                                                    else:
                                                        ui.notify('No visual scenes found in the response', color='warning')
                                                except Exception as e:
                                                    ui.notify(f'Failed to generate images: {str(e)}', color='negative', timeout=5000)
                                                    print(f"Image generation error: {str(e)}")  # Log the full error
                                                finally:
                                                    regenerate_button.props('loading=false')
                                            
                                            regenerate_button.on('click', regenerate_images)
                                
                                # Update appearance display if provided
                                if response.get("appearance") and len(response["appearance"]) > 0:
                                    appearance_display.content = response["appearance"][-1]  # Show the most recent appearance update
                                    
                            except asyncio.TimeoutError:
                                # Handle timeout
                                with chat_box:
                                    ui.label("Sorry, I'm taking too long to respond. Please try again.").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                ui.notify("Request timed out", color="negative")
                            except Exception as e:
                                # Handle errors
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                ui.notify(f"Error processing message: {str(e)}", color="negative")
                                    
                            finally:
                                # Hide thinking indicator when done
                                thinking_indicator.classes('hidden')
                        
                        # Start the async processing
                        ui.timer(0.1, lambda: asyncio.create_task(process_message()), once=True)
                    
                    # Connect send button to function
                    send_button = ui.button('SEND', on_click=send_message)\
                        .props('icon=send').classes('bg-primary text-white px-8')
                    
                    # Allow pressing Enter to send
                    def on_key_press(e):
                        if e.args.get('key') == 'Enter' and not e.args.get('shiftKey'):
                            send_message()
                    
                    msg_input.on('keydown', on_key_press)

        # Right Card
        with ui.card().classes('flex-1 max-w-[768px]'):
            with ui.column().classes('gap-4 w-full'):
                # Location image
                location_image = ui.image('assets/images/location.png').classes('w-full rounded-xl')
                
                # Location description
                location_desc = ui.label('cyberpunk apartment interior at night... synthwave color palette').classes('text-xs text-gray-400')
                
                # Add controls for world management
                ui.button('Change Location', on_click=lambda: ui.notify('Location change functionality to be implemented')).classes('mt-4')