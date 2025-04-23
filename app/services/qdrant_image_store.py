class QdrantImageStore:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantImageStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        config = Config()
        self.logger = Logger()
        self.host = config.get("qdrant", "host", "localhost")
        self.port = config.get("qdrant", "port", 6333)
        
        # Get image collection configuration
        collections_config = config.get("qdrant", "collections", {})
        image_config = collections_config.get("images", {})
        
        self.collection_name = image_config.get("name", "nyx_images")
        self.vector_size = image_config.get("vector_size", 512)
        self.distance_str = image_config.get("distance", "cosine")
        
        self.client = QdrantClient(host=self.host, port=self.port)
        self._ensure_collection()
        self._initialized = True 