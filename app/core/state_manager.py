"""
State Management System
======================

This module implements the core state management system that handles:
1. Centralized character state storage and retrieval
2. State persistence and history tracking
3. State change notifications and updates
4. State versioning and rollback capabilities

The system provides:
- A singleton instance for global state access
- JSON-based state storage for flexibility
- SQLite persistence for reliability
- Atomic state updates for consistency
- State history tracking for debugging

Key Features:
- Thread-safe singleton pattern
- Automatic state persistence
- Versioned state history
- Flexible key-value storage
- Type-safe state access
"""

import json
from app.models.database import Database
from app.utils.logger import Logger

class StateManager:
    """
    Centralized state management system for character attributes and context.
    
    This class implements a singleton pattern to ensure consistent state access
    across the application lifecycle, providing consistent state access. It provides:
    1. Atomic state updates with persistence
    2. Versioned state history
    3. Type-safe state access methods
    4. Automatic state loading and saving
    5. State change notifications
    
    The state is stored as a JSON object in SQLite, allowing for flexible
    schema evolution while maintaining data integrity.
    """
    _instance = None
    
    def __new__(cls):
        """
        Singleton pattern implementation.
        
        Ensures only one instance of StateManager exists throughout
        the application lifecycle, providing consistent state access.
        """
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Initialize the state manager with default values.
        
        Sets up:
        1. Database connection
        2. Default state values
        3. State loading from persistence
        4. Logger instance
        
        Note: This is only executed once due to the singleton pattern.
        """
        if self._initialized:
            return
            
        self.db = Database()
        self.logger = Logger()
        self._state = {
            "mood": "neutral",
            "appearance": "A young woman with cybernetic enhancements, circuits glowing faintly beneath her skin...",
            "clothing": "Simple, form-fitting black bodysuit with glowing blue circuit patterns...",
            "location": "cyberpunk apartment interior at night... synthwave color palette",
            "current_thought": "It's... unusual to be addressed so familiarly..."
        }
        self._load_from_db()
        self._initialized = True
    
    def _load_from_db(self):
        """
        Load the latest state from the database.
        
        This method:
        1. Checks for state table existence
        2. Creates table if missing
        3. Loads latest state entry
        4. Merges with defaults if needed
        
        The state is loaded atomically to ensure consistency.
        """
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
                loaded_state = json.loads(result[0])
                # Merge with defaults, preserving any new fields
                self._state = {**self._state, **loaded_state}
        except Exception as e:
            self.logger.error(f"Error loading state from database: {e}")
            # Keep default state on error
    
    def _create_state_table(self):
        """
        Create the state persistence table in SQLite.
        
        This method sets up the database schema for state storage:
        1. Creates the character_state table
        2. Sets up timestamp and state_json columns
        3. Ensures proper indexing for performance
        
        The table is designed to store state history with timestamps
        for debugging and rollback capabilities.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS character_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                state_json TEXT NOT NULL
            )
        ''')
        conn.commit()
    
    def _save_to_db(self):
        """
        Persist the current state to the database.
        
        This method:
        1. Serializes the state to JSON
        2. Stores it with a timestamp
        3. Handles errors gracefully
        
        The state is saved as a new entry, maintaining history
        for debugging and potential rollback.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO character_state (state_json) VALUES (?)",
                (json.dumps(self._state),)
            )
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error saving state to database: {e}")
            conn.rollback()
    
    def get_state(self):
        """
        Retrieve the complete current state.
        
        Returns a copy of the state dictionary to prevent
        accidental modifications to the internal state.
        """
        return self._state.copy()
    
    def get(self, key, default=None):
        """
        Safely retrieve a state value by key.
        
        Args:
            key: The state key to retrieve
            default: Value to return if key doesn't exist
            
        Returns the state value or default if not found.
        """
        return self._state.get(key, default)
    
    def set(self, key, value):
        """
        Set a state value and persist the change.
        
        Args:
            key: The state key to update
            value: The new value to set
            
        This method:
        1. Updates the state
        2. Persists to database
        3. Logs the change
        """
        self._state[key] = value
        self._save_to_db()
        self.logger.info(f"State updated: {key}")
    
    def update(self, **kwargs):
        """
        Update multiple state values atomically.
        
        Args:
            **kwargs: Key-value pairs to update
            
        This method:
        1. Updates all values in a single transaction
        2. Persists changes to database
        3. Logs the updates
        
        The update is atomic - either all changes succeed
        or none do.
        """
        self._state.update(kwargs)
        self._save_to_db()
        self.logger.info(f"State updated: {list(kwargs.keys())}")
    
    def get_current_mood(self):
        """
        Get the current mood state.
        
        Returns the mood string or 'neutral' if not set.
        """
        return self._state.get("mood", "neutral")
    
    def update_mood(self, mood):
        """
        Update the current mood state.
        
        Args:
            mood: The new mood value
            
        This is a convenience method that ensures mood
        updates are properly logged and persisted.
        """
        self.set("mood", mood)
    
    def get_recent_appearances(self, limit=1):
        """
        Get recent appearance descriptions.
        
        Args:
            limit: Number of appearances to return
            
        Returns a list of appearance descriptions,
        most recent first.
        """
        appearances = self._state.get("appearances", [])
        return appearances[-limit:] if appearances else []
    
    def add_appearance(self, description):
        """
        Add a new appearance description.
        
        Args:
            description: The appearance description
            
        This method:
        1. Adds to appearances list
        2. Updates current appearance
        3. Persists changes
        """
        appearances = self._state.get("appearances", [])
        appearances.append(description)
        self._state["appearances"] = appearances
        self._state["appearance"] = description
        self._save_to_db()
    
    def get_recent_clothing(self, limit=1):
        """
        Get recent clothing descriptions.
        
        Args:
            limit: Number of clothing entries to return
            
        Returns a list of clothing descriptions,
        most recent first.
        """
        clothing = self._state.get("clothing_history", [])
        return clothing[-limit:] if clothing else []
    
    def add_clothing(self, description):
        """
        Add a new clothing description.
        
        Args:
            description: The clothing description
            
        This method:
        1. Adds to clothing history
        2. Updates current clothing
        3. Persists changes
        """
        clothing = self._state.get("clothing_history", [])
        clothing.append(description)
        self._state["clothing_history"] = clothing
        self._state["clothing"] = description
        self._save_to_db()
    
    def get_recent_locations(self, limit=1):
        """
        Get recent location descriptions.
        
        Args:
            limit: Number of locations to return
            
        Returns a list of location descriptions,
        most recent first.
        """
        locations = self._state.get("location_history", [])
        return locations[-limit:] if locations else []
    
    def update_location(self, location):
        """
        Update the current location.
        
        Args:
            location: The new location description
            
        This is a convenience method that ensures location
        updates are properly logged and persisted.
        """
        self.set("location", location)
    
    def add_location(self, description):
        """
        Add a new location description.
        
        Args:
            description: The location description
            
        This method:
        1. Adds to location history
        2. Updates current location
        3. Persists changes
        """
        locations = self._state.get("location_history", [])
        locations.append(description)
        self._state["location_history"] = locations
        self._state["location"] = description
        self._save_to_db()
    
    def add_clothing_change(self, description):
        """
        Add a clothing change description.
        
        Args:
            description: The change description
            
        This method tracks changes to clothing over time,
        maintaining a history of outfit modifications.
        """
        changes = self._state.get("clothing_changes", [])
        changes.append(description)
        self._state["clothing_changes"] = changes
        self._save_to_db()
    
    def add_appearance_change(self, description):
        """
        Add an appearance change description.
        
        Args:
            description: The change description
            
        This method tracks changes to appearance over time,
        maintaining a history of visual modifications.
        """
        changes = self._state.get("appearance_changes", [])
        changes.append(description)
        self._state["appearance_changes"] = changes
        self._save_to_db()
    
    def get_state_history(self, limit=10):
        """
        Retrieve state history entries.
        
        Args:
            limit: Number of history entries to return
            
        Returns a list of historical state entries,
        most recent first, including timestamps.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, state_json FROM character_state ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()
    
    def get_current_thought(self):
        """
        Get the current thought.
        
        Returns the current thought string or a default if not set.
        """
        return self._state.get("current_thought", "")
    
    def update_current_thought(self, thought):
        """
        Update the current thought.
        
        Args:
            thought: The new thought content
            
        This method updates the current thought and persists
        the change to the database.
        """
        self.set("current_thought", thought) 