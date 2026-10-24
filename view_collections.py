"""
view_collection.py
-------------------
Quick utility to peek inside your Weaviate LegalDocs collection and see
exactly what chunks are currently stored (useful after uploading a PDF,
to confirm ingestion worked and see what will be searchable).
"""

import weaviate

COLLECTION_NAME = "LegalDocs"

client = weaviate.connect_to_local()

try:
    if not client.collections.exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' does not exist yet. Upload a PDF first.")
    else:
        collection = client.collections.get(COLLECTION_NAME)

        # Fetch all stored objects
        response = collection.query.fetch_objects(limit=100)

        print(f"Total chunks stored: {len(response.objects)}\n")

        for i, obj in enumerate(response.objects):
            props = obj.properties
            print(f"--- Chunk {i} ---")
            print(f"Source : {props.get('source')}")
            print(f"Section: {props.get('section')}")
            print(f"Text   :\n{props.get('text')}")  # full text, no truncation
            print()

finally:
    client.close()