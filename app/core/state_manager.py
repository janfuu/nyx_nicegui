import json
from app.models.database import Database
from app.utils.logger import Logger

class StateManager:
    """
    StateManager handles character state as a simple key-value store with persistence.
    This provides a cleaner, more flexible approach than individual database tables.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db = Database()
        self.logger = Logger()
        self._state = {
            "mood": "neutral",
            "appearance": "A young woman with cybernetic enhancements, circuits glowing faintly beneath her skin...",
            "clothing": "Simple, form-fitting black bodysuit with glowing blue circuit patterns...",
            "location": "cyberpunk apartment interior at night... synthwave color palette"
        }
        self._load_from_db()
        self._initialized = True
    
    def _load_from_db(self):
        """Load the latest state from database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if the state table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='character_state'")
            if not cursor.fetchone():
                self._create_state_table()
                self._save_to_db()  # Save initial state
                return
            
            # Get the latest state entry
            cursor.execute("SELECT state_json FROM character_state ORDER BY timestamp DESC LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                try:
                    loaded_state = json.loads(result[0])
                    # Update our state with loaded values, preserving defaults for missing keys
                    self._state.update(loaded_state)
                    self.logger.info(f"Loaded state from database: {list(loaded_state.keys())}")
                except json.JSONDecodeError:
                    self.logger.error("Failed to parse state JSON from database")
            else:
                self.logger.info("No existing state found in database, using defaults")
                self._save_to_db()  # Save initial state
        except Exception as e:
            self.logger.error(f"Error loading state from database: {str(e)}")
    
    def _create_state_table(self):
        """Create the state table if it doesn't exist"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS character_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state_json TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        self.logger.info("Created character_state table")
    
    def _save_to_db(self):
        """Save the current state to database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            state_json = json.dumps(self._state)
            cursor.execute(
                "INSERT INTO character_state (state_json) VALUES (?)",
                (state_json,)
            )
            conn.commit()
            self.logger.info(f"Saved state to database: {list(self._state.keys())}")
        except Exception as e:
            self.logger.error(f"Error saving state to database: {str(e)}")
    
    def get_state(self):
        """Get a copy of the entire state dictionary"""
        return self._state.copy()
    
    def get(self, key, default=None):
        """Get a value from state"""
        return self._state.get(key, default)
    
    def set(self, key, value):
        """Set a single state value and persist to database"""
        if key not in self._state or self._state[key] != value:
            self._state[key] = value
            self._save_to_db()
            self.logger.info(f"Updated state: {key} = {value[:30] if isinstance(value, str) else value}...")
    
    def update(self, **kwargs):
        """Update multiple state values at once"""
        if not kwargs:
            return
            
        updated = False
        for key, value in kwargs.items():
            if key not in self._state or self._state[key] != value:
                self._state[key] = value
                updated = True
        
        if updated:
            self._save_to_db()
            self.logger.info(f"Bulk updated state: {list(kwargs.keys())}")
    
    # Compatibility methods with original MemorySystem
    def get_current_mood(self):
        """Get current mood state"""
        return self.get("mood", "neutral")
    
    def update_mood(self, mood):
        """Update mood state"""
        self.set("mood", mood)
    
    def get_recent_appearances(self, limit=1):
        """Get appearance for compatibility with original system"""
        appearance = self.get("appearance")
        if appearance:
            # Format to match the old API
            return [{"description": appearance, "timestamp": "current"}]
        return []
    
    def add_appearance(self, description):
        """Update appearance state"""
        self.set("appearance", description)
        return 1  # Return an ID for compatibility
    
    def get_recent_clothing(self, limit=1):
        """Get clothing for compatibility with original system"""
        clothing = self.get("clothing")
        if clothing:
            # Format to match the old API
            return [{"description": clothing, "timestamp": "current"}]
        return []
    
    def add_clothing(self, description):
        """Update clothing state"""
        self.set("clothing", description)
        return 1  # Return an ID for compatibility
    
    def get_recent_locations(self, limit=1):
        """Get location for compatibility with original system"""
        location = self.get("location")
        if location:
            # Format to match the old API
            return [{"description": location, "timestamp": "current"}]
        return []
    
    def update_location(self, location):
        """Update location state"""
        self.set("location", location)
    
    def add_location(self, description):
        """Update location (alias for consistency)"""
        self.set("location", description)
        return 1  # Return an ID for compatibility
    
    # These methods don't update state but maintain API compatibility
    def add_clothing_change(self, description):
        """For compatibility - just updates current clothing"""
        return self.add_clothing(description)
    
    def add_appearance_change(self, description):
        """For compatibility - just updates current appearance"""
        return self.add_appearance(description)
    
    # Methods for history (we can add state history later if needed)
    def get_state_history(self, limit=10):
        """Get historical states from database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT state_json, timestamp FROM character_state ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        
        results = cursor.fetchall()
        history = []
        
        for state_json, timestamp in results:
            try:
                state = json.loads(state_json)
                history.append({"state": state, "timestamp": timestamp})
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse historical state JSON: {state_json[:50]}...")
        
        return history 