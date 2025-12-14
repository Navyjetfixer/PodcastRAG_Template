"""
Query endpoints for semantic search and Q&A with advanced RAG features.

Endpoints:
- GET  /status             - System status and statistics
- POST /search             - Semantic search with filters and re-ranking
- GET  /answer             - Streaming Q&A with SSE
- GET  /conversation/{id}  - Get conversation history
- DELETE /conversation/{id} - Delete conversation
- GET  /conversations      - List all conversations
- GET  /filters            - Get available filter options (episodes, books)
- GET  /health             - Health check
"""
from fastapi import APIRouter, HTTPException, Query as QueryParam
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sse_starlette.sse import EventSourceResponse
import uuid
import sys
from pathlib import Path
import asyncio
import json
import traceback

# ============================================
# Path Setup
# ============================================

current_file = Path(__file__).resolve()
src_dir = current_file.parent.parent.parent  # routes -> web -> src
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# ============================================
# Imports
# ============================================

from vectorstore.milvus_store import MilvusStore
from embeddings.embedder import Embedder
from llm.openai_api import OpenAIClient
from config.settings import settings
from cli.conversation import ConversationHistory

# Optional: Import reranker if available
RERANKER_AVAILABLE = False
CrossEncoderReranker = None

try:
    from reranker.cross_encoder_reranker import CrossEncoderReranker
    RERANKER_AVAILABLE = True
    print("✅ Reranker module loaded")
except ImportError as e:
    print(f"⚠️  Reranker module not available: {e}")
    print("   Re-ranking will be disabled. Install with: poetry add sentence-transformers")

# ============================================
# Router Setup
# ============================================

router = APIRouter(
    prefix="",
    tags=["query"],
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Resource not found"}
    }
)

# ============================================
# Global Service Instances
# ============================================

_milvus: Optional[MilvusStore] = None
_embedder: Optional[Embedder] = None
_llm: Optional[OpenAIClient] = None
_reranker: Optional[Any] = None  # Can be CrossEncoderReranker or None
_conversation_dir = Path(".web_conversations")


def get_services() -> tuple[MilvusStore, Embedder, OpenAIClient, Optional[Any]]:
    """
    Lazy initialization of global services.
    Services are created once and reused across requests.
    
    Returns:
        Tuple of (MilvusStore, Embedder, OpenAIClient, CrossEncoderReranker|None)
    """
    global _milvus, _embedder, _llm, _reranker
    
    if _milvus is None:
        print("🔧 Initializing Milvus connection...")
        _milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
        print("✅ Milvus connected")
    
    if _embedder is None:
        print(f"🔧 Loading embedding model: {settings.embedding_model}...")
        _embedder = Embedder(model_name=settings.embedding_model)
        print("✅ Embedder ready")
    
    if _llm is None:
        print(f"🔧 Initializing OpenAI client (model: {settings.llm_model})...")
        _llm = OpenAIClient(model=settings.llm_model)
        print("✅ OpenAI client ready")
    
    # Initialize reranker if enabled AND available
    if RERANKER_AVAILABLE and settings.use_reranker and _reranker is None:
        try:
            print(f"🔧 Initializing re-ranker (model: {settings.reranker_model})...")
            _reranker = CrossEncoderReranker(model_name=settings.reranker_model)
            print("✅ Re-ranker ready")
        except Exception as e:
            print(f"❌ Failed to initialize re-ranker: {e}")
            print("   Continuing without re-ranking...")
            _reranker = None
    elif not RERANKER_AVAILABLE and settings.use_reranker:
        print("⚠️  Re-ranker requested but module not available")
    
    return _milvus, _embedder, _llm, _reranker


def ensure_conversation_dir():
    """Ensure conversation storage directory exists."""
    _conversation_dir.mkdir(exist_ok=True)


# Initialize on module load
ensure_conversation_dir()


# ============================================
# Request/Response Models
# ============================================

class SearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    
    # ===== ENHANCED FILTERS =====
    episode_filter: Optional[str] = Field(None, description="Filter by episode ID (single, deprecated - use episodes)")
    episodes: Optional[List[str]] = Field(None, description="Filter by episode IDs (multiple)")
    books: Optional[List[str]] = Field(None, description="Filter by Bible books mentioned")
    has_verses: Optional[bool] = Field(None, description="Only return segments with Bible verses")
    # ============================
    
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score threshold")
    use_rewrite: bool = Field(True, description="Enable query rewriting for better results")
    use_context: bool = Field(True, description="Use conversation context")
    use_reranker: bool = Field(True, description="Use cross-encoder re-ranking")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context tracking")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "query": "What does Paul say about grace?",
                "top_k": 5,
                "episodes": ["ep_123", "ep_456"],
                "books": ["Romans", "Ephesians"],
                "has_verses": True,
                "min_score": 0.3,
                "use_rewrite": True,
                "use_context": True,
                "use_reranker": True
            }]
        }
    }


class SearchResult(BaseModel):
    """Single search result."""
    segment_id: int  # Changed from str to int to match Milvus normalization
    episode_id: str
    episode_title: str
    text: str
    start_time: str
    end_time: str
    score: float
    word_count: int
    rerank_score: Optional[float] = None
    original_rank: Optional[int] = None
    has_verses: bool = False
    verse_count: int = 0
    verse_references: Optional[str] = None
    books_mentioned: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search results."""
    query: str
    rewritten_query: Optional[str] = None
    count: int
    results: List[SearchResult]
    conversation_id: Optional[str] = None
    reranked: bool = False
    rerank_metrics: Optional[Dict[str, Any]] = None


class SystemStatus(BaseModel):
    """System status information."""
    status: str
    milvus_connected: bool
    total_segments: int
    total_episodes: int
    embedding_model: str
    llm_model: str
    reranker_enabled: bool
    reranker_available: bool
    reranker_model: Optional[str] = None
    active_conversations: int


class ConversationInfo(BaseModel):
    """Conversation information."""
    conversation_id: str
    message_count: int
    messages: List[Dict[str, Any]]


class FilterOptions(BaseModel):
    """Available filter options for UI."""
    episodes: List[Dict[str, str]]
    books: List[str]
    min_score_range: List[float]
    top_k_range: List[int]


# ============================================
# Status Endpoint
# ============================================

@router.get("/status", response_model=SystemStatus)
async def get_status():
    """
    Get system status and statistics.
    
    Returns current health status, connection state, and usage statistics.
    """
    try:
        milvus, embedder, llm, reranker = get_services()
        
        # Count total segments
        try:
            total_segments = milvus.count_segments()
        except Exception:
            total_segments = 0
        
        # Count unique episodes (respecting Milvus limits)
        try:
            episodes = milvus.collection.query(
                expr="episode_id != ''",
                output_fields=["episode_id"],
                limit=16000  # Stay under 16,384 limit
            )
            unique_episodes = len(set(e.get("episode_id", "") for e in episodes))
        except Exception:
            unique_episodes = 0
        
        # Count active conversations
        active_convs = len(list(_conversation_dir.glob("*.json")))
        
        return SystemStatus(
            status="online",
            milvus_connected=True,
            total_segments=total_segments,
            total_episodes=unique_episodes,
            embedding_model=settings.embedding_model,
            llm_model=settings.llm_model,
            reranker_enabled=settings.use_reranker,
            reranker_available=RERANKER_AVAILABLE,
            reranker_model=settings.reranker_model if settings.use_reranker else None,
            active_conversations=active_convs
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )


# ============================================
# Search Endpoint (WITH BOTH FIXES)
# ============================================

@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Perform semantic search over podcast transcripts with optional re-ranking.
    
    Enhanced with Bible verse filtering:
    - Filter by multiple episodes
    - Filter by Bible books mentioned
    - Filter by segments containing verses
    
    Two-stage retrieval (if re-ranker available):
    1. Bi-encoder (Milvus) retrieves candidates (fast)
    2. Cross-encoder re-ranks top results (accurate)
    """
    try:
        milvus, embedder, llm, reranker = get_services()
        
        # Get or create conversation
        conversation_id = request.conversation_id or str(uuid.uuid4())
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        # Query rewriting
        query_to_use = request.query
        rewritten_query = None
        
        if request.use_rewrite:
            if request.use_context and len(conversation) > 0:
                # Context-aware rewriting
                context_messages = conversation.get_history()[-3:]
                rewritten_query = llm.rewrite_query_with_context(
                    request.query,
                    context_messages
                )
            else:
                # Standard rewriting
                rewritten_query = llm.rewrite_query(request.query)
            
            # Use rewritten query if different
            if rewritten_query and rewritten_query != request.query:
                query_to_use = rewritten_query
                print(f"🔄 Query rewritten: '{request.query}' -> '{rewritten_query}'")
        
        # Embed query
        query_embedding = embedder.embed(query_to_use)
        
        # ===== BUILD ENHANCED FILTER EXPRESSION (FIX #1) =====
        filter_parts = []
        post_filter_books = None  # Will filter these in Python after retrieval
        
        # Episode filter (support both old single and new multiple)
        episode_ids = []
        if request.episode_filter:
            episode_ids.append(request.episode_filter)
        if request.episodes:
            episode_ids.extend(request.episodes)
        
        if episode_ids:
            # Remove duplicates
            episode_ids = list(set(episode_ids))
            # Use OR with || (same as search.py which works)
            episode_filter = " or ".join([f'episode_id == "{ep}"' for ep in episode_ids])
            filter_parts.append(f"({episode_filter})")
        
        # Bible book filter - SKIP in Milvus, apply after retrieval
        # Milvus doesn't support LIKE %pattern%, only pattern%
        if request.books:
            post_filter_books = request.books
            print(f"📖 Will post-filter for books: {post_filter_books}")
        
        # Verse filter - this works fine
        if request.has_verses:
            filter_parts.append("verse_count > 0")
        
        # Combine all Milvus filters with AND
        filter_expr = " and ".join(filter_parts) if filter_parts else None
        
        if filter_expr:
            print(f"🔍 Milvus filter: {filter_expr}")
        # =====================================================
        
        # Stage 1: Initial retrieval (get more candidates if re-ranking or post-filtering)
        retrieve_count = request.top_k
        if request.use_reranker and reranker and RERANKER_AVAILABLE:
            retrieve_count = max(request.top_k, settings.reranker_candidates)
        
        # Get extra results if we need to post-filter by books
        if post_filter_books:
            retrieve_count = retrieve_count * 3  # Get 3x more for post-filtering
        
        # Search Milvus (now returns normalized types)
        results = milvus.search(
            query_embedding=query_embedding,
            top_k=retrieve_count * 2,  # Get extra for filtering
            filter_expr=filter_expr
        )
        
        # === POST-FILTER BY BOOKS (in Python) ===
        if post_filter_books:
            print(f"🔍 Post-filtering {len(results)} results for books: {post_filter_books}")
            filtered_by_books = []
            for r in results:
                books_mentioned = r.get("books_mentioned", "")
                if books_mentioned:
                    # Check if any requested book is in the comma-separated list
                    mentioned_books = [b.strip() for b in books_mentioned.split(",")]
                    if any(book in mentioned_books for book in post_filter_books):
                        filtered_by_books.append(r)
            results = filtered_by_books
            print(f"✅ After book filter: {len(results)} results remain")
        
        # Filter by score and limit
        filtered_results = [
            r for r in results
            if r.get("score", 0.0) >= request.min_score
        ][:retrieve_count]
        
        print(f"🔍 Stage 1: Retrieved {len(filtered_results)} candidates")
        
        # Stage 2: Re-ranking (if enabled and available)
        reranked = False
        rerank_metrics = None
        
        if request.use_reranker and reranker and RERANKER_AVAILABLE and filtered_results:
            try:
                print(f"🎯 Stage 2: Re-ranking with cross-encoder...")
                
                rerank_result = reranker.rerank_with_comparison(
                    query=query_to_use,
                    results=filtered_results,
                    top_k=request.top_k,
                    original_score_field="score",
                    text_field="text"
                )
                
                filtered_results = rerank_result["reranked_results"]
                rerank_metrics = rerank_result["metrics"]
                reranked = True
                
                print(f"✅ Re-ranked to top {len(filtered_results)} results")
            except Exception as e:
                print(f"⚠️  Re-ranking failed: {e}")
                print("   Falling back to original results...")
                filtered_results = filtered_results[:request.top_k]
        else:
            # No re-ranking, just limit to top_k
            filtered_results = filtered_results[:request.top_k]
        
        # Convert to response model (types already normalized by Milvus)
        final_results = [SearchResult(**r) for r in filtered_results]
        
        # Store in conversation
        if request.use_context:
            conversation.add_message(
                "user",
                request.query,
                {
                    "rewritten": rewritten_query,
                    "type": "search",
                    "reranked": reranked,
                    "filters": {
                        "episodes": episode_ids if episode_ids else None,
                        "books": request.books,
                        "has_verses": request.has_verses,
                        "min_score": request.min_score
                    }
                }
            )
        
        return SearchResponse(
            query=request.query,
            rewritten_query=rewritten_query,
            count=len(final_results),
            results=final_results,
            conversation_id=conversation_id,
            reranked=reranked,
            rerank_metrics=rerank_metrics
        )
    
    except Exception as e:
        print(f"❌ Search error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


# ============================================
# Filter Options Endpoint (FIX #2)
# ============================================

@router.get("/filters", response_model=FilterOptions)
async def get_available_filters():
    """
    Get available filter options for the search UI.
    
    Returns:
    - List of all episodes (id + title)
    - List of all Bible books mentioned across all transcripts
    - Valid score range
    - Valid top_k range
    """
    try:
        milvus, _, _, _ = get_services()
        
        # === Get unique episodes (respecting Milvus limit) ===
        episodes_dict = {}
        offset = 0
        batch_size = 16000  # Stay under 16,384 limit
        
        print("🔍 Fetching episodes...")
        while True:
            try:
                batch = milvus.collection.query(
                    expr="episode_id != ''",
                    output_fields=["episode_id", "episode_title"],
                    limit=batch_size,
                    offset=offset
                )
                
                if not batch:
                    break
                
                # Collect unique episodes
                for seg in batch:
                    ep_id = seg.get("episode_id", "")
                    ep_title = seg.get("episode_title", "Unknown")
                    if ep_id and ep_id not in episodes_dict:
                        episodes_dict[ep_id] = ep_title
                
                # Check if we got all results
                if len(batch) < batch_size:
                    break
                
                offset += batch_size
                print(f"   Fetched {offset} segments so far...")
                
            except Exception as e:
                print(f"⚠️  Batch fetch warning at offset {offset}: {e}")
                break
        
        episode_list = [
            {"episode_id": ep_id, "title": title}
            for ep_id, title in sorted(episodes_dict.items(), key=lambda x: x[1])
        ]
        
        print(f"✅ Found {len(episode_list)} unique episodes")
        
        # === Get unique books mentioned ===
        books_set = set()
        offset = 0
        batch_size = 16000
        
        print("📖 Fetching Bible books...")
        while True:
            try:
                batch = milvus.collection.query(
                    expr="verse_count > 0",
                    output_fields=["books_mentioned"],
                    limit=batch_size,
                    offset=offset
                )
                
                if not batch:
                    break
                
                # Extract books
                for seg in batch:
                    books = seg.get("books_mentioned", "")
                    if books:
                        for book in books.split(","):
                            book = book.strip()
                            if book:
                                books_set.add(book)
                
                # Check if we got all results
                if len(batch) < batch_size:
                    break
                
                offset += batch_size
                print(f"   Fetched {offset} verse segments so far...")
                
            except Exception as e:
                print(f"⚠️  Books batch fetch warning at offset {offset}: {e}")
                break
        
        books_list = sorted(list(books_set))
        
        print(f"✅ Found {len(books_list)} unique Bible books")
        
        return FilterOptions(
            episodes=episode_list,
            books=books_list,
            min_score_range=[0.0, 1.0],
            top_k_range=[1, 50]
        )
        
    except Exception as e:
        print(f"❌ Error getting filters: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get filters: {str(e)}"
        )


# ============================================
# Q&A Streaming Endpoint
# ============================================

@router.get("/answer")
async def answer(
    query: str = QueryParam(..., min_length=1, description="Question to answer"),
    top_k: int = QueryParam(5, ge=1, le=50, description="Number of context segments"),
    episode_filter: Optional[str] = QueryParam(None, description="Filter by episode ID"),
    min_score: float = QueryParam(0.0, ge=0.0, le=1.0, description="Minimum similarity score"),
    use_rewrite: bool = QueryParam(True, description="Enable query rewriting"),
    use_context: bool = QueryParam(True, description="Use conversation context"),
    use_reranker: bool = QueryParam(True, description="Use cross-encoder re-ranking"),
    conversation_id: Optional[str] = QueryParam(None, description="Conversation ID")
):
    """
    Generate AI answer with streaming response (Server-Sent Events).
    
    The response streams in real-time as the AI generates the answer.
    Includes optional re-ranking for more accurate context selection.
    
    Events sent:
    - status: Processing updates
    - rewritten_query: Query after rewriting (if enabled)
    - search_results: Retrieved context segments
    - answer_chunk: Partial answer text
    - answer_complete: Final metadata
    - error: Error message
    """
    
    async def event_generator():
        """Generate SSE events for streaming response."""
        try:
            milvus, embedder, llm, reranker = get_services()
            
            # Get or create conversation
            conv_id = conversation_id or str(uuid.uuid4())
            conversation = ConversationHistory(
                conv_id,
                storage_dir=str(_conversation_dir)
            )
            
            # Status: Starting
            yield {
                "event": "status",
                "data": "Processing your question..."
            }
            await asyncio.sleep(0.1)
            
            # === Query Rewriting ===
            query_to_use = query
            rewritten_query = None
            
            if use_rewrite:
                yield {
                    "event": "status",
                    "data": "Optimizing search query..."
                }
                
                if use_context and len(conversation) > 0:
                    context_messages = conversation.get_history()[-3:]
                    rewritten_query = llm.rewrite_query_with_context(
                        query,
                        context_messages
                    )
                else:
                    rewritten_query = llm.rewrite_query(query)
                
                if rewritten_query and rewritten_query != query:
                    query_to_use = rewritten_query
                    yield {
                        "event": "rewritten_query",
                        "data": rewritten_query
                    }
                    print(f"🔄 Query rewritten: '{query}' -> '{rewritten_query}'")
            
            # === Stage 1: Search ===
            yield {
                "event": "status",
                "data": "Searching transcript database..."
            }
            
            query_embedding = embedder.embed(query_to_use)
            
            filter_expr = None
            if episode_filter:
                filter_expr = f'episode_id == "{episode_filter}"'
            
            # Get more candidates if re-ranking
            retrieve_count = top_k
            if use_reranker and reranker and RERANKER_AVAILABLE:
                retrieve_count = max(top_k, settings.reranker_candidates)
            
            results = milvus.search(
                query_embedding=query_embedding,
                top_k=retrieve_count * 2,
                filter_expr=filter_expr
            )
            
            # Filter by score
            filtered_results = [
                r for r in results
                if r.get("score", 0.0) >= min_score
            ][:retrieve_count]
            
            if not filtered_results:
                yield {
                    "event": "error",
                    "data": "No relevant segments found. Try lowering the minimum score threshold."
                }
                return
            
            print(f"🔍 Stage 1: Retrieved {len(filtered_results)} candidates")
            
            # === Stage 2: Re-ranking ===
            reranked = False
            
            if use_reranker and reranker and RERANKER_AVAILABLE and filtered_results:
                try:
                    yield {
                        "event": "status",
                        "data": "Re-ranking results for accuracy..."
                    }
                    
                    print(f"🎯 Stage 2: Re-ranking with cross-encoder...")
                    
                    filtered_results = reranker.rerank(
                        query=query_to_use,
                        results=filtered_results,
                        top_k=top_k,
                        text_field="text"
                    )
                    
                    reranked = True
                    print(f"✅ Re-ranked to top {len(filtered_results)} results")
                except Exception as e:
                    print(f"⚠️  Re-ranking failed: {e}")
                    print("   Falling back to original results...")
                    filtered_results = filtered_results[:top_k]
            else:
                filtered_results = filtered_results[:top_k]
            
            # Send search results
            yield {
                "event": "search_results",
                "data": json.dumps({
                    "count": len(filtered_results),
                    "results": filtered_results,
                    "reranked": reranked
                })
            }
            
            print(f"🔍 Found {len(filtered_results)} relevant segments")
            
            # === Generate Answer ===
            yield {
                "event": "status",
                "data": "Generating AI answer..."
            }
            
            # Prepare context (use top 3 for answer)
            context_segments = filtered_results[:3]
            
            conversation_context = ""
            if use_context and len(conversation) > 0:
                conversation_context = "Previous conversation:\n"
                for msg in conversation.get_history()[-3:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    conversation_context += f"{role}: {content}\n"
                conversation_context += "\n"
            
            # Stream answer (sync generator from OpenAI)
            full_answer = ""
            stream = llm.answer_query_stream(
                query=query,
                context_segments=context_segments,
                conversation_context=conversation_context
            )
            
            # Convert sync generator to async
            loop = asyncio.get_event_loop()
            
            def get_next_chunk():
                """Get next chunk from sync generator."""
                try:
                    return next(stream)
                except StopIteration:
                    return None
            
            # Stream chunks
            while True:
                chunk = await loop.run_in_executor(None, get_next_chunk)
                if chunk is None:
                    break
                
                full_answer += chunk
                yield {
                    "event": "answer_chunk",
                    "data": chunk
                }
            
            print(f"✅ Generated answer ({len(full_answer)} chars)")
            
            # Store in conversation
            if use_context:
                conversation.add_message(
                    "user",
                    query,
                    {
                        "rewritten": rewritten_query,
                        "type": "question",
                        "reranked": reranked
                    }
                )
                conversation.add_message("assistant", full_answer)
            
            # Send completion
            yield {
                "event": "answer_complete",
                "data": json.dumps({
                    "conversation_id": conv_id,
                    "message_count": len(conversation),
                    "answer_length": len(full_answer),
                    "reranked": reranked
                })
            }
        
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"❌ Error in event_generator:\n{error_details}")
            yield {
                "event": "error",
                "data": f"Error: {str(e)}"
            }
    
    return EventSourceResponse(event_generator())


# ============================================
# Conversation Management
# ============================================

@router.get("/conversation/{conversation_id}", response_model=ConversationInfo)
async def get_conversation(conversation_id: str):
    """
    Get conversation history by ID.
    
    Returns all messages in the conversation with metadata.
    """
    try:
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found or empty"
            )
        
        return ConversationInfo(
            conversation_id=conversation_id,
            message_count=len(conversation),
            messages=conversation.get_history()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation by ID.
    
    Removes the conversation file from storage.
    """
    try:
        conv_file = _conversation_dir / f"{conversation_id}.json"
        
        if not conv_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        conv_file.unlink()
        
        return {
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.get("/conversations")
async def list_conversations():
    """
    List all active conversations.
    
    Returns summary information about all stored conversations.
    """
    try:
        conversations = []
        
        for conv_file in _conversation_dir.glob("*.json"):
            conv_id = conv_file.stem
            conversation = ConversationHistory(
                conv_id,
                storage_dir=str(_conversation_dir)
            )
            
            if len(conversation) > 0:
                messages = conversation.get_history()
                conversations.append({
                    "conversation_id": conv_id,
                    "message_count": len(messages),
                    "last_message": messages[-1] if messages else None,
                    "created": conv_file.stat().st_ctime
                })
        
        # Sort by creation time (newest first)
        conversations.sort(key=lambda x: x["created"], reverse=True)
        
        return {
            "count": len(conversations),
            "conversations": conversations
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )

# ============================================
# ENHANCED CONVERSATION MANAGEMENT (NEW)
# ============================================

class ConversationMetadata(BaseModel):
    """Conversation metadata model."""
    conversation_id: str
    name: str
    created_at: str
    updated_at: str
    parent_id: Optional[str] = None
    branch_point: Optional[int] = None
    message_count: int
    is_branch: bool


class RenameRequest(BaseModel):
    """Request model for renaming a conversation."""
    name: str = Field(..., min_length=1, max_length=200)


class BranchRequest(BaseModel):
    """Request model for branching a conversation."""
    branch_point: int = Field(..., ge=0)
    name: Optional[str] = Field(None, max_length=200)


class SearchInConversationRequest(BaseModel):
    """Request model for searching within a conversation."""
    query: str = Field(..., min_length=1)


class SearchMatch(BaseModel):
    """Single search match within conversation."""
    message_index: int
    role: str
    content: str
    timestamp: str
    match_preview: str


@router.get("/conversations/list", response_model=List[ConversationMetadata])
async def list_conversations_with_metadata():
    """
    List all conversations with full metadata.
    
    Enhanced version that includes name, timestamps, branch info, etc.
    """
    try:
        conversations = []
        
        for conv_file in _conversation_dir.glob("*.json"):
            conv_id = conv_file.stem
            conversation = ConversationHistory(
                conv_id,
                storage_dir=str(_conversation_dir)
            )
            
            if len(conversation) > 0:
                metadata = conversation.get_metadata()
                conversations.append(ConversationMetadata(**metadata))
        
        # Sort by updated_at (newest first)
        conversations.sort(key=lambda x: x.updated_at, reverse=True)
        
        return conversations
        
    except Exception as e:
        print(f"❌ Error listing conversations: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.put("/conversation/{conversation_id}/rename")
async def rename_conversation(conversation_id: str, request: RenameRequest):
    """
    Rename a conversation.
    
    Args:
        conversation_id: ID of conversation to rename
        request: New name for the conversation
    
    Returns:
        Updated conversation metadata
    """
    try:
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        # Update name
        conversation.set_name(request.name)
        
        return {
            "message": "Conversation renamed successfully",
            "conversation_id": conversation_id,
            "new_name": request.name,
            "metadata": conversation.get_metadata()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error renaming conversation: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rename conversation: {str(e)}"
        )


@router.post("/conversation/{conversation_id}/branch")
async def branch_conversation(conversation_id: str, request: BranchRequest):
    """
    Create a new conversation branch from a specific message.
    
    Args:
        conversation_id: Parent conversation ID
        request: Branch point and optional name
    
    Returns:
        New branched conversation metadata
    """
    try:
        parent_conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(parent_conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        if request.branch_point >= len(parent_conversation):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid branch point: {request.branch_point} (max: {len(parent_conversation) - 1})"
            )
        
        # Create new branch
        new_conv_id = str(uuid.uuid4())
        branch_name = request.name or f"Branch from {parent_conversation.name}"
        
        new_conversation = parent_conversation.branch(
            branch_point=request.branch_point,
            new_conversation_id=new_conv_id,
            branch_name=branch_name
        )
        
        return {
            "message": "Branch created successfully",
            "parent_id": conversation_id,
            "branch_id": new_conv_id,
            "branch_point": request.branch_point,
            "metadata": new_conversation.get_metadata()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error branching conversation: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to branch conversation: {str(e)}"
        )


@router.post("/conversation/{conversation_id}/search", response_model=List[SearchMatch])
async def search_in_conversation(conversation_id: str, request: SearchInConversationRequest):
    """
    Search within a specific conversation.
    
    Args:
        conversation_id: Conversation to search
        request: Search query
    
    Returns:
        List of matching messages with context
    """
    try:
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        # Search conversation
        results = conversation.search(request.query)
        
        # Format results
        matches = []
        for msg_index, message, role in results:
            content = message.get("content", "")
            timestamp = message.get("timestamp", "")
            
            # Create preview with highlighted query
            query_lower = request.query.lower()
            content_lower = content.lower()
            
            # Find query position
            pos = content_lower.find(query_lower)
            if pos != -1:
                # Get 50 chars before and after
                start = max(0, pos - 50)
                end = min(len(content), pos + len(request.query) + 50)
                preview = content[start:end]
                
                if start > 0:
                    preview = "..." + preview
                if end < len(content):
                    preview = preview + "..."
            else:
                # Fallback: first 100 chars
                preview = content[:100] + ("..." if len(content) > 100 else "")
            
            matches.append(SearchMatch(
                message_index=msg_index,
                role=role,
                content=content,
                timestamp=timestamp,
                match_preview=preview
            ))
        
        return matches
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error searching conversation: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search conversation: {str(e)}"
        )


@router.get("/conversation/{conversation_id}/export/json")
async def export_conversation_json(conversation_id: str):
    """
    Export conversation as JSON file.
    
    Args:
        conversation_id: Conversation to export
    
    Returns:
        JSON file download
    """
    try:
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        # Get JSON export
        json_data = conversation.export_json()
        
        # Return as downloadable file
        from fastapi.responses import Response
        
        filename = f"{conversation.name.replace(' ', '_')}.json"
        
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error exporting conversation: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export conversation: {str(e)}"
        )


@router.get("/conversation/{conversation_id}/export/txt")
async def export_conversation_txt(conversation_id: str):
    """
    Export conversation as formatted text file.
    
    Args:
        conversation_id: Conversation to export
    
    Returns:
        Text file download
    """
    try:
        conversation = ConversationHistory(
            conversation_id,
            storage_dir=str(_conversation_dir)
        )
        
        if len(conversation) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found"
            )
        
        # Get text export
        text_data = conversation.export_text()
        
        # Return as downloadable file
        from fastapi.responses import Response
        
        filename = f"{conversation.name.replace(' ', '_')}.txt"
        
        return Response(
            content=text_data,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error exporting conversation: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export conversation: {str(e)}"
        )

# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    
    Returns OK if the service is running.
    """
    return {
        "status": "healthy",
        "service": "query-api",
        "version": "1.0.0",
        "reranker_available": RERANKER_AVAILABLE
    }