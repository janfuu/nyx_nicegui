from app.models.database import Database
from app.models.prompt_models import PromptManager
from app.core.state_manager import StateManager
from app.services.qdrant_memory_store import QdrantMemoryStore
from app.services.embedder import get_embedder
import json
import time
import sqlite3
import numpy as np
import asyncio

class MemorySystem:
    def __init__(self):
        self.db = Database()
        self.state_manager = StateManager()  # Use the new state manager
        self.qdrant_memory = QdrantMemoryStore()
        self.embedder = get_embedder()  # Use the global embedder instance
        self.appearance_changes = []
        self.location = None
        self.thoughts = []
        self.conversations = []
    
    def add_conversation_entry(self, role, content, embedding=None):
        """Add a conversation turn to the database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO conversations (role, content, embedding) VALUES (?, ?, ?)",
            (role, content, embedding)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_recent_conversation(self, limit=20):
        """Get recent conversation turns"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT role, content FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        
        # Return in chronological order
        results = cursor.fetchall()
        conversation = [{"role": role, "content": content} for role, content in reversed(results)]
        return conversation
    
    def add_thought(self, content, importance=5, embedding=None):
        """Add an extracted thought with importance level"""
        try:
            vector = self.embedder.embed_prompt(content).tolist()
            asyncio.create_task(self.qdrant_memory.store_memory(
                text=content,
                vector=vector,
                memory_type="thought",
                tags=["thought"],
                mood=self.get_current_mood()
            ))
        except Exception as e:
            print(f"Failed to store to Qdrant: {e}")
    
    # Forward state-related methods to StateManager
    def update_mood(self, mood: str):
        """Update the current mood - delegates to state_manager"""
        return self.state_manager.update_mood(mood)
        
    def get_current_mood(self):
        """Get the most recent mood - delegates to state_manager"""
        return self.state_manager.get_current_mood()
    
    def update_relationship(self, entity, parameter, value):
        """Update a relationship parameter for an entity"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO relationships (entity, parameter, value) VALUES (?, ?, ?)",
            (entity, parameter, value)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_relationship_parameters(self, entity=None):
        """Get relationship parameters for an entity or all entities"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if entity:
            cursor.execute(
                """
                SELECT r1.entity, r1.parameter, r1.value
                FROM relationships r1
                INNER JOIN (
                    SELECT entity, parameter, MAX(timestamp) as max_time
                    FROM relationships
                    WHERE entity = ?
                    GROUP BY entity, parameter
                ) r2
                ON r1.entity = r2.entity AND r1.parameter = r2.parameter AND r1.timestamp = r2.max_time
                """,
                (entity,)
            )
        else:
            cursor.execute(
                """
                SELECT r1.entity, r1.parameter, r1.value
                FROM relationships r1
                INNER JOIN (
                    SELECT entity, parameter, MAX(timestamp) as max_time
                    FROM relationships
                    GROUP BY entity, parameter
                ) r2
                ON r1.entity = r2.entity AND r1.parameter = r2.parameter AND r1.timestamp = r2.max_time
                """
            )
        
        results = cursor.fetchall()
        relationships = {}
        
        for entity_name, param, value in results:
            if entity_name not in relationships:
                relationships[entity_name] = {}
            relationships[entity_name][param] = value
        
        return relationships
    
    def get_relevant_memories(self, query, limit=5):
        """
        Get relevant memories based on a query
        
        As a basic implementation, this will retrieve:
        1. Recent thoughts
        2. Recent conversation entries
        
        For a more advanced implementation, this would use vector 
        embeddings to find semantically relevant memories.
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get recent thoughts
            cursor.execute(
                "SELECT content, importance FROM thoughts ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            thought_results = cursor.fetchall()
            
            # Get recent conversation entries (excluding the most recent as it's likely the current query)
            cursor.execute(
                "SELECT content FROM conversations WHERE role = 'user' ORDER BY timestamp DESC LIMIT ?,?",
                (1, limit-1)
            )
            convo_results = cursor.fetchall()
            
            # Format results as memory objects
            memories = []
            
            for content, importance in thought_results:
                memories.append({
                    "type": "thought",
                    "text": content,
                    "mood": self.get_current_mood()
                })
            
            for (content,) in convo_results:
                memories.append({
                    "type": "conversation",
                    "text": content,
                    "mood": self.get_current_mood()
                })
            
            # Sort by importance
            memories.sort(key=lambda x: x.get("importance", 0), reverse=True)
            
            return memories[:limit]
        
        except Exception as e:
            print(f"Error retrieving relevant memories: {e}")
            return []
    
    def get_recent_thoughts(self, limit=10):
        """Get recent thoughts"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT content, importance, timestamp FROM thoughts ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        
        results = cursor.fetchall()
        thoughts = [{"content": content, "importance": importance, "timestamp": timestamp} 
                   for content, importance, timestamp in results]
        return thoughts

    async def get_semantic_memories(self, query, limit=5, score_threshold=0.7):
        """Retrieve semantically similar memories from Qdrant"""
        try:
            vector = self.embedder.embed_prompt(query).tolist()
            results = await self.qdrant_memory.search_similar(
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold
            )
            return [
                {
                    "text": hit.payload.get("text"),
                    "type": hit.payload.get("type"),
                    "mood": hit.payload.get("mood", "neutral"),
                    "tags": hit.payload.get("tags", []),
                    "score": hit.score
                }
                for hit in results
            ]
        except Exception as e:
            print(f"Memory search failed: {e}")
            return []

    def get_recent_emotions(self, limit=10):
        """Get recent emotions"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT mood, intensity, timestamp FROM emotions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        
        results = cursor.fetchall()
        emotions = [{"mood": mood, "intensity": intensity, "timestamp": timestamp} 
                   for mood, intensity, timestamp in results]
        return emotions

    # Appearance methods delegated to StateManager
    def add_appearance(self, description):
        """Add an appearance description - delegates to state_manager"""
        return self.state_manager.add_appearance(description)

    def get_recent_appearances(self, limit=10):
        """Get recent appearance descriptions - delegates to state_manager"""
        return self.state_manager.get_recent_appearances(limit)

    # Clothing methods delegated to StateManager
    def add_clothing(self, description):
        """Add a clothing description - delegates to state_manager"""
        return self.state_manager.add_clothing(description)

    def get_recent_clothing(self, limit=10):
        """Get recent clothing descriptions - delegates to state_manager"""
        return self.state_manager.get_recent_clothing(limit)

    def add_clothing_change(self, change: str):
        """Add a clothing change - delegates to state_manager"""
        return self.state_manager.add_clothing_change(change)

    def add_appearance_change(self, change: str):
        """Add an appearance change - delegates to state_manager"""
        # Also keep the local tracking for session compatibility
        self.appearance_changes.append(change)
        return self.state_manager.add_appearance_change(change)
        
    # Location methods delegated to StateManager
    def update_location(self, location: str):
        """Update the current location - delegates to state_manager"""
        return self.state_manager.update_location(location)
        
    def add_location(self, description: str):
        """Add a location description - delegates to state_manager"""
        return self.state_manager.add_location(description)
        
    def get_recent_locations(self, limit=10):
        """Get recent location descriptions - delegates to state_manager"""
        return self.state_manager.get_recent_locations(limit)

    def restore_prompts_from_templates(self):
        """Restore prompts from default templates"""
        try:
            prompt_manager = PromptManager()
            # Force reinitialization of all prompts
            prompt_manager.initialize_prompts(force=True)
            return True
        except Exception as e:
            print(f"Error restoring prompts: {e}")
            return False

    def initialize_tables(self):
        """Initialize database tables"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Create the tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS thoughts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 5,
            embedding BLOB,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mood TEXT NOT NULL,
            intensity REAL DEFAULT 1.0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            parameter TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Initialize the state table via StateManager
        self.state_manager._create_state_table()
        
        # Initialize prompts
        prompt_manager = PromptManager()
        
        # Commit all changes
        conn.commit()
        return True
        
    # New method to expose the full state
    def get_character_state(self):
        """Get the complete character state"""
        return self.state_manager.get_state()
        
    # New method to update multiple state values at once
    def update_state(self, **kwargs):
        """Update multiple state values at once"""
        return self.state_manager.update(**kwargs)