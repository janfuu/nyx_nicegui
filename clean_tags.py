from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import re
import argparse
import sys
from sentence_transformers import SentenceTransformer

client = QdrantClient(host="localhost", port=6333)
collection = "nyx_memories"
embedder = SentenceTransformer("all-mpnet-base-v2")

def is_malformed_tag(tag):
    return isinstance(tag, str) and (tag.startswith("[") or tag.endswith("]"))

def clean_tag(tag):
    return tag.strip("[]").strip()

def find_and_fix_malformed_tags(dry_run=False):
    scroll_cursor = None
    cleaned_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name=collection,
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                tags = point.payload.get("tags", [])
                malformed = [t for t in tags if is_malformed_tag(t)]

                if malformed:
                    cleaned_tags = [clean_tag(t) for t in tags]
                    print(f"\nWould fix {point.id}: {tags} -> {cleaned_tags}")

                    if not dry_run:
                        # Create new payload without timestamp
                        new_payload = dict(point.payload)
                        del new_payload["timestamp"]
                        
                        client.set_payload(
                            collection_name=collection,
                            payload=new_payload,
                            points=[point.id]
                        )
                    cleaned_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would fix' if dry_run else 'Fixed'} tags in {cleaned_count} memories.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would fix' if dry_run else 'Fixed'} tags in {cleaned_count} memories.")
        sys.exit(0)

def remove_timestamps(dry_run=False):
    scroll_cursor = None
    removed_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name=collection,
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                if "timestamp" in point.payload:
                    print(f"\nWould remove timestamp from {point.id}")
                    
                    if not dry_run:
                        # Use delete_payload to remove the timestamp field
                        client.delete_payload(
                            collection_name=collection,
                            keys=["timestamp"],
                            points=[point.id]
                        )
                    removed_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would remove' if dry_run else 'Removed'} timestamps from {removed_count} memories.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would remove' if dry_run else 'Removed'} timestamps from {removed_count} memories.")
        sys.exit(0)

def recalculate_mood_vectors(dry_run=False):
    scroll_cursor = None
    updated_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name=collection,
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                mood = point.payload.get("mood")
                if mood:
                    print(f"\nWould update mood vector for {point.id} (mood: {mood})")
                    
                    if not dry_run:
                        # Calculate new mood vector
                        mood_vector = embedder.encode(mood).tolist()
                        
                        # Update the vector
                        client.update_vectors(
                            collection_name=collection,
                            points=[
                                {
                                    "id": point.id,
                                    "vector": {"mood_vector": mood_vector}
                                }
                            ]
                        )
                    updated_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would update' if dry_run else 'Updated'} mood vectors for {updated_count} memories.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would update' if dry_run else 'Updated'} mood vectors for {updated_count} memories.")
        sys.exit(0)

def remove_thumbnails(dry_run=False):
    """Remove thumbnail_b64 fields from all points in the nyx_images collection"""
    scroll_cursor = None
    removed_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name="nyx_images",  # Use the correct collection
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                if "thumbnail_b64" in point.payload:
                    print(f"\nWould remove thumbnail from {point.id}")
                    
                    if not dry_run:
                        # Use delete_payload to remove the thumbnail_b64 field
                        client.delete_payload(
                            collection_name="nyx_images",  # Use the correct collection
                            keys=["thumbnail_b64"],
                            points=[point.id]
                        )
                    removed_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would remove' if dry_run else 'Removed'} thumbnails from {removed_count} images.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would remove' if dry_run else 'Removed'} thumbnails from {removed_count} images.")
        sys.exit(0)

