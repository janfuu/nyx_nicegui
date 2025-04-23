from app.services.embedding_service import Embedder

# Global embedder instance
_embedder_instance = None

def get_embedder():
    """Get the global embedder instance, initializing it if needed"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance 