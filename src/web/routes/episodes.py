"""
Episode management endpoints.

Works with the refactored MilvusStore that returns normalized data.
Now includes re-ingestion capabilities.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import sys
from pathlib import Path
import traceback

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vectorstore.milvus_store import MilvusStore
from embeddings.embedder import Embedder  # ← FIXED
from config.settings import settings

router = APIRouter()

# Initialize Milvus and Embedder
try:
    milvus = MilvusStore(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        collection_name=settings.milvus_collection
    )
    embedder = Embedder()  # ← FIXED
    print("✅ Episode management services initialized")
except Exception as e:
    print(f"⚠️  Warning: Could not initialize episode services: {e}")
    milvus = None
    embedder = None


# ============================================================================
# MODELS
# ============================================================================

class Episode(BaseModel):
    """Basic episode information."""
    episode_id: str
    title: str
    segment_count: Optional[int] = 0
    total_words: Optional[int] = 0


class EpisodeDetail(BaseModel):
    """Detailed episode information."""
    episode_id: str
    title: str
    segment_count: int
    total_words: int


class EpisodeStats(BaseModel):
    """Episode statistics."""
    total_episodes: int
    total_segments: int
    total_words: int
    avg_segments_per_episode: float
    avg_words_per_episode: float

class VerseReference(BaseModel):
    """A Bible verse reference."""
    book: str
    chapter: int
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None
    reference: str  # Formatted as "Genesis 1:2"

class SegmentWithVerses(BaseModel):
    """Segment with verse references."""
    segment_id: int
    episode_id: str
    episode_title: str
    text: str
    verse_count: int
    verse_references: str
    books_mentioned: str

class EpisodeVerseStats(BaseModel):
    """Verse statistics for an episode."""
    episode_id: str
    episode_title: str
    total_verses: int
    unique_books: List[str]
    segments_with_verses: int
    verse_list: List[str]



# ============================================================================
# LIST EPISODES
# ============================================================================

@router.get("/list", response_model=List[Episode])
async def list_episodes():
    """Get a list of all episodes in the database."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print("📋 Listing episodes...")
        
        # Get unique episodes using the new API
        episodes_data = milvus.get_unique_episodes()
        
        if not episodes_data:
            print("ℹ️  No episodes found in database")
            return []
        
        print(f"✅ Found {len(episodes_data)} unique episodes")
        
        # Get segment counts and word counts for each episode
        episodes = []
        for ep_data in episodes_data:
            episode_id = ep_data["episode_id"]
            
            # Get segments for this episode
            segments = milvus.get_segments_by_episode(episode_id)
            
            episodes.append(Episode(
                episode_id=episode_id,
                title=ep_data["episode_title"],
                segment_count=len(segments),
                total_words=sum(seg["word_count"] for seg in segments)
            ))
        
        print(f"✅ Processed {len(episodes)} episodes with stats")
        return episodes
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error listing episodes:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list episodes: {str(e)}"
        )


# ============================================================================
# RE-INGEST ALL EPISODES (MUST BE BEFORE /{episode_id})
# ============================================================================

