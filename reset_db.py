"""
Quick script to reset Milvus collection.
⚠️  Run from project root: python reset_milvus.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.vectorstore.milvus_store import MilvusStore
from src.config.settings import settings

print("⚠️  WARNING: This will DELETE all data and recreate the collection!")
response = input("Type 'DELETE' to confirm: ").strip()

if response != "DELETE":
    print("✓ Cancelled")
    sys.exit(0)

# Drop and recreate
milvus = MilvusStore(
    host=settings.milvus_host,
    port=str(settings.milvus_port),
    collection_name=settings.milvus_collection
)

old_count = milvus.collection.num_entities
print(f"Dropping {old_count} segments...")

milvus.drop_collection()
print("✓ Dropped")

# Recreate
new_milvus = MilvusStore(
    host=settings.milvus_host,
    port=str(settings.milvus_port),
    collection_name=settings.milvus_collection
)

print("✅ New collection created with Bible verse fields!")
print("You can now re-ingest your episodes.")