from nicegui import ui, app

def content() -> None:
    with ui.row().classes('w-full gap-4 flex-nowrap'):
        # Left Card
        with ui.card().classes('flex-1'):
            with ui.column():
                with ui.row():
                    ui.icon("o_info").classes('text-xl')
                    with ui.element('div').classes('bg-primary'):
                        ui.label("Due to running on a Raspberry Pi, you might experience some slowdowns.").classes('text-white').style("font-size: 12px;").tailwind("pr-2")

                ui.label("Welcome!").classes('text-h6')
                ui.label("This App is build based on the NiceGUI framework - modified and adapted for easyier modularized use.").classes('text-body1')

        # Middle Text Area
        with ui.column().classes('flex-1'):
            ui.html('''
                <p>
                <strong>This could be your application!</strong>
                </p>
                
                <p style="margin-top:4px;">
                Available for Windows, Linux, and MacOS - as server, docker or native desktop app.
                Browse through plenty of live demos.
                Interact with your custom application through buttons, dialogs, 3D scenes, plots and much more. </p>
                <p>

                The Framework manages web development details, letting you focus on backend code for diverse applications, including robotics, IoT solutions, smart home automation, and machine learning. Designed to work smoothly with connected peripherals like webcams and GPIO pins in IoT setups, this framework streamlines the management of all your code in one place.
                </p>

                <p style="margin-top:12px;">
                <strong>This is just a small insight - if you want to know more, please get in touch.</strong>
                </p>
            ''')

        # Right Card
        with ui.card().classes('flex-1'):
            ui.label("Available for:").classes('text-h6')

            with ui.row():
                ui.icon("o_devices").classes('text-3xl')
                with ui.element('div').classes('p-1 bg-primary'):
                    ui.label("Windows | Linux | MacOS ").classes('text-white').style("font-size: 14px;").tailwind("pl-2 pr-2")

            with ui.row():
                ui.icon("o_terminal").classes('text-3xl')
                with ui.element('div').classes('p-1 bg-primary'):
                    ui.label("Desktop | Server | Docker ").classes('text-white').style("font-size: 14px;").tailwind("pl-2 pr-2")

            with ui.row():
                ui.spinner('puff', size='2em', color='positive', thickness=12)
                with ui.column():
                    def system_info_toggle():
                        state = system_info.visible
                        system_info.visible = not state

                    with ui.element('div').classes('p-1 bg-positive').style("border-radius: 10px; cursor: pointer;").on('click', lambda e: system_info_toggle()):
                        ui.label("Running on a Raspberry Pi 5").classes('text-white').style("font-size: 14px;").tailwind("pl-2 pr-2")

                    with ui.element() as system_info:
                        with ui.row():
                            ui.icon("o_info").classes('text-xl')
                            with ui.element('div').classes('bg-primary'):
                                ui.label("Model B Rev 1.0 64-bit").classes('text-white').style("font-size: 12px;").tailwind("pl-2 pr-2")

                        with ui.row():
                            ui.icon("o_memory").classes('text-xl')
                            with ui.element('div').classes('bg-primary'):
                                ui.label("Quad-Core ARM @2.44GHz ").classes('text-white').style("font-size: 12px;").tailwind("pl-2 pr-2")

                        with ui.row():
                            ui.icon("select_all").classes('text-xl')
                            with ui.element('div').classes('bg-primary'):
                                ui.label("8 GB of LPDDR4X RAM").classes('text-white').style("font-size: 12px;").tailwind("pl-2 pr-2")

                        with ui.row():
                            ui.icon("o_storage").classes('text-xl')
                            with ui.element('div').classes('bg-primary'):
                                ui.label("SanDisk 64 GB").classes('text-white').style("font-size: 12px;").tailwind("pl-2 pr-2")

                    system_info.visible = True

            ui.label("This app is designed for desktop use - you may encounter some minor performance issues on mobile devices.").classes('text-caption').tailwind("pt-1")