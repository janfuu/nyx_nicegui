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
        
        self.image_list = []
        self.prompt_list = []
        self.parsed_prompt_list = []
        self.id_list = []
        self.current_index = 0

    def add_image(self, thumb_url: str, orig_url: str, image_id: str = None, original_prompt: str = "", parsed_prompt: str = "") -> ui.image:
        """Place a thumbnail image in the UI and make it clickable to enlarge."""
        self.image_list.append(orig_url)
        
        # Store prompts and ID if provided
        self.prompt_list.append(original_prompt)
        self.parsed_prompt_list.append(parsed_prompt)
        
        # Generate an ID if not provided
        if image_id is None:
            import uuid
            image_id = str(uuid.uuid4())
        self.id_list.append(image_id)
        
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
        current_idx = self.current_index
        new_idx = current_idx + direction
        if 0 <= new_idx < len(self.image_list):
            print(f"Navigating from image {current_idx+1} to {new_idx+1} of {len(self.image_list)}")
            self._open(self.image_list[new_idx])
        else:
            print(f"Cannot navigate: current={current_idx+1}, requested={new_idx+1}, total={len(self.image_list)}")

    def _open(self, url: str) -> None:
        try:
            print(f"Opening image URL: {url}")
            self.large_image.set_source(url)
            current_idx = self.image_list.index(url)
            self.current_index = current_idx
            self.counter.text = f'{current_idx + 1} / {len(self.image_list)}'
            
            # Update prompt information if available
            if current_idx < len(self.prompt_list) and self.prompt_list[current_idx]:
                self.original_prompt.content = f"**Original prompt:** {self.prompt_list[current_idx]}"
            else:
                self.original_prompt.content = ""
            
            if current_idx < len(self.parsed_prompt_list) and self.parsed_prompt_list[current_idx]:
                self.parsed_prompt.content = f"**Parsed prompt:** {self.parsed_prompt_list[current_idx]}"
            else:
                self.parsed_prompt.content = ""
            
            self.dialog.open()
        except Exception as e:
            print(f"Error in lightbox._open: {str(e)}")
            import traceback
            print(traceback.format_exc())

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

