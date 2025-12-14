from src.vectorstore.milvus_store import MilvusStore
from pymilvus import connections, utility

# Connect
connections.connect('default', host='localhost', port='19530')

# List all collections
print('📚 All collections in Milvus:')
collections = utility.list_collections()
for col in collections:
    print(f'  - {col}')

print()

# Check the podcast_segments collection
store = MilvusStore()
print(f'📊 Collection: {store.collection_name}')
print(f'   Total entities: {store.collection.num_entities}')

# Try to query
results = store.query(expr='segment_id >= 0', limit=10)
print(f'   Query returned: {len(results)} results')

if results:
    print(f'   First result: {results[0]}')
else:
    print('   ⚠️  Collection is empty!')