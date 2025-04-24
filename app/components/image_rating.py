from nicegui import ui, events
from app.services.qdrant_image_store import QdrantImageStore
from app.core.memory_system import MemorySystem
from app.services.embedder import get_embedder

class ImageRating:
    """Handles image rating and storage in Qdrant"""
    def __init__(self) -> None:
        self.status = ui.label("").classes('text-white ml-4')
        
    async def rate_image(self, image_id: str, image_url: str, original_prompt: str, parsed_prompt: str, rating_value: int) -> None:
        """Store image in Qdrant with specified rating"""
        try:
            # Determine the appropriate rating message
            if rating_value > 0:
                rating_message = "Positively"
            elif rating_value < 0:
                rating_message = "Negatively" 
            else:
                rating_message = "Neutrally"
                
            self.status.text = f"{rating_message} rating image..."
            
            # Get embedder and Qdrant client
            embedder = get_embedder()
            qdrant = QdrantImageStore()
            
            # First check if the image already exists in Qdrant
            update_success = False
            try:
                # Attempt to update the rating first
                # If it succeeds, the image is already in Qdrant
                result = await qdrant.update_rating(image_id, rating_value)
                if result:
                    update_success = True
                    self.status.text = f"Rating updated successfully ✓"
                    return
            except Exception as check_e:
                # Only print if it's not a 404 error (expected when image doesn't exist yet)
                if "404" not in str(check_e) and "Not found" not in str(check_e):
                    print(f"Unexpected error checking image in Qdrant: {str(check_e)}")
            
            if update_success:
                return
                
            # Get current appearance and mood
            memory_system = MemorySystem()
            current_appearance = memory_system.get_recent_appearances(1)
            current_appearance_text = current_appearance[0]["description"] if current_appearance else None
            current_mood = memory_system.get_current_mood()
            current_location = memory_system.get_recent_locations(1)
            current_location_text = current_location[0]["description"] if current_location else None
            
            # Embed the image
            image_vector, thumbnail_b64 = embedder.embed_image_from_url(image_url)
            if image_vector is None:
                self.status.text = "Failed to embed image"
                return
                
            # Prepare payload
            import time
            payload = {
                "prompt": parsed_prompt,
                "original_prompt": original_prompt,  # Store both prompts
                "url": image_url,
                "thumbnail_b64": thumbnail_b64,
                "mood": current_mood,
                "appearance": current_appearance_text,
                "location": current_location_text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": "runware",
                "rating": rating_value
            }
            
            # Store in Qdrant
            result = await qdrant.store_image_embedding(
                image_id=image_id,
                vector=image_vector.tolist(),
                payload=payload
            )
            
            if result:
                self.status.text = f"Image stored with {rating_value} rating ✓"
            else:
                self.status.text = "Storage failed ✗"
                
        except Exception as e:
            import traceback
            print(f"Error storing rated image: {str(e)}")
            print(traceback.format_exc())
            self.status.text = f"Error: {str(e)}" 