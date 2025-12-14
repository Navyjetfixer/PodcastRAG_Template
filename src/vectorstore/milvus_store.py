"""
Milvus vector store for semantic search.
Handles storage and retrieval of embedded podcast segments with automatic type normalization.
Includes support for Bible verse reference tracking and filtering.
"""
from pymilvus import (
    connections,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
    utility
)
from typing import List, Dict, Any, Optional, Tuple, Union
import time


class MilvusStore:
    """
    Vector store using Milvus for semantic search with automatic type normalization.
    
    All query and search methods return normalized Python types (str, int, float)
    instead of Milvus internal types (int64, numpy types, etc.).
    
    Features:
    - Automatic collection creation with proper schema
    - Bible verse reference tracking and filtering
    - Batch insertion with progress tracking
    - Semantic search with metadata filtering
    - Universal type normalization for all queries
    - Consistent API across all methods
    - Respects Milvus query limits (16,384 max results)
    - Proper escaping of special characters in expressions
    
    Attributes:
        collection: Milvus collection instance
        collection_name: Name of the collection
        metric_type: Distance metric (L2, IP, COSINE)
        MAX_QUERY_LIMIT: Milvus hard limit for query results
    """
    
    # Milvus hard limit for query results
    MAX_QUERY_LIMIT = 16384
    
    def __init__(
        self,
        host: str = "localhost",
        port: str = "19530",
        collection_name: str = "podcast_segments",
        embedding_dim: int = 384,
        metric_type: str = "COSINE",
        index_type: str = "IVF_FLAT",
        index_params: Optional[Dict] = None
    ):
        """
        Initialize Milvus connection and collection.
        
        Args:
            host: Milvus server host
            port: Milvus server port
            collection_name: Name of the collection to use/create
            embedding_dim: Dimension of embedding vectors
            metric_type: Distance metric (L2, IP, COSINE)
            index_type: Index type (IVF_FLAT, HNSW, etc.)
            index_params: Custom index parameters
        """
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.metric_type = metric_type
        self.index_type = index_type
        
        # Default index params
        if index_params is None:
            self.index_params = {
                "metric_type": metric_type,
                "index_type": index_type,
                "params": {"nlist": 128}
            }
        else:
            self.index_params = index_params
        
        # Connect to Milvus
        print(f"🔗 Connecting to Milvus at {host}:{port}...")
        connections.connect("default", host=host, port=port)
        print("✅ Connected to Milvus")
        
        # Initialize collection
        self._init_collection()
    
    # ============================================
    # Collection Management
    # ============================================
    
    def _init_collection(self):
        """Initialize or load existing collection."""
        if utility.has_collection(self.collection_name):
            print(f"📂 Loading existing collection: {self.collection_name}")
            self.collection = Collection(self.collection_name)
            self.collection.load()
            print(f"✅ Collection loaded ({self.collection.num_entities} segments)")
        else:
            print(f"🏗️  Creating new collection: {self.collection_name}")
            self._create_collection()
            print("✅ Collection created")
    
    def _create_collection(self):
        """Create a new collection with the proper schema including Bible verse fields."""
        # Define schema
        fields = [
            FieldSchema(
                name="segment_id",
                dtype=DataType.INT64,
                is_primary=True,
                auto_id=True,
                description="Unique segment identifier"
            ),
            FieldSchema(
                name="episode_id",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Episode identifier"
            ),
            FieldSchema(
                name="episode_title",
                dtype=DataType.VARCHAR,
                max_length=500,
                description="Episode title"
            ),
            FieldSchema(
                name="text",
                dtype=DataType.VARCHAR,
                max_length=65535,
                description="Transcript segment text"
            ),
            FieldSchema(
                name="start_time",
                dtype=DataType.VARCHAR,
                max_length=20,
                description="Segment start time"
            ),
            FieldSchema(
                name="end_time",
                dtype=DataType.VARCHAR,
                max_length=20,
                description="Segment end time"
            ),
            FieldSchema(
                name="word_count",
                dtype=DataType.INT64,
                description="Number of words in segment"
            ),
            # ========================================
            # Bible verse reference fields
            # ========================================
            FieldSchema(
                name="has_verses",
                dtype=DataType.BOOL,
                description="Whether segment contains Bible verse references"
            ),
            FieldSchema(
                name="verse_count",
                dtype=DataType.INT64,
                description="Number of verse references in segment"
            ),
            FieldSchema(
                name="verse_references",
                dtype=DataType.VARCHAR,
                max_length=1000,
                description="Comma-separated list of verse references"
            ),
            FieldSchema(
                name="books_mentioned",
                dtype=DataType.VARCHAR,
                max_length=500,
                description="Comma-separated list of Bible books mentioned"
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.embedding_dim,
                description="Embedding vector"
            )
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description="Podcast transcript segments with embeddings and Bible verse references"
        )
        
        # Create collection
        self.collection = Collection(
            name=self.collection_name,
            schema=schema
        )
        
        # Create index on embedding field
        print(f"🔧 Creating index ({self.index_type})...")
        self.collection.create_index(
            field_name="embedding",
            index_params=self.index_params
        )
        
        # Load collection
        self.collection.load()
    
    # ============================================
    # String Escaping for Milvus Expressions
    # ============================================
    
    @staticmethod
    def _escape_milvus_string(value: str) -> str:
        """
        Escape special characters in strings for Milvus filter expressions.
        
        Milvus expressions use double quotes for strings, so internal quotes
        and backslashes must be escaped.
        
        Args:
            value: String to escape
            
        Returns:
            Escaped string safe for Milvus expressions
            
        Examples:
            >>> MilvusStore._escape_milvus_string('episode_108_"biblical"_marriage')
            'episode_108_\\"biblical\\"_marriage'
        """
        # Escape backslashes first (must be first!)
        value = value.replace("\\", "\\\\")
        # Escape double quotes
        value = value.replace('"', '\\"')
        return value
    
    # ============================================
    # Type Normalization (Universal)
    # ============================================
    
    def _normalize_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a Milvus entity to Python standard types.

        This is the single source of truth for type conversion.
        All query and search methods use this.

        Converts:
        - int64 → int (for segment_id) - Keep as int for consistency with delete operations
        - int64 → int (for word_count, verse_count)
        - bool → bool (for has_verses)
        - varchar → str (for all text fields)
        - numpy types → Python types

        Args:
            entity: Raw entity dict from Milvus

        Returns:
            Normalized entity with standard Python types
        """
        # Handle None/empty entities
        if not entity:
            return {}

        # Extract and convert each field with safe defaults
        normalized = {
            "segment_id": int(entity.get("segment_id", 0)),  # Changed from str to int
            "episode_id": str(entity.get("episode_id", "")),
            "episode_title": str(entity.get("episode_title", "Unknown")),
            "text": str(entity.get("text", "")),
            "start_time": str(entity.get("start_time", "00:00:00")),
            "end_time": str(entity.get("end_time", "00:00:00")),
            "word_count": int(entity.get("word_count", 0)),
            # Bible verse fields
            "has_verses": bool(entity.get("has_verses", False)),
            "verse_count": int(entity.get("verse_count", 0)),
            "verse_references": str(entity.get("verse_references", "")),
            "books_mentioned": str(entity.get("books_mentioned", ""))
        }
        
        # Preserve any extra fields (like embeddings)
        for key, value in entity.items():
            if key not in normalized:
                # Try to convert numpy/special types to Python types
                if hasattr(value, 'item'):  # numpy scalar
                    normalized[key] = value.item()
                elif hasattr(value, 'tolist'):  # numpy array
                    normalized[key] = value.tolist()
                else:
                    normalized[key] = value
        
        return normalized
    
    def _normalize_search_hit(self, hit: Any) -> Dict[str, Any]:
        """
        Normalize a search hit object to standard types.
        
        Search hits have both entity data and a score.
        
        Args:
            hit: Milvus search hit object
            
        Returns:
            Normalized result with entity data + score
        """
        # Extract entity data
        entity = {}
        if hasattr(hit, 'entity'):
            # Convert entity to dict
            for field in ['segment_id', 'episode_id', 'episode_title', 
                         'text', 'start_time', 'end_time', 'word_count',
                         'has_verses', 'verse_count', 'verse_references', 'books_mentioned']:
                if hasattr(hit.entity, field):
                    entity[field] = getattr(hit.entity, field)
                elif hasattr(hit.entity, 'get'):
                    entity[field] = hit.entity.get(field)
        
        # Normalize entity fields
        result = self._normalize_entity(entity)
        
        # Add search score
        if hasattr(hit, 'score'):
            result['score'] = float(hit.score)
        
        return result
    
    # ============================================
    # Data Insertion
    # ============================================
    
    def insert_segments(
        self,
        segments: List[Dict[str, Any]],
        batch_size: int = 100,
        show_progress: bool = True
    ) -> int:
        """
        Insert segments with embeddings and verse metadata into the collection.
        
        Args:
            segments: List of segment dicts with keys:
                - episode_id (str)
                - episode_title (str)
                - text (str)
                - start_time (str)
                - end_time (str)
                - word_count (int)
                - has_verses (bool)
                - verse_count (int)
                - verse_references (str)
                - books_mentioned (str)
                - embedding (List[float])
            batch_size: Number of segments per batch
            show_progress: Whether to print progress
        
        Returns:
            Number of segments inserted
        """
        if not segments:
            print("⚠️  No segments to insert")
            return 0
        
        total_segments = len(segments)
        inserted_count = 0
        
        print(f"📥 Inserting {total_segments} segments in batches of {batch_size}...")
        start_time = time.time()
        
        # Process in batches
        for i in range(0, total_segments, batch_size):
            batch = segments[i:i + batch_size]
            
            # Prepare data for insertion (MUST match schema field order)
            data = [
                [seg.get("episode_id", "") for seg in batch],
                [seg.get("episode_title", "") for seg in batch],
                [seg.get("text", "") for seg in batch],
                [seg.get("start_time", "00:00:00") for seg in batch],
                [seg.get("end_time", "00:00:00") for seg in batch],
                [int(seg.get("word_count", 0)) for seg in batch],
                # Bible verse fields
                [bool(seg.get("has_verses", False)) for seg in batch],
                [int(seg.get("verse_count", 0)) for seg in batch],
                [seg.get("verse_references", "") for seg in batch],
                [seg.get("books_mentioned", "") for seg in batch],
                [seg["embedding"] for seg in batch]
            ]
            
            # Insert batch
            try:
                self.collection.insert(data)
                inserted_count += len(batch)
                
                if show_progress:
                    progress = (inserted_count / total_segments) * 100
                    print(f"  Progress: {inserted_count}/{total_segments} ({progress:.1f}%)")
                    
            except Exception as e:
                print(f"❌ Error inserting batch {i}-{i+batch_size}: {e}")
                continue
        
        # Flush to persist data
        self.collection.flush()
        
        elapsed_time = time.time() - start_time
        print(f"✅ Inserted {inserted_count} segments in {elapsed_time:.2f}s")
        
        return inserted_count
    
    # ============================================
    # Query Operations (Normalized)
    # ============================================
    
    def query(
        self,
        expr: str,
        output_fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Query collection with automatic type normalization.
        
        This wraps Milvus collection.query() and normalizes all results.
        Respects Milvus MAX_QUERY_LIMIT of 16,384.
        
        Args:
            expr: Filter expression (e.g., 'episode_id == "ep001"')
            output_fields: Fields to return (None = all except embedding)
            limit: Maximum number of results (capped at MAX_QUERY_LIMIT)
            offset: Number of results to skip
            **kwargs: Additional query parameters
        
        Returns:
            List of normalized entity dictionaries
        """
        # Ensure collection is loaded
        self.collection.load()
        
        # Cap limit to Milvus maximum
        if limit > self.MAX_QUERY_LIMIT:
            print(f"⚠️  Query limit {limit} exceeds Milvus max {self.MAX_QUERY_LIMIT}, capping to max")
            limit = self.MAX_QUERY_LIMIT
        
        # Check offset + limit doesn't exceed maximum
        if offset + limit > self.MAX_QUERY_LIMIT:
            adjusted_limit = self.MAX_QUERY_LIMIT - offset
            if adjusted_limit <= 0:
                print(f"⚠️  Offset {offset} exceeds maximum query window")
                return []
            print(f"⚠️  Adjusting limit from {limit} to {adjusted_limit} due to offset")
            limit = adjusted_limit
        
        # Default output fields (exclude embedding for performance)
        if output_fields is None:
            output_fields = [
                "segment_id",
                "episode_id",
                "episode_title",
                "text",
                "start_time",
                "end_time",
                "word_count",
                "has_verses",
                "verse_count",
                "verse_references",
                "books_mentioned"
            ]
        
        # Execute query
        try:
            results = self.collection.query(
                expr=expr,
                output_fields=output_fields,
                limit=limit,
                offset=offset,
                **kwargs
            )
        except Exception as e:
            print(f"❌ Query error: {e}")
            return []
        
        # Normalize all results
        return [self._normalize_entity(entity) for entity in results]
    
    def query_all(
        self,
        output_fields: Optional[List[str]] = None,
        batch_size: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query all entities in batches with normalization.
        
        Useful for getting all data without hitting query limits.
        Uses pagination to work within Milvus MAX_QUERY_LIMIT.
        
        Args:
            output_fields: Fields to return
            batch_size: Number of entities per batch
        
        Returns:
            List of all normalized entities (up to MAX_QUERY_LIMIT total)
        """
        all_results = []
        offset = 0
        
        while offset < self.MAX_QUERY_LIMIT:
            # Calculate how many we can fetch
            remaining = self.MAX_QUERY_LIMIT - offset
            current_batch_size = min(batch_size, remaining)
            
            batch = self.query(
                expr="segment_id >= 0",
                output_fields=output_fields,
                limit=current_batch_size,
                offset=offset
            )
            
            if not batch:
                break
            
            all_results.extend(batch)
            offset += len(batch)
            
            # If we got fewer results than requested, we've reached the end
            if len(batch) < current_batch_size:
                break
        
        if offset >= self.MAX_QUERY_LIMIT and len(all_results) == self.MAX_QUERY_LIMIT:
            print(f"⚠️  Reached Milvus query limit ({self.MAX_QUERY_LIMIT}). There may be more data.")
        
        return all_results
    
    # ============================================
    # Search Operations (Normalized)
    # ============================================
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar segments with automatic normalization.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_expr: Optional filter expression (e.g., 'episode_id == "ep001"' or 'has_verses == true')
            output_fields: Fields to return (None = all)
        
        Returns:
            List of normalized search results with 'score' field
        """
        if output_fields is None:
            output_fields = [
                "segment_id",
                "episode_id",
                "episode_title",
                "text",
                "start_time",
                "end_time",
                "word_count",
                "has_verses",
                "verse_count",
                "verse_references",
                "books_mentioned"
            ]
        
        # Ensure collection is loaded
        self.collection.load()
        
        # Search parameters
        search_params = {
            "metric_type": self.metric_type,
            "params": {"nprobe": 10}
        }
        
        # Perform search
        try:
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=output_fields
            )
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
        
        # Normalize results
        normalized_results = []
        for hits in results:
            for hit in hits:
                normalized = self._normalize_search_hit(hit)
                normalized_results.append(normalized)
        
        return normalized_results
    
    def search_with_metadata(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        episode_ids: Optional[List[str]] = None,
        min_word_count: Optional[int] = None,
        max_word_count: Optional[int] = None,
        has_verses: Optional[bool] = None,
        books_mentioned: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search with metadata filtering and normalization.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            episode_ids: Filter by specific episode IDs
            min_word_count: Minimum word count filter
            max_word_count: Maximum word count filter
            has_verses: Filter for segments with/without verses
            books_mentioned: Filter by Bible books mentioned
        
        Returns:
            List of normalized search results
        """
        # Build filter expression with proper escaping
        filters = []
        
        if episode_ids:
            escaped_ids = [self._escape_milvus_string(eid) for eid in episode_ids]
            episode_filter = " or ".join([f'episode_id == "{eid}"' for eid in escaped_ids])
            filters.append(f"({episode_filter})")
        
        if min_word_count is not None:
            filters.append(f"word_count >= {min_word_count}")
        
        if max_word_count is not None:
            filters.append(f"word_count <= {max_word_count}")
        
        # Bible verse filters
        if has_verses is not None:
            filters.append(f"has_verses == {'true' if has_verses else 'false'}")
        
        if books_mentioned:
            book_filters = [f'books_mentioned like "%{book}%"' for book in books_mentioned]
            filters.append(f"({' or '.join(book_filters)})")
        
        filter_expr = " and ".join(filters) if filters else None
        
        return self.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_expr=filter_expr
        )
    
    # ============================================
    # Utility Methods (Normalized)
    # ============================================
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics including verse data.
        
        Returns:
            Dictionary with collection stats
        """
        self.collection.load()
        
        # Count segments with verses
        verse_segments = self.count_segments("has_verses == true")
        
        return {
            "name": self.collection_name,
            "num_entities": self.collection.num_entities,
            "segments_with_verses": verse_segments,
            "schema": str(self.collection.schema),
            "indexes": [str(idx) for idx in self.collection.indexes]
        }
    
    def count_segments(self, filter_expr: Optional[str] = None) -> int:
        """
        Count segments matching a filter.
        
        Args:
            filter_expr: Optional filter expression (e.g., 'has_verses == true')
        
        Returns:
            Number of matching segments
        """
        self.collection.load()
        
        if filter_expr:
            # For filtered counts, we need to query and count
            # This is limited by MAX_QUERY_LIMIT
            results = self.query(
                expr=filter_expr,
                output_fields=["segment_id"],
                limit=self.MAX_QUERY_LIMIT
            )
            count = len(results)
            if count == self.MAX_QUERY_LIMIT:
                print(f"⚠️  Count may be incomplete (hit limit of {self.MAX_QUERY_LIMIT})")
            return count
        else:
            return self.collection.num_entities
    
    def get_segment_by_id(self, segment_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific segment by ID with normalization.
        
        Args:
            segment_id: Segment ID (int or string)
        
        Returns:
            Normalized segment data or None if not found
        """
        # Convert to int for query
        if isinstance(segment_id, str):
            try:
                segment_id = int(segment_id)
            except ValueError:
                print(f"⚠️  Invalid segment_id: {segment_id}")
                return None
        
        results = self.query(
            expr=f"segment_id == {segment_id}",
            limit=1
        )
        
        return results[0] if results else None
    
    def get_segments_by_episode(
        self,
        episode_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all segments for an episode with normalization.
        
        Args:
            episode_id: Episode ID
            limit: Maximum segments to return (None = MAX_QUERY_LIMIT)
        
        Returns:
            List of normalized segments
        """
        if limit is None:
            limit = self.MAX_QUERY_LIMIT
        
        # Escape special characters in episode_id
        escaped_id = self._escape_milvus_string(episode_id)
        
        return self.query(
            expr=f'episode_id == "{escaped_id}"',
            limit=limit
        )
    
    def get_unique_episodes(self) -> List[Dict[str, str]]:
        """
        Get list of unique episodes with normalization.
        
        Queries up to MAX_QUERY_LIMIT segments and extracts unique episodes.
        If you have more segments than the limit, some episodes may not appear.
        
        Returns:
            List of dicts with 'episode_id' and 'episode_title'
        """
        # Query segments (respecting Milvus limit)
        all_segments = self.query(
            expr="segment_id >= 0",
            output_fields=["episode_id", "episode_title"],
            limit=self.MAX_QUERY_LIMIT
        )
        
        if not all_segments:
            return []
        
        # Extract unique episodes
        episodes_dict = {}
        for segment in all_segments:
            ep_id = segment["episode_id"]
            if ep_id not in episodes_dict:
                episodes_dict[ep_id] = {
                    "episode_id": ep_id,
                    "episode_title": segment["episode_title"]
                }
        
        episodes_list = list(episodes_dict.values())
        
        # Warn if we might have hit the limit
        if len(all_segments) == self.MAX_QUERY_LIMIT:
            print(f"⚠️  Retrieved {self.MAX_QUERY_LIMIT} segments. If you have more episodes, some may not be listed.")
        
        return episodes_list
    
    def episode_exists(self, episode_id: str) -> bool:
        """
        Check if an episode exists by episode_id.
        
        Args:
            episode_id: Episode ID to check
        
        Returns:
            True if episode exists, False otherwise
        """
        try:
            # Escape special characters
            escaped_id = self._escape_milvus_string(episode_id)
            
            results = self.query(
                expr=f'episode_id == "{escaped_id}"',
                output_fields=["episode_id"],
                limit=1
            )
            return len(results) > 0
        except Exception as e:
            print(f"⚠️  Error checking episode existence: {e}")
            return False
    
    def episode_exists_by_title(self, title: str) -> bool:
        """
        Check if an episode exists by title.
        
        Note: Uses exact string match with proper escaping.
        
        Args:
            title: Episode title to check
        
        Returns:
            True if episode exists, False otherwise
        """
        try:
            # Escape special characters in title
            escaped_title = self._escape_milvus_string(title)
            
            results = self.query(
                expr=f'episode_title == "{escaped_title}"',
                output_fields=["episode_title"],
                limit=1
            )
            return len(results) > 0
        except Exception as e:
            # If query fails, fall back to fetching all and comparing
            try:
                episodes = self.get_unique_episodes()
                return any(ep["episode_title"] == title for ep in episodes)
            except Exception as e2:
                print(f"⚠️  Error checking episode by title: {e2}")
                return False
    
    def get_episode_count(self) -> int:
        """
        Get the total number of unique episodes in the database.
        
        Returns:
            Number of unique episodes
        """
        episodes = self.get_unique_episodes()
        return len(episodes)
    
    def delete_segments(self, segment_ids: List[int]) -> bool:
        """
        Delete segments by ID.
        
        Args:
            segment_ids: List of segment IDs to delete
        
        Returns:
            True if successful
        """
        try:
            expr = f"segment_id in {segment_ids}"
            self.collection.delete(expr)
            self.collection.flush()
            print(f"✅ Deleted {len(segment_ids)} segments")
            return True
        except Exception as e:
            print(f"❌ Error deleting segments: {e}")
            return False
    
    def delete_episode(self, episode_id: str) -> Dict[str, Any]:
        """
        Delete all segments for an episode.
        
        Note: Limited to MAX_QUERY_LIMIT segments per episode.
        
        Args:
            episode_id: Episode ID
        
        Returns:
            Dict with deletion info
        """
        # Get all segments for episode (this now escapes episode_id)
        segments = self.get_segments_by_episode(episode_id)
        
        if not segments:
            return {
                "success": False,
                "message": f"Episode '{episode_id}' not found",
                "segments_deleted": 0
            }
        
        # Extract segment IDs (already int from normalization)
        segment_ids = [seg["segment_id"] for seg in segments]
        
        # Warn if we hit the limit
        if len(segments) == self.MAX_QUERY_LIMIT:
            print(f"⚠️  Episode has {self.MAX_QUERY_LIMIT}+ segments. Only first {self.MAX_QUERY_LIMIT} will be deleted.")
        
        # Delete
        success = self.delete_segments(segment_ids)
        
        return {
            "success": success,
            "message": "Episode deleted successfully" if success else "Deletion failed",
            "episode_id": episode_id,
            "segments_deleted": len(segment_ids) if success else 0
        }
    
    def clear_collection(self) -> bool:
        """
        Delete all segments from the collection.
        
        Note: Limited to MAX_QUERY_LIMIT segments.
        
        Returns:
            True if successful
        """
        try:
            # Get all segment IDs
            results = self.query(
                expr="segment_id >= 0",
                output_fields=["segment_id"],
                limit=self.MAX_QUERY_LIMIT
            )
            
            if results:
                segment_ids = [r["segment_id"] for r in results]  # Already int from normalization
                return self.delete_segments(segment_ids)
            
            return True
            
        except Exception as e:
            print(f"❌ Error clearing collection: {e}")
            return False
    
    def drop_collection(self):
        """Drop (delete) the entire collection."""
        print(f"🗑️  Dropping collection: {self.collection_name}")
        utility.drop_collection(self.collection_name)
        print("✅ Collection dropped")
    
    def create_index(self, force: bool = False):
        """
        Create or recreate index on embedding field.
        
        Args:
            force: If True, drop existing index first
        """
        if force:
            try:
                self.collection.drop_index()
                print("🗑️  Dropped existing index")
            except Exception:
                pass
        
        print(f"🔧 Creating index ({self.index_type})...")
        self.collection.create_index(
            field_name="embedding",
            index_params=self.index_params
        )
        self.collection.load()
        print("✅ Index created")
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MilvusStore(collection={self.collection_name}, entities={self.collection.num_entities})"
    
    def __str__(self) -> str:
        """Human-readable string."""
        return f"Milvus Vector Store: {self.collection_name}"


# ============================================
# Convenience Functions
# ============================================

def create_milvus_store(
    host: str = "localhost",
    port: str = "19530",
    collection_name: str = "podcast_segments",
    embedding_dim: int = 384
) -> MilvusStore:
    """
    Factory function to create a Milvus store.
    
    Args:
        host: Milvus server host
        port: Milvus server port
        collection_name: Collection name
        embedding_dim: Embedding dimension
    
    Returns:
        Configured MilvusStore instance
    """
    return MilvusStore(
        host=host,
        port=port,
        collection_name=collection_name,
        embedding_dim=embedding_dim
    )


# ============================================
# Module-level test
# ============================================

if __name__ == "__main__":
    print("🧪 Testing MilvusStore with normalization and verse support...")
    
    # Create store
    store = create_milvus_store()
    
    # Get stats
    stats = store.get_collection_stats()
    print(f"\n📊 Collection Stats:")
    print(f"  Name: {stats['name']}")
    print(f"  Entities: {stats['num_entities']}")
    print(f"  Segments with verses: {stats.get('segments_with_verses', 0)}")
    
    print("\n✅ Test complete!")