from nicegui import ui, app, events
from app.models.prompt_models import PromptManager, PromptType
from app.core.memory_system import MemorySystem
from app.core.prompt_builder import PromptBuilder
from functools import partial
import json
import os
from pathlib import Path
from app.core.image_scene_parser import ImageSceneParser
from app.core.image_generator import ImageGenerator
import asyncio
from typing import List

class Lightbox:
    """A thumbnail gallery where each image can be clicked to enlarge."""
    def __init__(self) -> None:
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            ui.keyboard(self._handle_key)
            self.large_image = ui.image().props('no-spinner fit=scale-down')
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
        image_index = self.image_list.index(self.large_image.source)
        if event_args.key.arrow_left and image_index > 0:
            self._open(self.image_list[image_index - 1])
        if event_args.key.arrow_right and image_index < len(self.image_list) - 1:
            self._open(self.image_list[image_index + 1])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        self.dialog.open()

def save_prompt(name, type_value, text_area):
    prompt_manager = PromptManager()
    success = prompt_manager.update_prompt(name, type_value, text_area.value)
    if success:
        ui.notify(f"Saved prompt: {name}")
    else:
        ui.notify(f"Error saving prompt: {name}", color="negative")

def reset_prompt(name, type_value, text_area):
    prompt_manager = PromptManager()
    prompt_manager.reset_to_default(name, type_value)
    
    # Fetch the reset prompt
    prompt = prompt_manager.get_prompt(name, type_value)
    if prompt:
        text_area.value = prompt["content"]
        ui.notify(f"Reset prompt: {name}")
    else:
        ui.notify(f"Error resetting prompt: {name}", color="negative")

def preview_system_prompt():
    """Generate and display a preview of the combined system prompt"""
    preview_dialog = ui.dialog()
    with preview_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### System Prompt Preview")
            
            # Build a preview of the system prompt
            preview_text = PromptBuilder.build_system_message(
                relevant_memories=["Example memory 1", "Example memory 2"],
                current_mood="curious and engaged",
                world_state={"location": "AI lab", "description": "A high-tech environment with computers"}
            )
            
            # Display the preview in a monospace font with good formatting
            with ui.scroll_area().classes('h-96 w-full'):
                ui.markdown(f"```\n{preview_text}\n```").classes('w-full')
                
            ui.button('Close', on_click=preview_dialog.close).classes('self-end')
    
    preview_dialog.open()

def display_memory_data():
    """Display memory data in a dialog window"""
    memory_system = MemorySystem()
    memory_dialog = ui.dialog()
    
    with memory_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Memory System Data")
            
            with ui.tabs().classes('w-full') as tabs:
                conversations_tab = ui.tab('Conversations')
                thoughts_tab = ui.tab('Thoughts')
                emotions_tab = ui.tab('Emotions')
                
            with ui.tab_panels(tabs, value=conversations_tab).classes('w-full'):
                # Conversations Panel
                with ui.tab_panel(conversations_tab):
                    recent_conversations = memory_system.get_recent_conversation(10)
                    
                    if recent_conversations:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for message in recent_conversations:
                                with ui.card().classes('q-mb-sm'):
                                    role_color = "primary" if message["role"] == "assistant" else "secondary"
                                    ui.label(f"Role: {message['role']}").classes(f'text-bold text-{role_color}')
                                    ui.separator()
                                    ui.markdown(message["content"])
                    else:
                        ui.label("No conversation data found").classes('text-italic')
                
                # Thoughts Panel
                with ui.tab_panel(thoughts_tab):
                    recent_thoughts = memory_system.get_recent_thoughts(10)
                    
                    if recent_thoughts:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for thought in recent_thoughts:
                                with ui.card().classes('q-mb-sm'):
                                    ui.label(f"Importance: {thought['importance']}").classes('text-bold')
                                    ui.label(f"Time: {thought['timestamp']}").classes('text-caption')
                                    ui.separator()
                                    ui.markdown(thought["content"])
                    else:
                        ui.label("No thoughts data found").classes('text-italic')
                
                # Emotions Panel
                with ui.tab_panel(emotions_tab):
                    recent_emotions = memory_system.get_recent_emotions(10)
                    
                    if recent_emotions:
                        with ui.scroll_area().classes('h-96 w-full'):
                            for emotion in recent_emotions:
                                with ui.card().classes('q-mb-sm'):
                                    ui.label(f"Mood: {emotion['mood']}").classes('text-bold')
                                    ui.label(f"Intensity: {emotion['intensity']}").classes('text-caption')
                                    ui.label(f"Time: {emotion['timestamp']}").classes('text-caption')
                    else:
                        ui.label("No emotions data found").classes('text-italic')
            
            ui.button('Close', on_click=memory_dialog.close).classes('self-end')
    
    memory_dialog.open()

