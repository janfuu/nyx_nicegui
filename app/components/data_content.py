from nicegui import ui, app
from random import random
from app.core.memory_system import MemorySystem
from app.core.response_parser import ResponseParser
import json
import time

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    
    # Get current state
    current_mood = memory_system.get_current_mood()
    current_appearances = memory_system.get_recent_appearances(1)
    current_appearance = current_appearances[0]["description"] if current_appearances else "No appearance set"
    current_clothing = memory_system.get_recent_clothing(1)
    current_clothing_text = current_clothing[0]["description"] if current_clothing else "No clothing set"
    
    # Add new Raw State Management tab
    with ui.tabs().classes('w-full') as tabs:
        standard_tab = ui.tab('Standard Controls')
        raw_state_tab = ui.tab('Raw State Editor')
    
    with ui.tab_panels(tabs, value=standard_tab).classes('w-full'):
        # Standard Controls Panel
        with ui.tab_panel(standard_tab):
            # Mood Section
            with ui.card().classes('w-full'):
                ui.markdown("**Current Mood**")
                
                with ui.row().classes('w-full items-center gap-4'):
                    mood_display = ui.markdown(current_mood).classes('text-lg')
                    
                    def update_mood():
                        # Store in memory system
                        memory_system.update_mood(mood_input.value)
                        # Get fresh value from memory system
                        current_mood = memory_system.get_current_mood()
                        mood_display.content = current_mood
                        ui.notify('Mood updated successfully!', color='positive')
                    
                    mood_input = ui.input(placeholder='Enter new mood...').classes('flex-1')
                    ui.button('Update Mood', on_click=update_mood).props('color=primary')
            
            ui.separator()
            
            # Appearance Section
            with ui.card().classes('w-full'):
                ui.markdown("**Current Appearance**")
                
                with ui.column().classes('w-full gap-4'):
                    # Ensure we get the latest appearance from memory system
                    appearance_display = ui.markdown(current_appearance).classes('text-lg')
                    
                    def update_appearance():
                        # Store in memory system
                        memory_system.add_appearance(appearance_input.value)
                        # Get fresh value from memory system
                        current_appearances = memory_system.get_recent_appearances(1)
                        if current_appearances:
                            appearance_display.content = current_appearances[0]["description"]
                        ui.notify('Appearance updated successfully!', color='positive')
                    
                    # Add refresh button to reload
                    with ui.row().classes('w-full justify-between items-center'):
                        appearance_input = ui.textarea(placeholder='Enter new appearance description...').classes('flex-grow')
                        
                        def refresh_appearance():
                            current_appearances = memory_system.get_recent_appearances(1)
                            if current_appearances:
                                appearance_display.content = current_appearances[0]["description"]
                                ui.notify('Appearance refreshed', color='info')
                            else:
                                ui.notify('No appearance data found', color='warning')
                        
                        ui.button(icon='refresh', on_click=refresh_appearance).props('flat').tooltip('Refresh')
                    
                    ui.button('Update Appearance', on_click=update_appearance).props('color=primary')
            
            ui.separator()
            
            # Clothing Section
            with ui.card().classes('w-full'):
                ui.markdown("**Current Clothing**")
                
                with ui.column().classes('w-full gap-4'):
                    # Ensure we get the latest clothing from memory system
                    clothing_display = ui.markdown(current_clothing_text).classes('text-lg')
                    
                    def update_clothing():
                        # Store in memory system
                        memory_system.add_clothing(clothing_input.value)
                        # Get fresh value from memory system
                        current_clothing = memory_system.get_recent_clothing(1)
                        if current_clothing:
                            clothing_display.content = current_clothing[0]["description"]
                        ui.notify('Clothing updated successfully!', color='positive')
                    
                    # Add refresh button to reload
                    with ui.row().classes('w-full justify-between items-center'):
                        clothing_input = ui.textarea(placeholder='Enter new clothing description...').classes('flex-grow')
                        
                        def refresh_clothing():
                            current_clothing = memory_system.get_recent_clothing(1)
                            if current_clothing:
                                clothing_display.content = current_clothing[0]["description"]
                                ui.notify('Clothing refreshed', color='info')
                            else:
                                ui.notify('No clothing data found', color='warning')
                        
                        ui.button(icon='refresh', on_click=refresh_clothing).props('flat').tooltip('Refresh')
                    
                    ui.button('Update Clothing', on_click=update_clothing).props('color=primary')
            
            ui.separator()
            
            # Location Section
            with ui.card().classes('w-full'):
                ui.markdown("**Current Location**")
                
                with ui.row().classes('w-full items-center gap-4'):
                    # Get current location from database
                    current_location = memory_system.get_recent_locations(1)
                    current_location_text = current_location[0]["description"] if current_location else "No location set"
                    location_display = ui.markdown(current_location_text).classes('text-lg')
                    
                    def update_location():
                        # Store in database using add_location
                        memory_system.add_location(location_input.value)
                        # Also update the current location
                        memory_system.update_location(location_input.value)
                        # Get fresh value from memory system
                        current_location = memory_system.get_recent_locations(1)
                        if current_location:
                            location_display.content = current_location[0]["description"]
                        ui.notify('Location updated successfully!', color='positive')
                    
                    location_input = ui.input(placeholder='Enter new location...').classes('flex-1')
                    ui.button('Update Location', on_click=update_location).props('color=primary')
        
        # Raw State Editor Panel
        with ui.tab_panel(raw_state_tab):
            with ui.card().classes('w-full'):
                ui.markdown("**Character State (Raw JSON Editor)**")
                ui.markdown("This editor allows you to directly manage the character state as a JSON object. "
                         "Changes here will be reflected immediately throughout the system.").classes('text-sm')
                
                # Initialize state editor
                current_state = memory_system.get_character_state()
                state_json = json.dumps(current_state, indent=2)
                
                state_editor = ui.textarea(value=state_json).classes('w-full h-96 font-mono')
                
                def update_state():
                    try:
                        # Parse the JSON
                        new_state = json.loads(state_editor.value)
                        
                        # Update each key individually to avoid overwriting the entire state
                        for key, value in new_state.items():
                            if key not in current_state or current_state[key] != value:
                                memory_system.state_manager.set(key, value)
                        
                        ui.notify('State updated successfully!', color='positive')
                        
                        # Update the editor with fresh state (in case there were any changes)
                        refresh_state_editor()
                    except json.JSONDecodeError as e:
                        ui.notify(f'Invalid JSON: {str(e)}', color='negative')
                    except Exception as e:
                        ui.notify(f'Error updating state: {str(e)}', color='negative')
                
                def refresh_state_editor():
                    nonlocal current_state
                    current_state = memory_system.get_character_state()
                    state_editor.value = json.dumps(current_state, indent=2)
                    ui.notify('State editor refreshed', color='info')
                
                with ui.row().classes('w-full justify-between'):
                    ui.button('Update State', on_click=update_state).props('color=primary')
                    ui.button('Refresh', on_click=refresh_state_editor, icon='refresh').props('outline')
                    
                ui.markdown("""#### Available State Keys

Common state keys include:
- `mood`: Character's current emotional state
- `appearance`: Physical appearance description
- `clothing`: Current outfit description
- `location`: Current location description

You can also add custom state values as needed.""").classes('text-sm mt-4')
                
                # Database Migration Section
                ui.separator()
                with ui.card().classes('w-full'):
                    ui.markdown("**Database Migration**")
                    ui.markdown("Migrate existing database content to Qdrant memory store").classes('text-sm')
                    
                    # Add progress indicator
                    progress = ui.linear_progress(0).classes('w-full')
                    status = ui.label('Ready to migrate...')
                    
                    async def migrate_to_qdrant():
                        try:
                            # Get all conversations from database
                            conversations = memory_system.get_recent_conversation(1000)  # Get a large number to ensure we get all
                            total = len(conversations)
                            processed = 0
                            
                            # Process each conversation through the parser
                            for conversation in conversations:
                                if conversation["role"] == "assistant":
                                    # Update progress
                                    processed += 1
                                    progress.value = processed / total
                                    status.set_text(f'Processing conversation {processed}/{total}...')
                                    await ui.run_javascript('void(0)')  # Keep UI alive
                                    
                                    # Parse the response to extract memories and other fields
                                    parsed_content = await ResponseParser._llm_parse(conversation["content"])
                                    
                                    # Extract mood from the text if present
                                    mood = "neutral"  # default mood
                                    if "<mood>" in conversation["content"]:
                                        mood_start = conversation["content"].find("<mood>") + len("<mood>")
                                        mood_end = conversation["content"].find("</mood>", mood_start)
                                        if mood_end != -1:
                                            mood = conversation["content"][mood_start:mood_end].strip()
                                    
                                    # Store the entire conversation as a memory
                                    memory = {
                                        "text": conversation["content"],
                                        "type": "chat",
                                        "mood": mood,
                                        "tags": ["first love", "initial conversation"],
                                        "timestamp": conversation.get("timestamp", time.time())
                                    }
                                    
                                    # Get embedding vector for the memory using the text model
                                    vector = memory_system.embedder.text_model.encode(memory["text"]).tolist()
                                    
                                    # Store in Qdrant
                                    await memory_system.qdrant_memory.store_memory(
                                        text=memory["text"],
                                        vector=vector,
                                        memory_type=memory["type"],
                                        mood=memory["mood"],
                                        mood_vector=memory_system.embedder.embed_prompt(memory["mood"]) if memory["mood"] else None,
                                        tags=memory["tags"]
                                    )
                                    
                                    # Store thoughts in Qdrant
                                    if parsed_content.get("thoughts"):
                                        for thought in parsed_content["thoughts"]:
                                            memory_system.add_thought(
                                                content=thought,
                                                importance=5  # Default importance level
                                            )
                            
                            progress.value = 1.0
                            status.set_text('Migration complete!')
                            ui.notify('Successfully migrated conversations to Qdrant', color='positive')
                        except Exception as e:
                            progress.value = 0.0
                            status.set_text('Migration failed!')
                            ui.notify(f'Error during migration: {str(e)}', color='negative')
                    
                    ui.button('Migrate Database to Qdrant', on_click=lambda: migrate_to_qdrant()).props('color=primary')
    
    ui.separator()
    
    # Rest of the page remains unchanged
    with ui.card().classes('w-full'):
        ui.markdown("**Spinner**")
        with ui.row():
            ui.spinner(size='lg')
            ui.spinner('audio', size='lg', color='green')
            ui.spinner('dots', size='lg', color='red')

    ui.separator()
    with ui.card().classes('w-full'):
        ui.markdown("**Chart**")
        chart = ui.highchart({
            'title': False,
            'chart': {'type': 'bar'},
            'xAxis': {'categories': ['A', 'B']},
            'series': [
                {'name': 'Alpha', 'data': [0.1, 0.2]},
                {'name': 'Beta', 'data': [0.3, 0.4]},
            ],
        }).classes('w-full h-64')

        def update():
            chart.options['series'][0]['data'][0] = random()
            chart.update()

        ui.button('Update', on_click=update)

    ui.separator()
    with ui.card().classes('w-full'):
        ui.markdown("**EChart**")
        echart = ui.echart({
            'xAxis': {'type': 'value'},
            'yAxis': {'type': 'category', 'data': ['A', 'B'], 'inverse': True},
            'legend': {'textStyle': {'color': 'gray'}},
            'series': [
                {'type': 'bar', 'name': 'Alpha', 'data': [0.1, 0.2]},
                {'type': 'bar', 'name': 'Beta', 'data': [0.3, 0.4]},
            ],
        })

        def update():
            echart.options['series'][0]['data'][0] = random()
            echart.update()

        ui.button('Update', on_click=update)

    ui.separator()
    with ui.card().classes('w-full'):
        ui.markdown("**Table**")
        
        columns = [
            {'name': 'name', 'label': 'Name', 'field': 'name', 'required': True, 'align': 'left'},
            {'name': 'age', 'label': 'Age', 'field': 'age', 'sortable': True},
        ]
        rows = [
            {'name': 'Elsa', 'age': 18},
            {'name': 'Oaken', 'age': 46},
            {'name': 'Hans', 'age': 20},
            {'name': 'Sven'},
            {'name': 'Olaf', 'age': 4},
            {'name': 'Anna', 'age': 17},
        ]

        ui.table(columns=columns, rows=rows, pagination=3).classes('w-full')

        ui.separator()