# Helper function to clean response text by removing image tags
def clean_response_text(text):
    """Remove <image> and <thought> tags from response text while preserving the flow of conversation"""
    import re
    # Replace each <image>...</image> tag with a simple [Image] placeholder
    cleaned = re.sub(r'<image>(.*?)</image>', '[Image]', text, flags=re.DOTALL)
    # Replace each <thought>...</thought> tag with nothing (remove completely)
    cleaned = re.sub(r'<thought>(.*?)</thought>', '', cleaned, flags=re.DOTALL)
    return cleaned

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    lightbox = Lightbox()  # Initialize lightbox
    
    # Get initial state from database
    initial_mood = memory_system.get_current_mood()
    initial_thoughts = memory_system.get_recent_thoughts(1)
    initial_appearances = memory_system.get_recent_appearances(1)
    
    # Test mode flag
    test_mode = False
    
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
                # Add test mode toggle at the top of the chat
                with ui.row().classes('w-full justify-between items-center mb-2'):
                    ui.label('Chat Interface').classes('text-lg font-bold')
                    
                    with ui.row().classes('items-center gap-2'):
                        test_toggle = ui.switch('Test Mode', on_change=lambda e: toggle_test_mode(e.value))
                        test_toggle.props('color=purple dense')
                        test_help = ui.button(icon='help_outline').props('flat round dense').classes('text-xs')
                        
                        def show_test_help():
                            ui.notify(
                                'Test Mode echoes input as response without calling the LLM. '
                                'Use <image>description</image> tags to test image generation.',
                                type='info',
                                close_button='OK',
                                timeout=10000
                            )
                        
                        test_help.on_click(show_test_help)
                
                # Chat display area - use a simple scrollable container
                chat_container = ui.scroll_area().classes('h-[560px] w-full')  # Slightly reduced height to accommodate test mode toggle
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
                                if test_mode:
                                    # In test mode, create a mock response that echoes the input
                                    # Extract image tags if present
                                    import re
                                    image_tags = re.findall(r'<image>(.*?)</image>', current_message, re.DOTALL)
                                    
                                    mock_response = {
                                        'text': f"Echo: {current_message}",
                                        'thoughts': ["This is a test thought from echo mode"],
                                        'mood': "Testing and curious",
                                        'appearance': ["Current test appearance with subtle glow effects"],
                                        'images': []
                                    }
                                    
                                    # If image tags were found, create mock image data
                                    if image_tags:
                                        # Use nyx_avatar.png for all placeholders but ensure unique URLs for navigation
                                        avatar_path = '/assets/images/nyx_avatar.png'
                                        
                                        # Create mock image entries for each tag
                                        for i, tag in enumerate(image_tags):
                                            # Add a query parameter to make each URL unique
                                            unique_url = f"{avatar_path}?id={i}"
                                            mock_response['images'].append({
                                                'url': unique_url,  # Use unique URLs for each image
                                                'description': tag.strip(),
                                                'original_prompt': tag.strip(),
                                                'parsed_prompt': f"Parsed version of: {tag.strip()}"
                                            })
                                    
                                    response = mock_response
                                else:
                                    # Get LLM response with timeout in normal mode
                                    response = await asyncio.wait_for(
                                        chat_pipeline.process_message(current_message),
                                        timeout=90  # 90 second timeout for LLM response
                                    )
                                
                                # Display assistant response with original formatting
                                with chat_box:
                                    # Create a message container for text and related images
                                    with ui.card().classes('self-start bg-gray-700 p-3 rounded-lg mb-3 max-w-3/4 border-l-4 border-blue-500'):
                                        # Clean response text by removing image tags before displaying
                                        cleaned_text = clean_response_text(response['text'])
                                        ui.markdown(cleaned_text).classes('text-white')
                                        
                                        # Update the side panels with thoughts, mood, and appearance
                                        # But don't display them in the chat response anymore
                                        if response.get("thoughts"):
                                            for thought in response["thoughts"]:
                                                thoughts_display.content = thought
                                        
                                        if response.get("mood"):
                                            mood_display.content = response["mood"]
                                        
                                        if response.get("appearance"):
                                            for appearance_change in response["appearance"]:
                                                appearance_display.content = appearance_change
                                        
                                        # Display generated images if present
                                        if response.get("images") and len(response["images"]) > 0:
                                            ui.separator().classes('my-2')
                                            with ui.row().classes('q-gutter-sm flex-wrap justify-center'):
                                                # Create a list to store image generation tasks
                                                tasks = []
                                                containers = []
                                                
                                                # First create all UI containers
                                                for image_data in response["images"]:
                                                    if isinstance(image_data, dict) and "url" in image_data and "description" in image_data:
                                                        try:
                                                            # Create a card for each image - make it much smaller
                                                            with ui.card().classes('q-pa-xs'):
                                                                loading = ui.spinner('default', size='md').props('color=primary')
                                                                container = ui.button().props('flat dense').classes('w-[120px] h-[120px] overflow-hidden')
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
                                                for i, task in enumerate(tasks):
                                                    try:
                                                        # Get the right image data for this task
                                                        current_image = response["images"][i]
                                                        
                                                        task['loading'].visible = False
                                                        task['img'].set_source(current_image["url"])
                                                        task['img'].visible = True
                                                        
                                                        # Generate a guaranteed unique ID for each image
                                                        image_uuid = f"img_{int(time.time())}_{i}"
                                                            
                                                        # Add to lightbox with prompts
                                                        lightbox.add_image(
                                                            thumb_url=current_image["url"],
                                                            orig_url=current_image["url"],
                                                            image_id=image_uuid,
                                                            original_prompt=current_image.get("original_prompt", current_image.get("description", "")),
                                                            parsed_prompt=current_image.get("parsed_prompt", "")
                                                        )
                                                        
                                                        # Set up click handler - update to use the lightbox
                                                        task['button'].on('click', lambda url=current_image["url"]: lightbox._open(url))
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
                                                                            with ui.card().classes('w-[120px] p-1 bg-gray-800'):
                                                                                # Extract UUID from URL path for image ID
                                                                                try:
                                                                                    image_uuid = image_url.split('/')[-1].split('.')[0]
                                                                                except:
                                                                                    from datetime import datetime
                                                                                    image_uuid = f"img_{int(datetime.now().timestamp())}"
                                                                                
                                                                                # Get scene prompt if available
                                                                                parsed_prompt = scene.get('prompt', '') if isinstance(scene, dict) else str(scene)
                                                                                
                                                                                # Add to lightbox with ID and prompts
                                                                                img = lightbox.add_image(
                                                                                    thumb_url=image_url,
                                                                                    orig_url=image_url,
                                                                                    image_id=image_uuid,
                                                                                    original_prompt=original_tag,
                                                                                    parsed_prompt=parsed_prompt
                                                                                )
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

    # Function to toggle test mode - moved inside content() function to fix nonlocal binding
    def toggle_test_mode(value):
        nonlocal test_mode
        test_mode = value
        ui.notify(
            f"Test mode {'enabled' if test_mode else 'disabled'}. " +
            ("Responses will echo input without calling the LLM." if test_mode else "Using normal LLM processing."),
            type='info' if test_mode else 'positive',
            timeout=3000
        )