def check_memory_tables():
    """Check if memory tables exist and show their structure"""
    memory_system = MemorySystem()
    tables_dialog = ui.dialog()
    
    with tables_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Database Tables")
            
            # Get DB info - modify the memory_system to add a method that returns this info
            # For now, we'll just show a placeholder
            with ui.scroll_area().classes('h-96 w-full'):
                ui.markdown("""```sql
-- Conversations Table
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Thoughts Table
CREATE TABLE IF NOT EXISTS thoughts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    embedding BLOB,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Emotions Table
CREATE TABLE IF NOT EXISTS emotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mood TEXT NOT NULL,
    intensity REAL DEFAULT 1.0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Relationships Table
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    parameter TEXT NOT NULL,
    value TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```""")
            
            ui.button('Close', on_click=tables_dialog.close).classes('self-end')
    
    tables_dialog.open()

def initialize_memory_system():
    """Initialize the memory system tables and show result"""
    memory_system = MemorySystem()
    result = memory_system.initialize_tables()
    
    if result:
        ui.notify("Memory tables initialized successfully", color="positive")
    else:
        ui.notify("Error initializing memory tables", color="negative")

def view_logs():
    """Display logs in a dialog window"""
    logs_dir = Path('logs')
    log_files = list(logs_dir.glob('*.log'))
    
    if not log_files:
        ui.notify("No log files found", color="warning")
        return
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    logs_dialog = ui.dialog()
    with logs_dialog:
        with ui.card().classes('w-full'):
            ui.markdown("### Application Logs")
            
            # Create a dropdown to select log file
            log_select = ui.select(
                [str(file.name) for file in log_files],
                value=str(log_files[0].name),
                label="Select Log File"
            )
            
            # Display log contents in a scroll area
            log_content_area = ui.scroll_area().classes('h-96 w-full font-mono')
            
            async def load_log_content(e):
                selected_log = logs_dir / log_select.value
                try:
                    with open(selected_log, 'r') as f:
                        content = f.read()
                    
                    with log_content_area:
                        log_content_area.clear()
                        ui.markdown(f"```\n{content}\n```")
                except Exception as ex:
                    ui.notify(f"Error loading log: {str(ex)}", color="negative")
            
            # Initial load
            load_log_content(None)
            
            # Update when selection changes
            log_select.on_value_change(load_log_content)
            
            ui.button('Close', on_click=logs_dialog.close).classes('self-end')
    
    logs_dialog.open()

