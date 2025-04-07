from nicegui import ui, app
from app.models.prompt_models import PromptManager, PromptType
from app.core.memory_system import MemorySystem
from app.core.prompt_builder import PromptBuilder
from functools import partial

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

def content() -> None:
    prompt_manager = PromptManager()
    memory_system = MemorySystem()
    
    with ui.card().classes('w-full'):
        ui.markdown("**Memories**")
        
        with ui.column().classes('gap-1 w-full'):
            ui.button('CHECK TABLE', on_click=lambda: ui.notify('Checking memory table...'))
            ui.button('INIT MEMORY', on_click=lambda: memory_system.initialize_tables())
            ui.button('DEBUG MEMORIES', on_click=lambda: ui.notify(str(memory_system.get_recent_memories(5))))
            ui.button('FORCE MEMORY')

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
                    ui.label('Edit System Prompt').classes('text-lg font-bold')
                    ui.label(system_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This defines the core identity of the AI').classes('text-sm text-gray-500')
                    system_textarea = ui.textarea(system_prompt["content"]).classes('w-full h-64').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "base_system", PromptType.SYSTEM.value, system_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "base_system", PromptType.SYSTEM.value, system_textarea)).props('outline color="grey"')
            
            # Personality Panel
            with ui.tab_panel(personality_tab):
                personality_prompt = prompt_manager.get_prompt("personality", PromptType.PERSONALITY.value)
                if personality_prompt:
                    ui.label('Edit Personality').classes('text-lg font-bold')
                    ui.label(personality_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This defines behavioral traits and characteristics').classes('text-sm text-gray-500')
                    personality_textarea = ui.textarea(personality_prompt["content"]).classes('w-full h-64').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "personality", PromptType.PERSONALITY.value, personality_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "personality", PromptType.PERSONALITY.value, personality_textarea)).props('outline color="grey"')
            
            # Appearance Panel
            with ui.tab_panel(appearance_tab):
                appearance_prompt = prompt_manager.get_prompt("appearance", PromptType.APPEARANCE.value)
                if appearance_prompt:
                    ui.label('Edit Appearance').classes('text-lg font-bold')
                    ui.label(appearance_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This defines how the AI visualizes itself').classes('text-sm text-gray-500')
                    appearance_textarea = ui.textarea(appearance_prompt["content"]).classes('w-full h-64').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "appearance", PromptType.APPEARANCE.value, appearance_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "appearance", PromptType.APPEARANCE.value, appearance_textarea)).props('outline color="grey"')
            
            # Instructions Panel
            with ui.tab_panel(instructions_tab):
                instructions_prompt = prompt_manager.get_prompt("instructions", PromptType.INSTRUCTIONS.value)
                if instructions_prompt:
                    ui.label('Edit Instructions').classes('text-lg font-bold')
                    ui.label(instructions_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This defines special tags and formatting instructions').classes('text-sm text-gray-500')
                    instructions_textarea = ui.textarea(instructions_prompt["content"]).classes('w-full h-64').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "instructions", PromptType.INSTRUCTIONS.value, instructions_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "instructions", PromptType.INSTRUCTIONS.value, instructions_textarea)).props('outline color="grey"')
            
            # Parser Panel
            with ui.tab_panel(parser_tab):
                parser_prompt = prompt_manager.get_prompt("response_parser", PromptType.PARSER.value)
                if parser_prompt:
                    ui.label('Edit Response Parser').classes('text-lg font-bold')
                    ui.label(parser_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This defines how to parse special tags in responses').classes('text-sm text-gray-500')
                    parser_textarea = ui.textarea(parser_prompt["content"]).classes('w-full h-64').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "response_parser", PromptType.PARSER.value, parser_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "response_parser", PromptType.PARSER.value, parser_textarea)).props('outline color="grey"')
            
            # Template Panel
            with ui.tab_panel(template_tab):
                template_prompt = prompt_manager.get_prompt("chat_template", PromptType.TEMPLATE.value)
                if template_prompt:
                    ui.label('Edit Chat Template').classes('text-lg font-bold')
                    ui.label(template_prompt["description"]).classes('text-md text-gray-500')
                    ui.label('This is a Jinja2 template for formatting chat messages').classes('text-sm text-gray-500')
                    template_textarea = ui.textarea(template_prompt["content"]).classes('w-full h-64 font-mono').props('wrap="word"')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('Save', on_click=partial(save_prompt, "chat_template", PromptType.TEMPLATE.value, template_textarea)).props('color="primary"')
                        ui.button('Reset to Default', on_click=partial(reset_prompt, "chat_template", PromptType.TEMPLATE.value, template_textarea)).props('outline color="grey"')
    
    # Rest of your UI components...
