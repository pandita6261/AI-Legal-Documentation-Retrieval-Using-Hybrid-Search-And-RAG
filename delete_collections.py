"""
delete_collection.py
----------------------
Completely deletes the 'LegalDocs' collection from Weaviate --
both the schema and all stored data inside it.

Use this when you want to start completely fresh (e.g. after testing,
or if you changed the schema/properties and need to recreate it).

After running this, the next PDF you upload will automatically
recreate the collection from scratch (since main.py calls
ensure_collection() before inserting anything).
"""

import weaviate

COLLECTION_NAME = "LegalDocs"

client = weaviate.connect_to_local()

try:
    if client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' deleted successfully.")
    else:
        print(f"Collection '{COLLECTION_NAME}' does not exist -- nothing to delete.")
finally:
    client.close()