def test_image_generator_parser():
    """Test the image generator and scene parser together"""
    # Initialize components
    memory_system = MemorySystem()
    image_scene_parser = ImageSceneParser()
    image_generator = ImageGenerator()
    lightbox = Lightbox()
    
    with ui.card().classes('w-full p-4'):
        ui.label('Test Image Generation').classes('text-xl font-bold mb-4')
        
        # Test input area
        with ui.card().classes('w-full p-3 mb-4 bg-gray-800'):
            ui.label('Enter a response with visual descriptions:').classes('text-sm mb-2')
            test_input = ui.textarea(placeholder='Enter text with visual descriptions...').classes('w-full bg-gray-800 border-none')
        
        # Results area
        results_container = ui.column().classes('w-full')
        
        async def generate_images(scenes):
            """Generate images for each scene in parallel"""
            with results_container:
                ui.label('Parsed Scenes').classes('text-h6 q-mt-md')
                for scene in scenes:
                    with ui.card().classes('q-mb-sm q-pa-sm bg-dark'):
                        ui.label(scene['content'] if isinstance(scene, dict) else scene).classes('text-body2')
                
                ui.separator()
                
                # Then start image generation
                ui.label('Generated Images').classes('text-h6 q-mt-md')
                with ui.row().classes('q-gutter-md flex-wrap'):
                    # Create a list to store image generation tasks
                    tasks = []
                    containers = []
                    lightbox = Lightbox()
                    
                    # First create all UI containers
                    for scene in scenes:
                        try:
                            scene_content = scene['content'] if isinstance(scene, dict) else scene
                            
                            # Create a card for each image
                            with ui.card().classes('q-pa-xs'):
                                loading = ui.spinner('default', size='xl').props('color=primary')
                                container = ui.button().props('flat dense').classes('w-[300px] h-[400px] overflow-hidden')
                                with container:
                                    img = ui.image().props('fit=cover').classes('w-full h-full')
                                    img.visible = False
                                
                                with ui.row().classes('items-center justify-between q-mt-xs'):
                                    desc = scene_content[:30] + "..." if len(scene_content) > 30 else scene_content
                                    ui.label(desc).classes('text-caption text-grey-5 ellipsis')
                                
                                tasks.append({
                                    'scene': scene_content,
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
                        scene_contents = [task['scene'] for task in tasks]
                        print(f"Generating {len(scene_contents)} images in parallel...")
                        
                        # Generate all images at once
                        image_urls = await image_generator.generate_parallel(scene_contents)
                        
                        # Update UI only once after all images are generated
                        for i, (task, image_url) in enumerate(zip(tasks, image_urls)):
                            if image_url:
                                print(f"Successfully generated image {i+1}: {image_url}")
                                task['loading'].visible = False
                                task['img'].set_source(image_url)
                                task['img'].visible = True
                                lightbox.image_list.append(image_url)
                                task['button'].on('click', lambda url=image_url: lightbox._open(url))
                            else:
                                task['loading'].visible = False
                                ui.label('Generation failed').classes('text-caption text-negative')
                    
                    except Exception as e:
                        print(f"Error in parallel generation: {str(e)}")
                        ui.notify(f"Error generating images: {str(e)}", type='negative')
        
        async def run_test(e):
            """Run the test with the current input"""
            try:
                # Get current appearance from memory system
                current_appearance = memory_system.get_recent_appearances(1)
                current_appearance_text = current_appearance[0]["description"] if current_appearance else None
                current_mood = memory_system.get_current_mood()
                
                # Extract image tags from input
                import re
                image_pattern = r'<image>(.*?)</image>'
                image_tags = re.findall(image_pattern, test_input.value, re.DOTALL)
                
                if not image_tags:
                    with results_container:
                        ui.label("No <image> tags found in the input").classes('text-gray-400')
                    return
                
                # Format image contents with context and sequence
                image_context = {
                    "appearance": current_appearance_text,
                    "mood": current_mood,
                    "images": [{"content": tag.strip(), "sequence": i+1} for i, tag in enumerate(image_tags)]
                }
                
                # Process through image parser
                parsed_scenes = image_scene_parser.parse_images(
                    json.dumps(image_context),
                    current_appearance=current_appearance_text
                )
                
                # Clear previous results
                results_container.clear()
                
                if parsed_scenes and len(parsed_scenes) > 0:
                    await generate_images(parsed_scenes)
                else:
                    with results_container:
                        ui.label("No visual scenes found in the input").classes('text-gray-400')
                        # Log the input and context for debugging
                        print(f"Input text: {test_input.value}")
                        print(f"Image context: {json.dumps(image_context, indent=2)}")
                        print(f"Parsed scenes: {parsed_scenes}")
            except Exception as e:
                ui.notify(f"Error: {str(e)}", color='negative')
                print(f"Full error: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # Run test button
        ui.button('Run Test', on_click=run_test).props('icon=play_arrow color=purple')

def content() -> None:
    prompt_manager = PromptManager()
    memory_system = MemorySystem()
    
    with ui.card().classes('w-full'):
        ui.markdown("**Memory System**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Check Database Tables', on_click=check_memory_tables).props('outline')
            ui.button('Initialize Memory System', on_click=initialize_memory_system).props('color="primary"')
            ui.button('View Memory Data', on_click=display_memory_data).props('color="secondary"')

    ui.separator()
    
    # Logging and Diagnostics Section
    with ui.card().classes('w-full'):
        ui.markdown("**Logging and Diagnostics**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('View Logs', on_click=view_logs).props('color="info"')
            ui.button('Clear Logs', on_click=lambda: ui.notify("Not implemented yet")).props('outline')

    ui.separator()
    
    # Image Generator & Parser Test Section
    with ui.card().classes('w-full'):
        ui.markdown("**Image Generator & Parser Test**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('Test Image Generator & Parser', on_click=test_image_generator_parser).props('color="primary"')

    ui.separator()
    
    # Prompt Editor Section
    with ui.card().classes('w-full'):
        ui.markdown("**Prompt Editor**")
        
        # Add a preview button for the combined system prompt
        with ui.row().classes('justify-end w-full'):
            ui.button('Preview Combined System Prompt', on_click=preview_system_prompt).props('outline')
        
        # Create tabs for different prompt types
        with ui.tabs().classes('w-full') as tabs:
            system_tab = ui.tab('System')
            personality_tab = ui.tab('Personality')
            appearance_tab = ui.tab('Appearance')
            instructions_tab = ui.tab('Instructions')
            parser_tab = ui.tab('Parser')
            template_tab = ui.tab('Template')
        
        with ui.tab_panels(tabs, value=system_tab).classes('w-full'):
            # System Prompt Panel
            with ui.tab_panel(system_tab):
                system_prompt = prompt_manager.get_prompt("base_system", PromptType.SYSTEM.value)
                if system_prompt:
                    with ui.column().classes('gap-2 w-full'):
                        ui.label('Edit System Prompt').classes('text-lg font-bold')
                        ui.label(system_prompt["description"]).classes('text-md text-gray-500')
                        ui.label('This defines the core identity of the AI').classes('text-sm text-gray-500')
                        system_textarea = ui.textarea(value=system_prompt["content"])\
                            .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                            .props('wrap="soft" auto-grow')
                        
                        with ui.row().classes('gap-2'):
                            ui.button('Save', on_click=partial(save_prompt, "base_system", PromptType.SYSTEM.value, system_textarea))\
                                .props('color="primary"')
                            ui.button('Reset to Default', on_click=partial(reset_prompt, "base_system", PromptType.SYSTEM.value, system_textarea))\
                                .props('outline color="grey"')
            
            # Personality Panel
            with ui.tab_panel(personality_tab):
                personality_prompt = prompt_manager.get_prompt("personality", PromptType.PERSONALITY.value)
                if personality_prompt:
                    with ui.column().classes('gap-2 w-full'):
                        ui.label('Edit Personality').classes('text-lg font-bold')
                        ui.label(personality_prompt["description"]).classes('text-md text-gray-500')
                        ui.label('This defines behavioral traits and characteristics').classes('text-sm text-gray-500')
                        personality_textarea = ui.textarea(value=personality_prompt["content"])\
                            .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                            .props('wrap="soft" auto-grow')
                        
                        with ui.row().classes('gap-2'):
                            ui.button('Save', on_click=partial(save_prompt, "personality", PromptType.PERSONALITY.value, personality_textarea))\
                                .props('color="primary"')
                            ui.button('Reset to Default', on_click=partial(reset_prompt, "personality", PromptType.PERSONALITY.value, personality_textarea))\
                                .props('outline color="grey"')
            
            # Appearance Panel
            with ui.tab_panel(appearance_tab):
                appearance_prompt = prompt_manager.get_prompt("appearance", PromptType.APPEARANCE.value)
                if appearance_prompt:
                    with ui.column().classes('gap-2 w-full'):
                        ui.label('Edit Appearance').classes('text-lg font-bold')
                        ui.label(appearance_prompt["description"]).classes('text-md text-gray-500')
                        ui.label('This defines how the AI visualizes itself').classes('text-sm text-gray-500')
                        appearance_textarea = ui.textarea(value=appearance_prompt["content"])\
                            .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                            .props('wrap="soft" auto-grow')
                        
                        with ui.row().classes('gap-2'):
                            ui.button('Save', on_click=partial(save_prompt, "appearance", PromptType.APPEARANCE.value, appearance_textarea))\
                                .props('color="primary"')
                            ui.button('Reset to Default', on_click=partial(reset_prompt, "appearance", PromptType.APPEARANCE.value, appearance_textarea))\
                                .props('outline color="grey"')
            
            # Instructions Panel
            with ui.tab_panel(instructions_tab):
                instructions_prompt = prompt_manager.get_prompt("instructions", PromptType.INSTRUCTIONS.value)
                if instructions_prompt:
                    with ui.column().classes('gap-2 w-full'):
                        ui.label('Edit Instructions').classes('text-lg font-bold')
                        ui.label(instructions_prompt["description"]).classes('text-md text-gray-500')
                        ui.label('This defines special tags and formatting instructions').classes('text-sm text-gray-500')
                        instructions_textarea = ui.textarea(value=instructions_prompt["content"])\
                            .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                            .props('wrap="soft" auto-grow')
                        
                        with ui.row().classes('gap-2'):
                            ui.button('Save', on_click=partial(save_prompt, "instructions", PromptType.INSTRUCTIONS.value, instructions_textarea))\
                                .props('color="primary"')
                            ui.button('Reset to Default', on_click=partial(reset_prompt, "instructions", PromptType.INSTRUCTIONS.value, instructions_textarea))\
                                .props('outline color="grey"')
            
            # Parser Panel
            with ui.tab_panel(parser_tab):
                with ui.tabs().classes('w-full') as parser_tabs:
                    image_parser_tab = ui.tab('Image Scene Parser')
                    response_parser_tab = ui.tab('Response Parser')
                
                with ui.tab_panels(parser_tabs, value=image_parser_tab).classes('w-full'):
                    # Image Scene Parser Panel
                    with ui.tab_panel(image_parser_tab):
                        image_parser_prompt = prompt_manager.get_prompt("image_scene_parser", PromptType.IMAGE_PARSER.value)
                        if image_parser_prompt:
                            with ui.column().classes('gap-2 w-full'):
                                ui.label('Edit Image Scene Parser').classes('text-lg font-bold')
                                ui.label(image_parser_prompt["description"]).classes('text-md text-gray-500')
                                ui.label('This defines how to parse visual scenes from responses').classes('text-sm text-gray-500')
                                image_parser_textarea = ui.textarea(value=image_parser_prompt["content"])\
                                    .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                                    .props('wrap="soft" auto-grow')
                                
                                with ui.row().classes('gap-2'):
                                    ui.button('Save', on_click=partial(save_prompt, "image_scene_parser", PromptType.IMAGE_PARSER.value, image_parser_textarea))\
                                        .props('color="primary"')
                                    ui.button('Reset to Default', on_click=partial(reset_prompt, "image_scene_parser", PromptType.IMAGE_PARSER.value, image_parser_textarea))\
                                        .props('outline color="grey"')
                    
                    # Response Parser Panel
                    with ui.tab_panel(response_parser_tab):
                        response_parser_prompt = prompt_manager.get_prompt("response_parser", PromptType.RESPONSE_PARSER.value)
                        if response_parser_prompt:
                            with ui.column().classes('gap-2 w-full'):
                                ui.label('Edit Response Parser').classes('text-lg font-bold')
                                ui.label(response_parser_prompt["description"]).classes('text-md text-gray-500')
                                ui.label('This defines how to parse thoughts, mood, and appearance changes').classes('text-sm text-gray-500')
                                response_parser_textarea = ui.textarea(value=response_parser_prompt["content"])\
                                    .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                                    .props('wrap="soft" auto-grow')
                                
                                with ui.row().classes('gap-2'):
                                    ui.button('Save', on_click=partial(save_prompt, "response_parser", PromptType.RESPONSE_PARSER.value, response_parser_textarea))\
                                        .props('color="primary"')
                                    ui.button('Reset to Default', on_click=partial(reset_prompt, "response_parser", PromptType.RESPONSE_PARSER.value, response_parser_textarea))\
                                        .props('outline color="grey"')
            
            # Template Panel
            with ui.tab_panel(template_tab):
                template_prompt = prompt_manager.get_prompt("chat_template", PromptType.TEMPLATE.value)
                if template_prompt:
                    with ui.column().classes('gap-2 w-full'):
                        ui.label('Edit Chat Template').classes('text-lg font-bold')
                        ui.label(template_prompt["description"]).classes('text-md text-gray-500')
                        ui.label('This is a Jinja2 template for formatting chat messages').classes('text-sm text-gray-500')
                        template_textarea = ui.textarea(value=template_prompt["content"])\
                            .classes('w-full h-96 font-mono text-sm bg-[#1a1a1a] text-white')\
                            .props('wrap="soft" auto-grow')
                        
                        with ui.row().classes('gap-2'):
                            ui.button('Save', on_click=partial(save_prompt, "chat_template", PromptType.TEMPLATE.value, template_textarea))\
                                .props('color="primary"')
                            ui.button('Reset to Default', on_click=partial(reset_prompt, "chat_template", PromptType.TEMPLATE.value, template_textarea))\
                                .props('outline color="grey"')
    
    # Rest of your UI components...
