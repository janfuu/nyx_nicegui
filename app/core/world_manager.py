from app.models.database import Database

class WorldManager:
    def __init__(self):
        self._current_state = {
            "location": "Default Location",
            "description": "",
            "image": ""
        }

    def get_current_state(self):
        return self._current_state

    def update_location(self, name, description, image):
        self._current_state["location"] = name
        self._current_state["description"] = description
        self._current_state["image"] = image

    def update_world_state(self, event):
        # Use specialized model for world updates
        world_provider = self.config.get("llm", "world_provider", None)
        world_model = self.config.get("llm", "world_model", None)
        
        response = self.llm.generate_response(
            system_prompt="You update the world state based on events",
            user_message=f"Event: {event}",
            provider=world_provider,
            model=world_model
        )
        # Process response...