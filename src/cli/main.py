"""
Main CLI entry point for DataOverDogma application.
Provides unified command-line interface for all operations.
"""
import typer
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vectorstore.milvus_store import MilvusStore
from src.utils import BibleVerseExtractor

# Initialize Typer app
app = typer.Typer(
    name="dataoverdogma",
    help="Data Over Dogma - Podcast Search and Analysis CLI",
    add_completion=False
)

# Initialize core components
store = MilvusStore()
verse_extractor = BibleVerseExtractor()


# ============================================================================
# INGEST COMMANDS 
# ============================================================================

@app.command()
def ingest_folder(
    folder_path: str = typer.Argument(..., help="Path to folder containing episode JSON files"),
    force: bool = typer.Option(False, "--force", help="Re-ingest episodes even if they exist"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without ingesting"),
    max_episodes: int = typer.Option(None, "--max-episodes", help="Maximum number of episodes to ingest"),
):
    """Ingest multiple episodes from a folder."""
    from src.cli.ingest import ingest_folder as _ingest_folder
    _ingest_folder(Path(folder_path), force=force, max_episodes=max_episodes)


@app.command()
def ingest_episode(
    json_file: str = typer.Argument(..., help="Path to episode JSON file"),
    force: bool = typer.Option(False, "--force", help="Re-ingest even if exists"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without ingesting"),
):
    """Ingest a single episode."""
    from src.cli.ingest import ingest_episode as _ingest_episode
    _ingest_episode(Path(json_file), force=force)


# ============================================================================
# ROOT COMMANDS
# ============================================================================

@app.command()
def status():
    """Show system status and statistics."""
    typer.echo("📊 Data Over Dogma - System Status\n")
    
    # Collection stats
    stats = store.get_stats()
    typer.echo(f"📚 Collection: {stats['collection_name']}")
    typer.echo(f"   Segments: {stats['total_entities']:,}")
    
    typer.echo("\n✅ System operational")


@app.command()
def info():
    """Display application information."""
    typer.echo("🎙️  Data Over Dogma - Podcast Search & Analysis")
    typer.echo("   Version: 2.0.0")
    typer.echo("   Features:")
    typer.echo("   • Semantic search with RAG")
    typer.echo("   • Bible verse extraction")
    typer.echo("   • Episode management")
    typer.echo("   • Multi-modal chunking")
    typer.echo("\n📚 Available commands:")
    typer.echo("   ingest-folder   - Ingest episodes from folder")
    typer.echo("   ingest-episode  - Ingest single episode")
    typer.echo("   status          - System status")
    typer.echo("\n💡 Use --help with any command for more info")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    app()