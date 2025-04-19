import sqlite3
import os
from pathlib import Path

class Database:
    def __init__(self, db_path="data/nyx_memory.db"):
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
        self.setup()
    
    def setup(self):
        """Initialize database and create tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Create conversations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            role TEXT,
            content TEXT,
            embedding BLOB
        )
        ''')
        
        # Create thoughts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS thoughts (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content TEXT,
            importance INTEGER DEFAULT 5,
            embedding BLOB
        )
        ''')
        
        # Create emotions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emotions (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mood TEXT,
            intensity REAL
        )
        ''')
        
        # Create relationships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY,
            entity TEXT,
            parameter TEXT,
            value REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create world state table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS world_state (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            location TEXT,
            description TEXT,
            image_url TEXT
        )
        ''')
        
        # Create locations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL
        )
        ''')
        
        # Create appearance table for storing Nyx's appearance descriptions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS appearance (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL,
            source TEXT DEFAULT 'self_tag'
        )
        ''')
        
        # Create prompts table with version support
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            description TEXT,
            version INTEGER DEFAULT 1,
            is_default BOOLEAN DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, type)
        )
        ''')
        
        self.conn.commit()
        
        # Update schema to add any missing columns to existing tables
        self.update_schema()
    
    def get_connection(self):
        """Get the database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def update_schema(self):
        """Update database schema to latest version"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if version column exists in prompts table
        cursor.execute("PRAGMA table_info(prompts)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add missing columns if they don't exist
        if 'version' not in column_names:
            cursor.execute("ALTER TABLE prompts ADD COLUMN version INTEGER DEFAULT 1")
            print("Added 'version' column to prompts table")
        
        if 'is_default' not in column_names:
            cursor.execute("ALTER TABLE prompts ADD COLUMN is_default BOOLEAN DEFAULT 0")
            print("Added 'is_default' column to prompts table")
        
        if 'updated_at' not in column_names:
            cursor.execute("ALTER TABLE prompts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("Added 'updated_at' column to prompts table")
        
        conn.commit()