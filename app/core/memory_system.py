from app.models.database import Database
from app.models.prompt_models import PromptManager
import json
import time
import sqlite3
import numpy as np

class MemorySystem:
    def __init__(self):
        self.db = Database()
    
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
    
    def get_recent_conversation(self, limit=10):
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
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO thoughts (content, importance, embedding) VALUES (?, ?, ?)",
            (content, importance, embedding)
        )
        conn.commit()
        return cursor.lastrowid
    
    def update_mood(self, mood, intensity=1.0):
        """Update the current mood state"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO emotions (mood, intensity) VALUES (?, ?)",
            (mood, intensity)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_current_mood(self):
        """Get the most recent mood"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT mood FROM emotions ORDER BY timestamp DESC LIMIT 1"
        )
        
        result = cursor.fetchone()
        if result:
            return result[0]
        return "neutral"  # Default mood
    
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
                    "value": content,
                    "importance": importance
                })
            
            for (content,) in convo_results:
                memories.append({
                    "type": "conversation",
                    "value": content,
                    "importance": 3  # Default importance
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
        
        # Initialize prompts
        prompt_manager = PromptManager()
        
        # Commit all changes
        conn.commit()
        return True