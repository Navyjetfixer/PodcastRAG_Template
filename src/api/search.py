"""
Enhanced search endpoints with filters and advanced ranking.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import sys
from pathlib import Path
import traceback

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vectorstore.milvus_store import MilvusStore
from embeddings.embedder import Embedder
from config.settings import settings

router = APIRouter()

# Initialize services
try:
    milvus = MilvusStore(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        collection_name=settings.milvus_collection
    )
    embedder = Embedder()
    print("✅ Search services initialized")
except Exception as e:
    print(f"⚠️  Warning: Could not initialize search services: {e}")
    milvus = None
    embedder = None


# ============================================================================
# MODELS
# ============================================================================

class SearchResult(BaseModel):
    """Enhanced search result with metadata."""
    segment_id: int
    episode_id: str
    episode_title: str
    text: str
    similarity_score: float
    segment_index: int
    timestamp: Optional[str] = None
    word_count: int
    has_verses: bool = False
    verse_references: Optional[str] = None
    books_mentioned: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    query: str
    total_results: int
    results: List[SearchResult]
    filters_applied: dict
    search_time_ms: float


class SearchFilters(BaseModel):
    """Available search filters."""
    episodes: Optional[List[str]] = None
    books: Optional[List[str]] = None
    min_score: Optional[float] = None
    has_verses: Optional[bool] = None
    limit: int = 10


# ============================================================================
# ENHANCED SEARCH ENDPOINT
# ============================================================================

@router.post("/", response_model=SearchResponse)
async def enhanced_search(
    query: str = Query(..., min_length=1, description="Search query"),
    episodes: Optional[List[str]] = Query(None, description="Filter by episode IDs"),
    books: Optional[List[str]] = Query(None, description="Filter by Bible books"),
    min_score: Optional[float] = Query(None, ge=0, le=1, description="Minimum similarity score"),
    has_verses: Optional[bool] = Query(None, description="Only return segments with Bible verses"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return")
):
    """
    Enhanced semantic search with filters.
    
    Filters:
    - episodes: List of episode IDs to search within
    - books: List of Bible books to filter by
    - min_score: Minimum similarity score (0-1)
    - has_verses: Only return segments containing Bible verses
    - limit: Max number of results (1-100)
    """
    if not milvus or not embedder:
        raise HTTPException(status_code=503, detail="Search service not available")
    
    start_time = datetime.now()
    
    try:
        print(f"\n🔍 ENHANCED SEARCH")
        print(f"   Query: '{query}'")
        print(f"   Filters: episodes={episodes}, books={books}, min_score={min_score}, has_verses={has_verses}")
        
        # Generate query embedding
        query_embedding = embedder.embed([query])[0]
        
        # Build filter expression
        filter_parts = []
        
        # Episode filter
        if episodes:
            episode_filter = " or ".join([f'episode_id == "{ep}"' for ep in episodes])
            filter_parts.append(f"({episode_filter})")
        
        # Bible book filter
        if books:
            book_filters = [f'books_mentioned like "%{book}%"' for book in books]
            book_filter = " or ".join(book_filters)
            filter_parts.append(f"({book_filter})")
        
        # Verse filter
        if has_verses:
            filter_parts.append("verse_count > 0")
        
        # Combine filters
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        print(f"   Filter expression: {filter_expr}")
        
        # Perform search
        raw_results = milvus.search(
            query_embedding=query_embedding,
            top_k=limit * 2,
            filter_expr=filter_expr
        )
        
        # Apply score filtering and format results
        results = []
        for r in raw_results:
            score = r.get("similarity_score", 0)
            
            # Apply minimum score filter
            if min_score and score < min_score:
                continue
            
            results.append(SearchResult(
                segment_id=r["segment_id"],
                episode_id=r["episode_id"],
                episode_title=r["episode_title"],
                text=r["text"],
                similarity_score=round(score, 4),
                segment_index=r["segment_index"],
                timestamp=r.get("timestamp"),
                word_count=r["word_count"],
                has_verses=r.get("verse_count", 0) > 0,
                verse_references=r.get("verse_references"),
                books_mentioned=r.get("books_mentioned")
            ))
            
            if len(results) >= limit:
                break
        
        # Calculate search time
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        print(f"   ✅ Found {len(results)} results in {search_time:.2f}ms")
        
        return SearchResponse(
            query=query,
            total_results=len(results),
            results=results,
            filters_applied={
                "episodes": episodes,
                "books": books,
                "min_score": min_score,
                "has_verses": has_verses,
                "limit": limit
            },
            search_time_ms=round(search_time, 2)
        )
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Search error:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET AVAILABLE FILTERS
# ============================================================================

@router.get("/filters")
async def get_available_filters():
    """Get all available filter options (episodes, books)."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Search service not available")
    
    try:
        print("📋 Fetching available search filters...")
        
        # Get all unique episodes
        episodes = milvus.get_unique_episodes()
        episode_list = [
            {"episode_id": ep["episode_id"], "title": ep["episode_title"]}
            for ep in episodes
        ]
        
        # Get all unique books mentioned
        all_segments = milvus.collection.query(
            expr="verse_count > 0",
            output_fields=["books_mentioned"],
            limit=10000
        )
        
        books_set = set()
        for seg in all_segments:
            books = seg.get("books_mentioned", "")
            if books:
                for book in books.split(","):
                    books_set.add(book.strip())
        
        books_list = sorted(list(books_set))
        
        print(f"✅ Found {len(episode_list)} episodes and {len(books_list)} books")
        
        return {
            "episodes": episode_list,
            "books": books_list,
            "min_score_range": [0.0, 1.0],
            "max_limit": 100
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error fetching filters:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SEARCH SUGGESTIONS
# ============================================================================

@router.get("/suggest")
async def search_suggestions(
    query: str = Query(..., min_length=2, description="Partial search query")
):
    """Get search suggestions based on partial query."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Search service not available")
    
    try:
        print(f"💡 Getting suggestions for: '{query}'")
        
        suggestions = []
        
        # Suggest episodes that match
        episodes = milvus.get_unique_episodes()
        for ep in episodes:
            if query.lower() in ep["episode_title"].lower():
                suggestions.append({
                    "type": "episode",
                    "text": ep["episode_title"],
                    "value": ep["episode_id"]
                })
        
        # Suggest Bible books
        bible_books = [
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
            "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
            "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
            "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
            "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
            "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
            "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
            "Zephaniah", "Haggai", "Zechariah", "Malachi",
            "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
            "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
            "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
            "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
            "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
            "Jude", "Revelation"
        ]
        
        for book in bible_books:
            if query.lower() in book.lower():
                suggestions.append({
                    "type": "book",
                    "text": book,
                    "value": book
                })
        
        print(f"✅ Found {len(suggestions)} suggestions")
        
        return {
            "query": query,
            "suggestions": suggestions[:10]
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error getting suggestions:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MULTI-VERSE SEARCH
# ============================================================================

@router.get("/verse/{book}/{chapter}")
async def search_by_verse_reference(
    book: str,
    chapter: int,
    verse: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search for segments that reference a specific Bible verse or chapter.
    
    Examples:
    - /verse/Genesis/1 - All segments referencing Genesis chapter 1
    - /verse/John/3?verse=16 - All segments referencing John 3:16
    """
    if not milvus:
        raise HTTPException(status_code=503, detail="Search service not available")
    
    try:
        # Build search pattern
        if verse:
            search_pattern = f"{book} {chapter}:{verse}"
            print(f"🔍 Searching for verse: {search_pattern}")
        else:
            search_pattern = f"{book} {chapter}:"
            print(f"🔍 Searching for chapter: {book} {chapter}")
        
        # Query segments
        results = milvus.collection.query(
            expr=f'verse_references like "%{book}%"',
            output_fields=["segment_id", "episode_id", "episode_title", "text",
                          "verse_references", "verse_count", "segment_index"],
            limit=1000
        )
        
        # Filter for exact matches
        matching_segments = []
        for r in results:
            verse_refs = r.get("verse_references", "")
            if search_pattern in verse_refs:
                matching_segments.append({
                    "segment_id": r["segment_id"],
                    "episode_id": r["episode_id"],
                    "episode_title": r["episode_title"],
                    "text": r["text"],
                    "verse_references": verse_refs,
                    "segment_index": r["segment_index"]
                })
                
                if len(matching_segments) >= limit:
                    break
        
        print(f"✅ Found {len(matching_segments)} segments")
        
        return {
            "reference": search_pattern,
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "total_results": len(matching_segments),
            "segments": matching_segments
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error searching by verse:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))