@router.post("/reingest-all")
async def reingest_all_episodes():
    """Re-ingest all episodes from transcript files."""
    if not milvus or not embedder:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        # Import here to avoid circular imports
        from cli.ingest import ingest_episode
        
        # Get the repo root (parent of src/)
        print(f"🔍 DEBUG: __file__ = {Path(__file__)}")
        print(f"🔍 DEBUG: __file__.parent = {Path(__file__).parent}")
        print(f"🔍 DEBUG: __file__.parent.parent = {Path(__file__).parent.parent}")
        print(f"🔍 DEBUG: __file__.parent.parent.parent = {Path(__file__).parent.parent.parent}")

        repo_root = Path(__file__).parent.parent.parent.parent
        transcripts_dir = repo_root / "transcripts"

        print(f"🔍 DEBUG: repo_root = {repo_root.absolute()}")
        print(f"🔍 DEBUG: transcripts_dir = {transcripts_dir.absolute()}") 
        
        if not transcripts_dir.exists():
            raise HTTPException(
                status_code=404,
                detail="Transcripts directory not found"
            )
        
        # Find all JSON files (metadata)
        json_files = sorted(transcripts_dir.glob("*.json"))

        # DEBUG: Print what we found
        print(f"🔍 DEBUG: transcripts_dir = {transcripts_dir.absolute()}")
        print(f"🔍 DEBUG: transcripts_dir.exists() = {transcripts_dir.exists()}")
        print(f"🔍 DEBUG: Found {len(json_files)} JSON files")
        if json_files:
            print(f"🔍 DEBUG: First file: {json_files[0]}")
        else:
            print(f"🔍 DEBUG: Listing directory contents:")
            for item in transcripts_dir.iterdir():
                print(f"   - {item.name}")

        if not json_files:
            raise HTTPException(
                status_code=404,
                detail="No transcript files found in transcripts directory"
            )
        
        print(f"📥 Re-ingesting {len(json_files)} episodes...")
        
        processed = 0
        errors = []
        
        for json_file in json_files:
            # Find corresponding SRT file
            srt_file = json_file.with_suffix(".srt")
            
            if not srt_file.exists():
                errors.append(f"Missing SRT file for {json_file.name}")
                continue
            
            try:
                print(f"\n  Processing: {json_file.stem}")
                
                # Delete existing episode first
                # Use same episode_id generation as ingest.py for consistency
                episode_id = json_file.stem.lower().replace(" ", "_").replace(":", "").replace("?", "").replace(",", "")
                segments = milvus.get_segments_by_episode(episode_id)
                print(f"🔍 DEBUG: Found {len(segments)} segments for episode {episode_id}")
                
                if segments:
                    segment_ids = [s["segment_id"] for s in segments]  # segment_id is already int from normalized response
                    milvus.delete_segments(segment_ids)
                    print(f"    Deleted {len(segment_ids)} old segments")
                
                # Re-ingest with CORRECT parameters
                result = ingest_episode(
                    episode_json_path=str(json_file),
                    transcript_srt_path=str(srt_file),
                    force=True,
                    chunk_size=3500
                )
                
                if result.get("success"):
                    processed += 1
                    print(f"    ✅ Re-ingested successfully")
                else:
                    error_msg = f"Failed: {result.get('error', 'Unknown error')}"
                    errors.append(f"{json_file.name}: {error_msg}")
                    print(f"    ❌ {error_msg}")
                
            except Exception as e:
                error_msg = f"Failed to process {json_file.name}: {str(e)}"
                errors.append(error_msg)
                print(f"    ❌ {error_msg}")
                continue
        
        return {
            "success": True,
            "message": f"Re-ingested {processed} of {len(json_files)} episodes",
            "episodes_processed": processed,
            "total_episodes": len(json_files),
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error re-ingesting all episodes:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VERSE QUERIES
# ============================================================================

@router.get("/verses/all", response_model=List[SegmentWithVerses])
async def get_all_verses():
    """Get all segments that contain Bible verse references."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print("📖 Fetching all segments with verses...")
        
        # Query Milvus for segments with verses
        results = milvus.collection.query(
            expr="verse_count > 0",
            output_fields=["segment_id", "episode_id", "episode_title", "text", 
                          "verse_count", "verse_references", "books_mentioned"],
            limit=1000
        )
        
        segments = [
            SegmentWithVerses(
                segment_id=r["segment_id"],
                episode_id=r["episode_id"],
                episode_title=r["episode_title"],
                text=r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                verse_count=r["verse_count"],
                verse_references=r["verse_references"],
                books_mentioned=r["books_mentioned"]
            )
            for r in results
        ]
        
        print(f"✅ Found {len(segments)} segments with verses")
        return segments
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error fetching verses:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verses/episode/{episode_id}", response_model=EpisodeVerseStats)
async def get_episode_verses(episode_id: str):
    """Get all verse references for a specific episode."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print(f"📖 Fetching verses for episode: {episode_id}")
        
        # Get all segments for this episode
        segments = milvus.get_segments_by_episode(episode_id)
        
        if not segments:
            raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
        
        # Collect verse statistics
        total_verses = 0
        segments_with_verses = 0
        all_books = set()
        all_verse_refs = []
        
        for seg in segments:
            if seg.get("verse_count", 0) > 0:
                total_verses += seg["verse_count"]
                segments_with_verses += 1
                
                # Parse verse references
                refs = seg.get("verse_references", "")
                if refs:
                    all_verse_refs.extend([r.strip() for r in refs.split(",")])
                
                # Parse books mentioned
                books = seg.get("books_mentioned", "")
                if books:
                    all_books.update([b.strip() for b in books.split(",")])
        
        episode_title = segments[0].get("episode_title", episode_id) if segments else episode_id
        
        return EpisodeVerseStats(
            episode_id=episode_id,
            episode_title=episode_title,
            total_verses=total_verses,
            unique_books=sorted(list(all_books)),
            segments_with_verses=segments_with_verses,
            verse_list=all_verse_refs
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error fetching episode verses:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verses/book/{book_name}")
async def get_verses_by_book(book_name: str):
    """Get all segments that reference a specific book of the Bible."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print(f"📖 Fetching segments referencing {book_name}...")
        
        # Query for segments where books_mentioned contains the book name
        results = milvus.collection.query(
            expr=f"books_mentioned like '%{book_name}%'",
            output_fields=["segment_id", "episode_id", "episode_title", "text", 
                          "verse_count", "verse_references", "books_mentioned"],
            limit=500
        )
        
        segments = [
            {
                "segment_id": r["segment_id"],
                "episode_id": r["episode_id"],
                "episode_title": r["episode_title"],
                "text_preview": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                "verse_count": r["verse_count"],
                "verse_references": r["verse_references"],
            }
            for r in results
        ]
        
        print(f"✅ Found {len(segments)} segments referencing {book_name}")
        
        return {
            "book": book_name,
            "total_segments": len(segments),
            "segments": segments
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error fetching book references:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# EPISODE STATISTICS (BEFORE /{episode_id})
# ============================================================================

@router.get("/stats/overview", response_model=EpisodeStats)
async def get_episode_stats():
    """Get overall statistics about episodes."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print("📊 Calculating episode statistics...")
        
        # Get all episodes
        episodes_data = milvus.get_unique_episodes()
        
        if not episodes_data:
            return EpisodeStats(
                total_episodes=0,
                total_segments=0,
                total_words=0,
                avg_segments_per_episode=0.0,
                avg_words_per_episode=0.0
            )
        
        # Calculate stats across all episodes
        total_segments = 0
        total_words = 0
        
        for ep_data in episodes_data:
            segments = milvus.get_segments_by_episode(ep_data["episode_id"])
            total_segments += len(segments)
            total_words += sum(seg["word_count"] for seg in segments)
        
        total_episodes = len(episodes_data)
        avg_segments = total_segments / total_episodes if total_episodes > 0 else 0
        avg_words = total_words / total_episodes if total_episodes > 0 else 0
        
        print(f"✅ Stats calculated: {total_episodes} episodes, {total_segments} segments")
        
        return EpisodeStats(
            total_episodes=total_episodes,
            total_segments=total_segments,
            total_words=total_words,
            avg_segments_per_episode=round(avg_segments, 2),
            avg_words_per_episode=round(avg_words, 2)
        )
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error calculating stats:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get("/stats/count")
async def get_episode_count():
    """Get the total number of episodes."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print("📊 Counting episodes...")
        
        # Get unique episodes and count them
        episodes = milvus.get_unique_episodes()
        count = len(episodes)
        
        print(f"✅ Total episodes: {count}")
        
        return {
            "total_episodes": count
        }
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error counting episodes:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get count: {str(e)}"
        )


@router.get("/stats/health")
async def health_check():
    """Health check for episodes endpoint."""
    try:
        if not milvus:
            return {
                "status": "unhealthy",
                "service": "episodes-api",
                "error": "Milvus not initialized"
            }
        
        segment_count = milvus.count_segments()
        episode_count = len(milvus.get_unique_episodes())
        
        return {
            "status": "healthy",
            "service": "episodes-api",
            "milvus_connected": True,
            "total_segments": segment_count,
            "total_episodes": episode_count
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "episodes-api",
            "error": str(e)
        }


# ============================================================================
# GET EPISODE DETAILS (AFTER all specific routes)
# ============================================================================
# ============================================================================
# RE-INGEST SINGLE EPISODE
# ============================================================================

@router.post("/{episode_id}/reingest")
async def reingest_episode(episode_id: str):
    """Re-ingest a single episode from transcript files."""
    if not milvus or not embedder:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        # Import here to avoid circular imports
        from cli.ingest import ingest_episode
        
# Get the repo root (parent of src/)
        print(f"🔍 DEBUG: __file__ = {Path(__file__)}")
        print(f"🔍 DEBUG: __file__.parent = {Path(__file__).parent}")
        print(f"🔍 DEBUG: __file__.parent.parent = {Path(__file__).parent.parent}")
        print(f"🔍 DEBUG: __file__.parent.parent.parent = {Path(__file__).parent.parent.parent}")

        repo_root = Path(__file__).parent.parent.parent.parent
        transcripts_dir = repo_root / "transcripts"

        print(f"🔍 DEBUG: repo_root = {repo_root.absolute()}")
        print(f"🔍 DEBUG: transcripts_dir = {transcripts_dir.absolute()}")
        
        
        # Find transcript files (try multiple patterns)
        json_file = None
        for pattern in [f"{episode_id}.json", f"Episode_{episode_id}.json", f"*{episode_id}*.json"]:
            matches = list(transcripts_dir.glob(pattern))
            if matches:
                json_file = matches[0]
                break
        
        if not json_file or not json_file.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Transcript file not found for episode: {episode_id}"
            )
        
        srt_file = json_file.with_suffix(".srt")
        
        if not srt_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"SRT file not found: {srt_file.name}"
            )
        
        # Delete existing episode
        segments = milvus.get_segments_by_episode(episode_id)
        segments_deleted = 0
        
        if segments:
            segment_ids = [s["segment_id"] for s in segments]  # segment_id is already int from normalized response
            milvus.delete_segments(segment_ids)
            segments_deleted = len(segment_ids)
        
        # Re-ingest with CORRECT parameters
        result = ingest_episode(
            episode_json_path=str(json_file),
            transcript_srt_path=str(srt_file),
            force=True,
            chunk_size=3500
        )
        
        return {
            "success": result.get("success", False),
            "message": f"Episode '{episode_id}' re-ingested successfully",
            "segments_deleted": segments_deleted,
            "transcript_file": json_file.name,
            "segments_ingested": result.get("segments_ingested", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error re-ingesting episode:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# GET EPISODE DETAILS (MUST be after specific routes to avoid conflicts)
# ============================================================================

@router.get("/{episode_id}", response_model=EpisodeDetail)
async def get_episode_details(episode_id: str):
    """Get detailed information about a specific episode."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print(f"📄 Fetching details for episode: {episode_id}")
        
        # Get all segments for this episode
        segments = milvus.get_segments_by_episode(episode_id)
        
        if not segments:
            raise HTTPException(
                status_code=404,
                detail=f"Episode not found: {episode_id}"
            )
        
        # Calculate statistics
        segment_count = len(segments)
        total_words = sum(seg.get("word_count", 0) for seg in segments)
        episode_title = segments[0].get("episode_title", episode_id)
        
        print(f"✅ Found episode with {segment_count} segments")
        
        return EpisodeDetail(
            episode_id=episode_id,
            title=episode_title,
            segment_count=segment_count,
            total_words=total_words
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error fetching episode details:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get episode details: {str(e)}"
        )


    # ... existing delete code ...

# ============================================================================
# DELETE EPISODE
# ============================================================================

@router.delete("/{episode_id}")
async def delete_episode(episode_id: str):
    """Delete an episode and all its segments from the database."""
    if not milvus:
        raise HTTPException(status_code=503, detail="Episode service not available")
    
    try:
        print(f"🗑️  Deleting episode: {episode_id}")
        
        # Use the new API method which returns a dict
        result = milvus.delete_episode(episode_id)
        
        if not result["success"]:
            if "not found" in result["message"].lower():
                raise HTTPException(
                    status_code=404,
                    detail=result["message"]
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result["message"]
                )
        
        print(f"✅ Deleted {result['segments_deleted']} segments")
        
        return {
            "success": True,
            "message": f"Successfully deleted episode: {episode_id}",
            "segments_deleted": result["segments_deleted"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error deleting episode:\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete episode: {str(e)}"
        )