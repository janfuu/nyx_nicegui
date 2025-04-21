#!/usr/bin/env python
"""
Simple script to test Qdrant storage directly
"""

import asyncio
import numpy as np
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

async def main():
    print("Starting Qdrant test...")
    
    # Create a sample vector
    vector = np.random.rand(512).astype(np.float32)
    vector = vector / np.linalg.norm(vector)  # normalize
    
    # Simple payload
    payload = {
        "title": "Test vector",
        "description": "This is a test vector to verify Qdrant is working",
        "timestamp": "2025-04-20T00:00:00"
    }
    
    try:
        # Connect to Qdrant
        print("Connecting to Qdrant...")
        client = QdrantClient(host="localhost", port=6333)
        
        # Check existing collections
        collections = client.get_collections()
        print(f"Existing collections: {[c.name for c in collections.collections]}")
        
        # Create or recreate a test collection
        collection_name = "test_collection"
        print(f"Creating collection {collection_name}...")
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE)
        )
        
        # Generate a UUID for the point
        point_id = str(uuid.uuid4())
        print(f"Generated UUID for test point: {point_id}")
        
        # Insert a single point
        print("Inserting test point...")
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload=payload
                )
            ]
        )
        
        # Verify point was inserted
        print("Checking point count...")
        count = client.count(collection_name=collection_name)
        print(f"Points in collection: {count.count}")
        
        # Try to scroll points
        print("Retrieving points...")
        results = client.scroll(
            collection_name=collection_name,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        points = results[0]
        print(f"Retrieved {len(points)} points")
        for i, point in enumerate(points):
            print(f"Point {i+1}: ID={point.id}, Payload keys={list(point.payload.keys())}")
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main()) 