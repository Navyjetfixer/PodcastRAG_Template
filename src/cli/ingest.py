"""
CLI tool for ingesting podcast episodes into the vector store.
Now includes Bible verse extraction and metadata enrichment.
Uses persistent episode mapping for stable sequential IDs.
"""
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich import print as rprint
from rich.console import Console
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vectorstore.milvus_store import MilvusStore
from embeddings.embedder import Embedder
from transcripts.parser import TranscriptParser
from config.settings import settings

# Try to import Bible verse extractor (graceful fallback if not available)
try:
    from utils.enhanced_verse_extractor import BibleVerseExtractor
    VERSE_EXTRACTOR_AVAILABLE = True
except ImportError:
    VERSE_EXTRACTOR_AVAILABLE = False
    print("⚠️  Bible verse extractor not available. Continuing without verse extraction.") 

console = Console()

# Episode mapping file location
EPISODE_MAPPING_FILE = Path("data/episode_mapping.json")


def load_episode_mapping() -> Dict[str, str]:
    """
    Load the persistent episode mapping from disk.
    
    Returns:
        Dictionary mapping episode_title -> episode_id
    """
    if EPISODE_MAPPING_FILE.exists():
        try:
            with open(EPISODE_MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            rprint(f"[yellow]⚠️  Warning: Could not load episode mapping: {e}[/yellow]")
            return {}
    return {}


def save_episode_mapping(mapping: Dict[str, str]) -> None:
    """
    Save the episode mapping to disk.
    
    Args:
        mapping: Dictionary mapping episode_title -> episode_id
    """
    try:
        EPISODE_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EPISODE_MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
    except Exception as e:
        rprint(f"[yellow]⚠️  Warning: Could not save episode mapping: {e}[/yellow]")


def get_or_create_episode_id(episode_title: str, episode_mapping: Dict[str, str]) -> tuple[str, bool]:
    """
    Get existing episode ID for a title, or create a new sequential ID.
    
    Args:
        episode_title: Title of the episode
        episode_mapping: Current mapping dictionary
    
    Returns:
        Tuple of (episode_id, is_new)
        - episode_id: The ID (existing or newly assigned)
        - is_new: True if this is a new episode, False if it already existed
    """
    # Check if episode already has an ID
    if episode_title in episode_mapping:
        return episode_mapping[episode_title], False
    
    # Generate new sequential ID
    existing_ids = list(episode_mapping.values())
    max_num = 0
    
    for ep_id in existing_ids:
        if ep_id.startswith('episode_'):
            try:
                num = int(ep_id.split('_')[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                pass
    
    next_num = max_num + 1
    new_episode_id = f"episode_{next_num:03d}"
    
    # Add to mapping
    episode_mapping[episode_title] = new_episode_id
    
    return new_episode_id, True


def ingest_episode(
    episode_json_path: str,
    transcript_srt_path: str,
    force: bool = False,
    chunk_size: int = 3500
) -> Dict[str, Any]:
    """
    Ingest a single podcast episode into the vector store with Bible verse extraction.
    
    Args:
        episode_json_path: Path to episode metadata JSON
        transcript_srt_path: Path to transcript SRT file
        force: If True, overwrite existing episode
        chunk_size: Maximum characters per segment
    
    Returns:
        Dictionary with ingestion results and statistics
    """
    rprint("\n[bold cyan]🎙️  DataOverDogma Episode Ingestion[/bold cyan]")
    rprint("=" * 60)
    
    # ========================================
    # 1. Validate Files
    # ========================================
    json_file = Path(episode_json_path)
    srt_file = Path(transcript_srt_path)
    
    if not json_file.exists():
        rprint(f"[red]❌ Episode JSON not found:[/red] {json_file}")
        return {"success": False, "error": "JSON file not found"}
    
    if not srt_file.exists():
        rprint(f"[red]❌ Transcript SRT not found:[/red] {srt_file}")
        return {"success": False, "error": "SRT file not found"}
    
    rprint(f"[green]✓[/green] Found episode metadata: {json_file.name}")
    rprint(f"[green]✓[/green] Found transcript: {srt_file.name}")
    
    # ========================================
    # 2. Load Episode Mapping & Generate Episode ID
    # ========================================
    rprint("\n[bold]📄 Loading Episode Metadata...[/bold]")
    
    try:
        # Read JSON metadata
        with open(episode_json_path, 'r', encoding='utf-8-sig') as f:
            file_content = f.read()
        
        episode_data = json.loads(file_content)
        episode_title = episode_data.get('title', 'Unknown Title')
        
        # Load episode mapping
        episode_mapping = load_episode_mapping()
        
        # Get or create episode ID
        episode_id, is_new_episode = get_or_create_episode_id(episode_title, episode_mapping)
        
        if is_new_episode:
            rprint(f"[green]✓[/green] New episode detected - assigned ID: {episode_id}")
            # Save mapping immediately
            save_episode_mapping(episode_mapping)
        else:
            rprint(f"[cyan]ℹ️  Known episode - existing ID: {episode_id}[/cyan]")
        
        rprint(f"[cyan]Episode ID:[/cyan] {episode_id}")
        rprint(f"[cyan]Title:[/cyan] {episode_title}")
        
        # Initialize Milvus
        milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
        
    except json.JSONDecodeError as e:
        rprint(f"[red]❌ Invalid JSON format:[/red] {e}")
        rprint(f"[red]Line {e.lineno}, Column {e.colno}[/red]")
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        rprint(f"[red]❌ Failed to load episode metadata:[/red] {e}")
        import traceback
        rprint(f"[dim]{traceback.format_exc()}[/dim]")
        return {"success": False, "error": f"Failed to load metadata: {e}"}
    
    # ========================================
    # 3. Check for Existing Episode in Milvus
    # ========================================
    rprint("\n[bold]🔍 Checking Milvus Database...[/bold]")
    
    try:
        if milvus.episode_exists(episode_id):
            if force:
                rprint(f"[yellow]⚠️  Episode '{episode_id}' exists in database. Force flag set - deleting...[/yellow]")
                result = milvus.delete_episode(episode_id)
                if result["success"]:
                    rprint(f"[green]✓[/green] Deleted {result['segments_deleted']} existing segments")
                else:
                    rprint(f"[red]❌ Failed to delete existing episode[/red]")
                    return {"success": False, "error": "Failed to delete existing episode"}
            else:
                rprint(f"[yellow]⚠️  Episode '{episode_id}' already exists in database![/yellow]")
                rprint("[yellow]Use --force to overwrite[/yellow]")
                return {
                    "success": False,
                    "error": "Episode already exists",
                    "episode_id": episode_id,
                    "exists": True
                }
        else:
            rprint("[green]✓[/green] Episode not in database - proceeding with ingestion")
        
    except Exception as e:
        rprint(f"[red]❌ Database check failed:[/red] {e}")
        return {"success": False, "error": f"Database check failed: {e}"}
    
    # ========================================
    # 4. Parse Transcript
    # ========================================
    rprint("\n[bold]📝 Parsing Transcript...[/bold]")
    
    try:
        # Initialize parser with chunk size
        parser = TranscriptParser(max_segment_chars=chunk_size)
        
        rprint(f"[cyan]Max segment size:[/cyan] {chunk_size} chars")
        
        # Parse transcript (uses your existing method signature)
        segments = parser.parse_srt_with_json(srt_file, json_file)
        
        # Override episode_id in all segments with our stable ID
        for segment in segments:
            segment["episode_id"] = episode_id
        
        rprint(f"[green]✓[/green] Parsed {len(segments)} segments")
        
        # Calculate statistics
        total_words = sum(seg.get("word_count", 0) for seg in segments)
        avg_words = total_words / len(segments) if segments else 0
        
        rprint(f"[cyan]Total words:[/cyan] {total_words:,}")
        rprint(f"[cyan]Average words per segment:[/cyan] {avg_words:.1f}")
        
    except Exception as e:
        rprint(f"[red]❌ Failed to parse transcript:[/red] {e}")
        return {"success": False, "error": f"Failed to parse transcript: {e}"}
    
    # ========================================
    # 5. Extract Bible Verses
    # ========================================
    rprint("\n[bold]📖 Extracting Bible Verse References...[/bold]")
    
    verse_stats = {
        "total_verses": 0,
        "segments_with_verses": 0,
        "unique_books": set(),
        "extraction_available": VERSE_EXTRACTOR_AVAILABLE
    }
    
    if VERSE_EXTRACTOR_AVAILABLE:
        try:
            verse_extractor = BibleVerseExtractor()
            
            for segment in segments:
                # Extract verses from segment text
                verses = verse_extractor.extract_verses(segment["text"])
                
                # Add verse metadata to segment
                segment["has_verses"] = len(verses) > 0
                segment["verse_count"] = len(verses)
                
                # Format verse references as comma-separated string
                verse_refs = [str(v) for v in verses]
                segment["verse_references"] = ", ".join(verse_refs)
                
                # Extract unique books mentioned
                books = list(set([v.book for v in verses]))
                segment["books_mentioned"] = ", ".join(books)
                
                # Update statistics
                if len(verses) > 0:
                    verse_stats["segments_with_verses"] += 1
                    verse_stats["total_verses"] += len(verses)
                    verse_stats["unique_books"].update(books)
            
            # Display statistics
            if verse_stats["total_verses"] > 0:
                rprint(f"[green]✓[/green] Found {verse_stats['total_verses']} verse references")
                rprint(f"[cyan]Segments with verses:[/cyan] {verse_stats['segments_with_verses']}")
                rprint(f"[cyan]Unique books mentioned:[/cyan] {len(verse_stats['unique_books'])}")
                
                if len(verse_stats["unique_books"]) > 0:
                    books_list = sorted(list(verse_stats["unique_books"]))[:10]
                    rprint(f"[cyan]Top books:[/cyan] {', '.join(books_list)}")
            else:
                rprint("[yellow]ℹ️  No Bible verse references found in this episode[/yellow]")
        
        except Exception as e:
            rprint(f"[yellow]⚠️  Verse extraction failed:[/yellow] {e}")
            rprint("[yellow]Continuing without verse metadata...[/yellow]")
            # Add empty verse fields to all segments
            for segment in segments:
                segment["has_verses"] = False
                segment["verse_count"] = 0
                segment["verse_references"] = ""
                segment["books_mentioned"] = ""
    else:
        # Bible verse extractor not available - add empty fields
        rprint("[yellow]⚠️  Bible verse extraction not available[/yellow]")
        for segment in segments:
            segment["has_verses"] = False
            segment["verse_count"] = 0
            segment["verse_references"] = ""
            segment["books_mentioned"] = ""
    
    # ========================================
    # 6. Generate Embeddings
    # ========================================
    rprint("\n[bold]🧮 Generating Embeddings...[/bold]")
    
    try:
        embedder = Embedder(model_name=settings.embedding_model)
        
        # Extract texts for embedding
        texts = [seg["text"] for seg in segments]
        
        rprint(f"[cyan]Embedding model:[/cyan] {settings.embedding_model}")
        rprint(f"[cyan]Texts to embed:[/cyan] {len(texts)}")
        
        # Generate embeddings
        embeddings = embedder.embed_batch(texts, show_progress=True)
        
        # Add embeddings to segments
        for seg, emb in zip(segments, embeddings):
            seg["embedding"] = emb
        
        rprint(f"[green]✓[/green] Generated {len(embeddings)} embeddings")
        rprint(f"[cyan]Embedding dimension:[/cyan] {len(embeddings[0])}")
        
    except Exception as e:
        rprint(f"[red]❌ Failed to generate embeddings:[/red] {e}")
        return {"success": False, "error": f"Failed to generate embeddings: {e}"}
    
    # ========================================
    # 7. Insert into Vector Store
    # ========================================
    rprint("\n[bold]💾 Inserting into Vector Store...[/bold]")
    
    try:
        inserted_count = milvus.insert_segments(
            segments=segments,
            batch_size=100,
            show_progress=True
        )
        
        if inserted_count == len(segments):
            rprint(f"[green]✅ Successfully ingested episode '{episode_title}'[/green]")
        else:
            rprint(f"[yellow]⚠️  Partial ingestion: {inserted_count}/{len(segments)} segments[/yellow]")
        
    except Exception as e:
        rprint(f"[red]❌ Failed to insert segments:[/red] {e}")
        return {"success": False, "error": f"Failed to insert segments: {e}"}
    
    # ========================================
    # 8. Final Summary
    # ========================================
    rprint("\n[bold green]✅ Ingestion Complete![/bold green]")
    
    # Create summary table
    table = Table(title="Ingestion Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Episode ID", episode_id)
    table.add_row("Episode Title", episode_title)
    table.add_row("Segments Ingested", str(inserted_count))
    table.add_row("Total Words", f"{total_words:,}")
    table.add_row("Avg Words/Segment", f"{avg_words:.1f}")
    table.add_row("Embedding Model", settings.embedding_model)
    table.add_row("Embedding Dimension", str(len(embeddings[0])))
    
    # Add verse statistics if available
    if VERSE_EXTRACTOR_AVAILABLE and verse_stats["total_verses"] > 0:
        table.add_row("─" * 20, "─" * 20)
        table.add_row("Verse References", str(verse_stats["total_verses"]))
        table.add_row("Segments with Verses", str(verse_stats["segments_with_verses"]))
        table.add_row("Unique Books", str(len(verse_stats["unique_books"])))
    
    console.print(table)
    
    # Return results
    return {
        "success": True,
        "episode_id": episode_id,
        "episode_title": episode_title,
        "segments_ingested": inserted_count,
        "total_words": total_words,
        "avg_words_per_segment": avg_words,
        "verse_statistics": {
            "total_verses": verse_stats["total_verses"],
            "segments_with_verses": verse_stats["segments_with_verses"],
            "unique_books": len(verse_stats["unique_books"]),
            "extraction_available": VERSE_EXTRACTOR_AVAILABLE
        }
    }


def ingest_folder(
    folder_path: str,
    force: bool = False,
    chunk_size: int = 3500,
    skip_existing: bool = True,
    max_episodes: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ingest all episodes from a folder with flat structure.
    
    Expected structure (flat):
    folder/
      ├── episode1.json
      ├── episode1.srt
      ├── episode2.json
      ├── episode2.srt
    
    OR subfolder structure:
    folder/
      ├── episode1/
      │   ├── episode.json
      │   └── transcript.srt
      ├── episode2/
      │   ├── episode.json
      │   └── transcript.srt
    
    Args:
        folder_path: Path to folder containing episodes
        force: If True, overwrite existing episodes
        chunk_size: Maximum characters per segment
        skip_existing: Skip episodes that already exist (unless force=True)
        max_episodes: Maximum number of episodes to ingest (None = all)
    
    Returns:
        Dictionary with batch ingestion results
    """
    rprint("\n[bold cyan]📚 Batch Episode Ingestion[/bold cyan]")
    rprint("=" * 60)
    
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        rprint(f"[red]❌ Folder not found:[/red] {folder}")
        return {"success": False, "error": "Folder not found"}
    
    # ========================================
    # Find episode pairs (flat structure)
    # ========================================
    
    # First, try flat structure: find matching .json and .srt files
    json_files = list(folder.glob("*.json"))
    episode_pairs = []
    
    for json_file in json_files:
        # Look for matching .srt file with same base name
        base_name = json_file.stem
        srt_file = json_file.parent / f"{base_name}.srt"
        
        if srt_file.exists():
            episode_pairs.append((json_file, srt_file))
    
    # If no flat structure found, try subfolder structure
    if not episode_pairs:
        episode_folders = [
            d for d in folder.iterdir()
            if d.is_dir() and (d / "episode.json").exists()
        ]
        
        for episode_folder in episode_folders:
            json_file = episode_folder / "episode.json"
            srt_file = episode_folder / "transcript.srt"
            
            if srt_file.exists():
                episode_pairs.append((json_file, srt_file))
    
    # Check if any episodes found
    if not episode_pairs:
        rprint(f"[yellow]⚠️  No episode pairs found in {folder}[/yellow]")
        rprint("[yellow]Looking for:[/yellow]")
        rprint("  • Flat: episode_name.json + episode_name.srt")
        rprint("  • Folders: episode_folder/episode.json + episode_folder/transcript.srt")
        return {"success": False, "error": "No episodes found"}
    
    # ========================================
    # Apply max_episodes limit
    # ========================================
    total_found = len(episode_pairs)
    if max_episodes and max_episodes < total_found:
        episode_pairs = episode_pairs[:max_episodes]
        rprint(f"[cyan]Found {total_found} episodes, limiting to {max_episodes}[/cyan]")
    else:
        rprint(f"[cyan]Found {len(episode_pairs)} episode pairs[/cyan]")
    
    # ========================================
    # Track results
    # ========================================
    results = {
        "total_episodes": len(episode_pairs),
        "total_found": total_found,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "episodes": []
    }
    
    # ========================================
    # Process each episode
    # ========================================
    for i, (json_file, srt_file) in enumerate(episode_pairs, 1):
        rprint(f"\n[bold]Episode {i}/{len(episode_pairs)}[/bold]")
        rprint(f"[cyan]JSON:[/cyan] {json_file.name}")
        rprint(f"[cyan]SRT:[/cyan] {srt_file.name}")
        
        # Get episode title for display
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                episode_data = json.load(f)
            episode_title = episode_data.get('title', json_file.stem)
            rprint(f"[cyan]Title:[/cyan] {episode_title}")
        except Exception as e:
            rprint(f"[red]❌ Error reading {json_file}: {e}[/red]")
            results["failed"] += 1
            continue
        
        # Ingest episode (it handles episode_id generation and duplicate checking)
        try:
            result = ingest_episode(
                episode_json_path=str(json_file),
                transcript_srt_path=str(srt_file),
                force=force,
                chunk_size=chunk_size
            )
            
            if result["success"]:
                results["successful"] += 1
                results["episodes"].append({
                    "episode_id": result["episode_id"],
                    "episode_title": result["episode_title"],
                    "segments": result["segments_ingested"],
                    "verses": result["verse_statistics"]["total_verses"],
                    "status": "success"
                })
                rprint(f"[green]✅ Successfully ingested '{episode_title}'[/green]")
            elif result.get("exists") and skip_existing and not force:
                # Episode already exists and we're skipping
                results["skipped"] += 1
                results["episodes"].append({
                    "episode_id": result.get("episode_id", "unknown"),
                    "episode_title": episode_title,
                    "status": "skipped",
                    "reason": "already exists"
                })
                rprint(f"[yellow]⏭️  Skipped '{episode_title}' - already exists[/yellow]")
            else:
                results["failed"] += 1
                results["episodes"].append({
                    "episode_id": result.get("episode_id", "unknown"),
                    "episode_title": episode_title,
                    "status": "failed",
                    "error": result.get("error", "Unknown error")
                })
                rprint(f"[red]❌ Failed to ingest '{episode_title}'[/red]")
        
        except Exception as e:
            rprint(f"[red]❌ Ingestion failed:[/red] {e}")
            results["failed"] += 1
            results["episodes"].append({
                "episode_id": "unknown",
                "episode_title": episode_title,
                "status": "failed",
                "error": str(e)
            })
    
    # ========================================
    # Final summary
    # ========================================
    rprint("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    rprint("[bold]📊 Batch Ingestion Summary[/bold]")
    
    summary_table = Table(show_header=False)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="white")
    
    # Show if limited
    if max_episodes and max_episodes < total_found:
        summary_table.add_row("Total Episodes Found", str(total_found))
        summary_table.add_row("Processed (Limited)", str(results["total_episodes"]))
    else:
        summary_table.add_row("Total Episodes", str(results["total_episodes"]))
    
    summary_table.add_row("✅ Successful", f"[green]{results['successful']}[/green]")
    summary_table.add_row("❌ Failed", f"[red]{results['failed']}[/red]")
    summary_table.add_row("⏭️  Skipped", f"[yellow]{results['skipped']}[/yellow]")
    
    # Calculate total verses extracted
    total_verses = sum(ep.get("verses", 0) for ep in results["episodes"] if ep["status"] == "success")
    if total_verses > 0:
        summary_table.add_row("📖 Total Verses", str(total_verses))
    
    console.print(summary_table)
    
    results["success"] = results["failed"] == 0
    return results


# ============================================
# CLI Entry Points
# ============================================

def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest podcast episodes into vector store with Bible verse extraction"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Single episode ingestion
    single_parser = subparsers.add_parser("episode", help="Ingest a single episode")
    single_parser.add_argument("json_path", help="Path to episode.json")
    single_parser.add_argument("srt_path", help="Path to transcript.srt")
    single_parser.add_argument("--force", "-f", action="store_true", help="Overwrite if exists")
    single_parser.add_argument("--chunk-size", type=int, default=3500, help="Max chars per segment")
    
    # Batch folder ingestion
    batch_parser = subparsers.add_parser("folder", help="Ingest all episodes from folder")
    batch_parser.add_argument("folder_path", help="Path to folder with episodes")
    batch_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing")
    batch_parser.add_argument("--chunk-size", type=int, default=3500, help="Max chars per segment")
    batch_parser.add_argument("--no-skip", action="store_true", help="Don't skip existing episodes")
    batch_parser.add_argument("--max-episodes", type=int, default=None, help="Maximum episodes to ingest")
    
    args = parser.parse_args()
    
    if args.command == "episode":
        result = ingest_episode(
            episode_json_path=args.json_path,
            transcript_srt_path=args.srt_path,
            force=args.force,
            chunk_size=args.chunk_size
        )
        
        sys.exit(0 if result["success"] else 1)
    
    elif args.command == "folder":
        result = ingest_folder(
            folder_path=args.folder_path,
            force=args.force,
            chunk_size=args.chunk_size,
            skip_existing=not args.no_skip,
            max_episodes=args.max_episodes
        )
        
        sys.exit(0 if result["success"] else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()