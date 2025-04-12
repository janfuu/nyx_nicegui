from nicegui import ui
from ..services.chat_pipeline import ChatPipeline
import time
import asyncio
from ..core.memory_system import MemorySystem
import httpx

# Initialize the chat pipeline
chat_pipeline = ChatPipeline()

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    
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
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                # Store reference to portrait image
                portrait_path = 'app/assets/images/portrait.jpg'
                portrait_ref = ui.image(portrait_path).classes('w-full rounded-xl')
                
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
                    dialog = ui.dialog()
                    with dialog:
                        with ui.card().classes('w-full max-w-3xl'):
                            ui.label('Image Details').classes('text-xl font-bold mb-2')
                            ui.image(image_data["url"]).classes('w-full rounded-lg mb-4')
                            ui.label('Original Prompt:').classes('font-bold')
                            ui.markdown(image_data["description"]).classes('bg-[#1a1a1a] p-3 rounded mb-4')
                            
                            with ui.row().classes('justify-between w-full'):
                                ui.button('Set as Portrait', 
                                        on_click=lambda: set_as_portrait(image_data["url"]))\
                                    .props('icon=face color=purple').classes('mr-2')
                                ui.button('Close', on_click=dialog.close)
                    dialog.open()
                
                # Message input and send button
                with ui.row().classes('gap-4 mt-auto w-full'):
                    msg_input = ui.input(placeholder='Type a message...').classes('flex-1 bg-[#1f1f1f] text-white')
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
                                response = await chat_pipeline.process_message(current_message)
                                
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
                                        
                                        # Display any self actions (appearance updates)
                                        if response.get("self"):
                                            ui.separator().classes('my-2')
                                            with ui.expansion('APPEARANCE', icon='face').classes('w-full'):
                                                for self_action in response["self"]:
                                                    ui.markdown(f"*{self_action}*").classes('text-purple-300 text-sm italic pl-4')
                                                    appearance_display.content = self_action
                                        
                                        # Add Visualize button for on-demand image generation
                                        ui.separator().classes('my-2')
                                        with ui.row().classes('justify-between w-full'):
                                            visualize_button = ui.button('Visualize', icon='image')\
                                                .props('color=purple').classes('mr-2')
                                            
                                            async def visualize_response():
                                                visualize_button.props('loading')
                                                try:
                                                    # Generate images for the response
                                                    images = await chat_pipeline.generate_images(response['text'])
                                                    
                                                    if images and len(images) > 0:  # Check both that images exists and has items
                                                        # Display generated images
                                                        with ui.expansion('GENERATED IMAGES', icon='image').classes('w-full'):
                                                            with ui.row().classes('flex-wrap gap-2 w-full'):
                                                                for image_data in images:
                                                                    if isinstance(image_data, dict) and "url" in image_data and "description" in image_data:
                                                                        with ui.card().classes('w-[180px] p-1 bg-gray-800'):
                                                                            img = ui.image(image_data["url"]).classes('w-full rounded-lg cursor-pointer')
                                                                            img.on('click', lambda d=image_data: show_image_details(d))
                                                                            
                                                                            with ui.row().classes('items-center justify-between w-full mt-1'):
                                                                                short_desc = image_data["description"][:30] + ("..." if len(image_data["description"]) > 30 else "")
                                                                                ui.label(short_desc).classes('text-xs italic text-gray-300 truncate max-w-[75%]')
                                                                                ui.button(icon='search', on_click=lambda d=image_data: show_image_details(d))\
                                                                                    .props('flat dense round').classes('text-xs')
                                                    else:
                                                        ui.notify('No visual scenes found in the response', color='warning')
                                                except Exception as e:
                                                    ui.notify(f'Failed to generate images: {str(e)}', color='negative', timeout=5000)
                                                    print(f"Image generation error: {str(e)}")  # Log the full error
                                                finally:
                                                    visualize_button.props('loading=false')
                                            
                                            visualize_button.on('click', visualize_response)
                                
                                # Update appearance display if provided
                                if response.get("self") and len(response["self"]) > 0:
                                    appearance_display.content = response["self"][-1]  # Show the most recent appearance update
                                    
                            except Exception as e:
                                # Handle errors
                                with chat_box:
                                    ui.label(f"Error: {str(e)}").classes('self-start bg-red-800 p-2 rounded-lg mb-2')
                                    
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
        with ui.card().classes('flex-1'):
            with ui.column().classes('gap-4 w-full'):
                # Location image
                location_image = ui.image('assets/images/location.png').classes('w-full rounded-xl')
                
                # Location description
                location_desc = ui.label('cyberpunk apartment interior at night... synthwave color palette').classes('text-xs text-gray-400')
                
                # Add controls for world management
                ui.button('Change Location', on_click=lambda: ui.notify('Location change functionality to be implemented')).classes('mt-4')