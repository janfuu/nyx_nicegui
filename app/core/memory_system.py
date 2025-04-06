from app.models.database import Database
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
        return result[0] if result else "neutral"
    
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