def update_image_urls(dry_run=False):
    """Update image URLs from localhost:9000 to http://orang:9000 in the nyx_images collection"""
    scroll_cursor = None
    updated_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name="nyx_images",
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                if "url" in point.payload:
                    current_url = point.payload["url"]
                    if "localhost:9000" in current_url:
                        new_url = current_url.replace("localhost:9000", "orang:9000")
                        print(f"\nWould update URL from {current_url} to {new_url}")
                        
                        if not dry_run:
                            # Update the URL in the payload
                            client.set_payload(
                                collection_name="nyx_images",
                                payload={"url": new_url},
                                points=[point.id]
                            )
                        updated_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would update' if dry_run else 'Updated'} {updated_count} image URLs.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would update' if dry_run else 'Updated'} {updated_count} image URLs.")
        sys.exit(0)

def remove_source_urls(dry_run=False):
    """Remove source_url fields from all points in the nyx_images collection"""
    scroll_cursor = None
    removed_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name="nyx_images",
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                if "source_url" in point.payload:
                    print(f"\nWould remove source_url from {point.id}")
                    
                    if not dry_run:
                        # Use delete_payload to remove the source_url field
                        client.delete_payload(
                            collection_name="nyx_images",
                            keys=["source_url"],
                            points=[point.id]
                        )
                    removed_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would remove' if dry_run else 'Removed'} source_url from {removed_count} images.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would remove' if dry_run else 'Removed'} source_url from {removed_count} images.")
        sys.exit(0)

def update_image_bucket(dry_run=False):
    """Update image URLs from nyxmemories bucket to nyximages bucket in the nyx_images collection"""
    scroll_cursor = None
    updated_count = 0
    total_processed = 0

    try:
        while True:
            result, scroll_cursor = client.scroll(
                collection_name="nyx_images",
                limit=200,
                with_payload=True,
                with_vectors=False,
                offset=scroll_cursor
            )

            if not result:
                break

            total_processed += len(result)
            print(f"\rProcessed {total_processed} records...", end="", file=sys.stderr)

            for point in result:
                if "url" in point.payload:
                    current_url = point.payload["url"]
                    if "nyxmemories" in current_url:
                        new_url = current_url.replace("nyxmemories", "nyximages")
                        print(f"\nWould update URL from {current_url} to {new_url}")
                        
                        if not dry_run:
                            # Update the URL in the payload
                            client.set_payload(
                                collection_name="nyx_images",
                                payload={"url": new_url},
                                points=[point.id]
                            )
                        updated_count += 1

            # Break if we've reached the end (scroll_cursor is None)
            if scroll_cursor is None:
                break

        print(f"\n✅ {'Would update' if dry_run else 'Updated'} {updated_count} image URLs.")

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Partial results:")
        print(f"Processed {total_processed} records")
        print(f"{'Would update' if dry_run else 'Updated'} {updated_count} image URLs.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean Qdrant database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--remove-timestamps', action='store_true', help='Remove timestamp fields instead of cleaning tags')
    parser.add_argument('--recalculate-mood', action='store_true', help='Recalculate mood vectors based on mood field')
    parser.add_argument('--remove-thumbnails', action='store_true', help='Remove thumbnail_b64 fields from nyx_images collection')
    parser.add_argument('--update-urls', action='store_true', help='Update image URLs from localhost to orang')
    parser.add_argument('--remove-source-urls', action='store_true', help='Remove source_url fields from nyx_images collection')
    parser.add_argument('--update-bucket', action='store_true', help='Update image URLs from nyxmemories to nyximages bucket')
    args = parser.parse_args()
    
    if args.update_bucket:
        update_image_bucket(dry_run=args.dry_run)
    elif args.remove_source_urls:
        remove_source_urls(dry_run=args.dry_run)
    elif args.update_urls:
        update_image_urls(dry_run=args.dry_run)
    elif args.remove_thumbnails:
        remove_thumbnails(dry_run=args.dry_run)
    elif args.recalculate_mood:
        recalculate_mood_vectors(dry_run=args.dry_run)
    elif args.remove_timestamps:
        remove_timestamps(dry_run=args.dry_run)
    else:
        find_and_fix_malformed_tags(dry_run=args.dry_run)
