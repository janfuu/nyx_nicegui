from nicegui import ui, app
from random import random
from app.core.memory_system import MemorySystem

def content() -> None:
    # Initialize memory system
    memory_system = MemorySystem()
    
    # Get current state
    current_mood = memory_system.get_current_mood()
    current_appearances = memory_system.get_recent_appearances(1)
    current_appearance = current_appearances[0]["description"] if current_appearances else "No appearance set"
    
    # Mood Section
    with ui.card().classes('w-full'):
        ui.markdown("**Current Mood**")
        
        with ui.row().classes('w-full items-center gap-4'):
            mood_display = ui.markdown(current_mood).classes('text-lg')
            
            def update_mood():
                memory_system.update_mood(mood_input.value)
                mood_display.content = mood_input.value
                ui.notify('Mood updated successfully!', color='positive')
            
            mood_input = ui.input(placeholder='Enter new mood...').classes('flex-1')
            ui.button('Update Mood', on_click=update_mood).props('color=primary')
    
    ui.separator()
    
    # Appearance Section
    with ui.card().classes('w-full'):
        ui.markdown("**Current Appearance**")
        
        with ui.column().classes('w-full gap-4'):
            appearance_display = ui.markdown(current_appearance).classes('text-lg')
            
            def update_appearance():
                # Store in database using add_appearance
                memory_system.add_appearance(appearance_input.value)
                # Also add to changes list
                memory_system.add_appearance_change(appearance_input.value)
                appearance_display.content = appearance_input.value
                ui.notify('Appearance updated successfully!', color='positive')
            
            appearance_input = ui.textarea(placeholder='Enter new appearance description...').classes('w-full')
            ui.button('Update Appearance', on_click=update_appearance).props('color=primary')
    
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
                location_display.content = location_input.value
                ui.notify('Location updated successfully!', color='positive')
            
            location_input = ui.input(placeholder='Enter new location...').classes('flex-1')
            ui.button('Update Location', on_click=update_location).props('color=primary')

        ui.separator()
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
