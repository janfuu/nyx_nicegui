# app/utils/qdrant_init.py

from app.services.qdrant_client import QdrantImageStore
from app.services.qdrant_memory_store import QdrantMemoryStore
from app.utils.logger import Logger
import asyncio

logger = Logger()

async def initialize_qdrant():
    """
    Initialize and verify all Qdrant connections and collections
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Initialize the memory store
        memory_store = QdrantMemoryStore()
        memory_store_health = await memory_store.check_health()
        
        # Initialize the image store
        image_store = QdrantImageStore()
        
        # If we made it this far, the collections are created
        logger.info("Qdrant collections initialized successfully")
        
        if not memory_store_health:
            logger.error("Qdrant health check failed. Please check your Qdrant server.")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Qdrant: {str(e)}")
        return False

def run_initialization():
    """Run the initialization synchronously - useful for startup scripts"""
    return asyncio.run(initialize_qdrant())

if __name__ == "__main__":
    # This allows running this file directly to test Qdrant connection
    success = run_initialization()
    print(f"Qdrant initialization {'successful' if success else 'failed'}") 