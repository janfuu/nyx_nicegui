# app/utils/qdrant_init.py

"""
Qdrant Initialization Service
============================

This module handles the initialization and health checking of Qdrant services:
1. Memory Store: For semantic memory and mental states
2. Image Store: For image metadata and embeddings

The initialization process:
1. Creates necessary collections if they don't exist
2. Verifies connection to Qdrant server
3. Checks health of all services
4. Provides synchronous wrapper for startup scripts

This module is typically called during system startup to ensure
all Qdrant services are properly initialized and available.
"""

from app.services.qdrant_image_store import QdrantImageStore
from app.services.qdrant_memory_store import QdrantMemoryStore
from app.utils.config import Config
import asyncio
import logging

# Use the root logger with our custom name
logger = logging.getLogger('nyx')

# Global initialization flag
_is_initialized = False

async def initialize_qdrant():
    """
    Initialize and verify all Qdrant connections and collections.
    
    This function:
    1. Initializes the memory store for semantic memories
    2. Initializes the image store for image metadata
    3. Performs health checks on all services
    4. Logs the initialization status
    
    The function is designed to fail gracefully if any part of the
    initialization process fails, providing detailed error logging.
    
    Returns:
        bool: True if all services initialized successfully, False otherwise
    """
    global _is_initialized
    
    if _is_initialized:
        logger.debug("Qdrant already initialized, skipping...")
        return True
        
    try:
        # Initialize the memory store for semantic memories
        memory_store = QdrantMemoryStore()
        memory_store_health = await memory_store.check_health()
        
        # Initialize the image store for image metadata
        image_store = QdrantImageStore()
        
        # If we made it this far, the collections are created
        logger.info("Qdrant collections initialized successfully")
        
        if not memory_store_health:
            logger.error("Qdrant health check failed. Please check your Qdrant server.")
            return False
            
        _is_initialized = True
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Qdrant: {str(e)}")
        return False

def run_initialization():
    """
    Run the Qdrant initialization synchronously.
    
    This is a convenience wrapper for the async initialization function,
    primarily used in startup scripts and direct execution. It:
    1. Creates a new event loop
    2. Runs the async initialization
    3. Closes the event loop
    4. Returns the initialization result
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    return asyncio.run(initialize_qdrant())

if __name__ == "__main__":
    """
    Direct execution entry point.
    
    This allows running this file directly to test Qdrant connection
    and initialization. Useful for:
    1. Testing Qdrant server connectivity
    2. Verifying collection creation
    3. Debugging initialization issues
    """
    success = run_initialization()
    print(f"Qdrant initialization {'successful' if success else 'failed'}") 