"""
Diagnostic utilities for the search system.
"""
from src.vectorstore.milvus_store import MilvusStore
from src.config.settings import settings

def check_collection_stats():
    """Display collection statistics."""
    milvus = MilvusStore(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        collection_name=settings.milvus_collection
    )
    
    # Get collection info
    collection = milvus.collection
    print(f"\n📊 Collection: {settings.milvus_collection}")
    print(f"   Total entities: {collection.num_entities}")
    
    # Sample some data
    results = collection.query(
        expr="segment_id >= 0",
        limit=100,
        output_fields=["episode_id", "episode_title", "segment_id", "verse_references", "text"]
    )
    
    # Get unique episodes
    episodes = {}
    for r in results:
        ep_id = r.get('episode_id')
        if ep_id not in episodes:
            episodes[ep_id] = {
                'title': r.get('episode_title'),
                'segments': 0
            }
        episodes[ep_id]['segments'] += 1
        
    verses = {}
    for v in results:
        verse = v.get('verse_reference')
        print(verse)
    
    print(f"\n📚 Episodes in collection:")
    for ep_id, info in episodes.items():
        print(f"   - {info['title']} ({ep_id}): {info['segments']} segments")
    
    print(f"\n📝 Sample segments:")
    for i, r in enumerate(results[:3], 1):
        text_preview = r['text'][:100] + "..." if len(r['text']) > 100 else r['text']
        print(f"\n   {i}. [{r['episode_title']}] Segment {r['segment_id']}")
        print(f"      {text_preview}")

if __name__ == "__main__":
    check_collection_stats()