"""
Memory System Service
====================

This module implements the core memory management system that handles:
1. Conversation history storage and retrieval
2. Semantic memory search using vector embeddings
3. State management delegation (mood, appearance, location, etc.)
4. Relationship tracking
5. Thought and emotion persistence

The system combines:
- Qdrant for vector-based semantic memory search
- StateManager for centralized state management
- SQLite for conversation history (temporary storage)

Note: Most state-related data (mood, appearance, location, etc.) is now managed
through the StateManager rather than individual database tables.
"""

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
    """
    Central memory management system for the AI.
    
    This class orchestrates memory-related operations with a focus on:
    1. Managing conversation history (temporary storage)
    2. Providing semantic memory search via Qdrant
    3. Delegating state management to StateManager
    4. Tracking relationships and thoughts
    
    The system has evolved to use a centralized state object managed by
    StateManager, reducing database complexity and improving consistency.
    """
    def __init__(self):
        self.db = Database()                    # SQLite database for conversation history
        self.state_manager = StateManager()     # Centralized state management
        self.qdrant_memory = QdrantMemoryStore() # Vector store for semantic memories
        self.embedder = get_embedder()          # Text embedding service
        self.appearance_changes = []            # Track appearance changes (legacy)
        self.location = None                    # Current location (legacy)
        self.thoughts = []                      # Active thoughts
        self.conversations = []                 # Conversation history
    
    def add_conversation_entry(self, role, content, embedding=None):
        """
        Add a conversation turn to the database.
        
        This method stores individual conversation turns with optional
        vector embeddings for later semantic search. It maintains the
        chronological order of conversations for context retrieval.
        
        Note: This is temporary storage for the current session only.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO conversations (role, content, embedding) VALUES (?, ?, ?)",
            (role, content, embedding)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_recent_conversation(self, limit=20):
        """
        Retrieve recent conversation history.
        
        This method returns the most recent conversation turns in
        chronological order, providing context for the current interaction.
        The limit parameter controls how many turns are returned.
        
        Note: This retrieves from temporary session storage only.
        """
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
    
    def add_thought(self, content, intensity=0.5, embedding=None):
        """
        Store a thought with intensity level.
        
        This method:
        1. Updates the current thought in state manager
        2. Stores the thought in Qdrant for semantic search
        3. Includes current state context
        """
        try:
            # Update current thought in state manager
            self.state_manager.update_current_thought(content)
            
            # Store in Qdrant for semantic search
            vector = self.embedder.embed_prompt(content)
            asyncio.create_task(self.qdrant_memory.store_memory(
                text=content,
                vector=vector,
                memory_type="thought",
                tags=["thought"],
                mood=self.get_current_mood(),
                intensity=intensity
            ))
        except Exception as e:
            print(f"Failed to store thought: {e}")
    
    def add_secret(self, content, intensity=0.5, embedding=None):
        """
        Store a secret with intensity level.
        
        This method stores secrets in the Qdrant vector store for semantic
        search capabilities. The intensity level helps prioritize secrets
        during retrieval.
        """
        try:
            vector = self.embedder.embed_prompt(content)
            asyncio.create_task(self.qdrant_memory.store_memory(
                text=content,
                vector=vector,
                memory_type="secret",
                tags=["secret"],
                mood=self.get_current_mood(),
                intensity=intensity
            ))
        except Exception as e:
            print(f"Failed to store secret to Qdrant: {e}")
            
    def add_fantasy(self, content, intensity=0.5, embedding=None):
        """
        Store a fantasy with intensity level.
        
        This method stores fantasies in the Qdrant vector store for semantic
        search capabilities. The intensity level helps prioritize fantasies
        during retrieval.
        """
        try:
            vector = self.embedder.embed_prompt(content)
            asyncio.create_task(self.qdrant_memory.store_memory(
                text=content,
                vector=vector,
                memory_type="fantasy",
                tags=["fantasy"],
                mood=self.get_current_mood(),
                intensity=intensity
            ))
        except Exception as e:
            print(f"Failed to store fantasy to Qdrant: {e}")
    
    # State management methods delegated to StateManager
    def update_mood(self, mood: str):
        """
        Update the current mood state.
        
        This method delegates to the state manager to update and persist
        the current mood. The mood state influences both responses and
        memory retrieval.
        """
        return self.state_manager.update_mood(mood)
        
    def get_current_mood(self):
        """
        Retrieve the current mood state.
        
        This method gets the most recent mood from the state manager.
        The mood is used to provide context for responses and memory
        retrieval.
        """
        return self.state_manager.get_current_mood()
    
    def update_relationship(self, entity, parameter, value):
        """
        Update a relationship parameter for an entity.
        
        This method stores relationship information between the AI and
        other entities (users, concepts, etc.). It tracks how the AI
        feels about and interacts with different entities over time.
        
        Note: Relationships are now stored in the state object.
        """
        return self.state_manager.update_relationship(entity, parameter, value)
    
    def get_relationship_parameters(self, entity=None):
        """
        Retrieve relationship parameters for entities.
        
        This method gets the current state of relationships, either for
        a specific entity or all entities. It returns the most recent
        values for each parameter, providing context for interactions.
        
        Note: Relationships are now retrieved from the state object.
        """
        return self.state_manager.get_relationship_parameters(entity)
    
    async def get_relevant_memories(self, query, limit=5):
        """
        Retrieve relevant memories based on a query.
        
        This method combines different types of memories:
        1. Semantic memories from Qdrant
        2. Recent conversation entries (from temporary storage)
        
        The results are sorted by importance and relevance to provide
        the most useful context for the current interaction.
        """
        try:
            # Get semantic memories from Qdrant
            semantic_memories = await self.get_semantic_memories(query, limit)
            
            # Get recent conversation entries
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM conversations WHERE role = 'user' ORDER BY timestamp DESC LIMIT ?,?",
                (1, limit-1)
            )
            convo_results = cursor.fetchall()
            
            # Format results
            memories = []
            
            # Add semantic memories
            memories.extend(semantic_memories)
            
            # Add conversation entries
            for (content,) in convo_results:
                memories.append({
                    "type": "conversation",
                    "text": content,
                    "mood": self.get_current_mood()
                })
            
            return memories[:limit]
        
        except Exception as e:
            print(f"Error retrieving relevant memories: {e}")
            return []

    async def get_semantic_memories(self, query, limit=5, score_threshold=0.7):
        """
        Retrieve semantically similar memories from Qdrant.
        
        This method uses vector embeddings to find memories that are
        semantically related to the query. It returns memories that
        exceed the specified similarity threshold, including their
        content, type, mood, and relevance score.
        """
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

    # State management delegation methods
    def add_appearance(self, description):
        """
        Add an appearance description.
        
        This method delegates to the state manager to store and track
        changes in the AI's appearance. It's used to maintain a consistent
        visual identity across interactions.
        """
        return self.state_manager.add_appearance(description)

    def get_recent_appearances(self, limit=10):
        """
        Retrieve recent appearance descriptions.
        
        This method gets the most recent appearance states from the
        state manager. It's used to provide context about how the AI
        currently looks or has looked recently.
        """
        return self.state_manager.get_recent_appearances(limit)

    def add_clothing(self, description):
        """
        Add a clothing description.
        
        This method delegates to the state manager to store and track
        changes in the AI's clothing. It's used to maintain a consistent
        visual identity and track outfit changes.
        """
        return self.state_manager.add_clothing(description)

    def add_clothing_change(self, change: str):
        """
        Add a clothing change.
        
        This method delegates to the state manager to track changes in
        the AI's clothing. It's used to maintain a consistent visual
        identity and track outfit changes.
        """
        return self.state_manager.add_clothing_change(change)

    def add_appearance_change(self, change: str):
        """
        Add an appearance change.
        
        This method delegates to the state manager to track changes in
        the AI's appearance. It's used to maintain a consistent visual
        identity across interactions.
        """
        # Also keep the local tracking for session compatibility
        self.appearance_changes.append(change)
        return self.state_manager.add_appearance_change(change)
        
    def update_location(self, location: str):
        """
        Update the current location.
        
        This method delegates to the state manager to update and track
        the AI's current location. It's used to provide context for
        location-based interactions.
        """
        return self.state_manager.update_location(location)
        
    def add_location(self, description: str):
        """
        Add a location description.
        
        This method delegates to the state manager to store and track
        location descriptions. It's used to maintain context about
        where the AI is or has been.
        """
        return self.state_manager.add_location(description)
        
    def get_recent_locations(self, limit=10):
        """
        Retrieve recent location descriptions.
        
        This method gets the most recent location states from the
        state manager. It's used to provide context about where the
        AI currently is or has been recently.
        """
        return self.state_manager.get_recent_locations(limit)

    def restore_prompts_from_templates(self):
        """
        Restore prompts from default templates.
        
        This method reinitializes all prompts from their default templates,
        ensuring a consistent starting point for prompt management.
        """
        try:
            prompt_manager = PromptManager()
            # Force reinitialization of all prompts
            prompt_manager.initialize_prompts(force=True)
            return True
        except Exception as e:
            print(f"Error restoring prompts: {e}")
            return False

    def initialize_tables(self):
        """
        Initialize database tables.
        
        This method creates the necessary database tables for:
        1. Conversation history (temporary storage)
        2. State management (via StateManager)
        3. Prompt templates
        
        Note: Most state-related tables have been consolidated into
        the state object managed by StateManager.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Create conversation table for temporary storage
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
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
        
    def get_character_state(self):
        """
        Get the complete character state.
        
        This method retrieves the entire state object from the state
        manager, providing a complete snapshot of the AI's current state.
        """
        return self.state_manager.get_state()
        
    def update_state(self, **kwargs):
        """
        Update multiple state values at once.
        
        This method allows bulk updates to the state object, providing
        a convenient way to modify multiple state attributes simultaneously.
        """
        return self.state_manager.update(**kwargs)

    def get_recent_clothing(self, limit=1):
        """
        Retrieve recent clothing descriptions.
        
        This method gets the most recent clothing states from the
        state manager. It's used to provide context about what the AI
        is currently wearing or has worn recently.
        
        Args:
            limit: Number of clothing entries to return
            
        Returns:
            List of dictionaries containing clothing descriptions
        """
        clothing = self.state_manager.get_recent_clothing(limit)
        # Convert to the expected format with "description" key
        return [{"description": item} for item in clothing] if clothing else []