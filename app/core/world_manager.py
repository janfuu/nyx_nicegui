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