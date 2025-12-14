"""
CLI tool for deleting episodes from the vector store.
"""
import sys
from pathlib import Path
from typing import Optional, List
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vectorstore.milvus_store import MilvusStore
from src.config.settings import settings

console = Console()


def delete_episode(episode_id: str, confirm: bool = True) -> dict:
    """
    Delete a single episode by ID.
    
    Args:
        episode_id: Episode ID to delete
        confirm: Whether to ask for confirmation
    
    Returns:
        Dictionary with deletion results
    """
    rprint(f"\n[bold red]🗑️  Delete Episode: {episode_id}[/bold red]")
    rprint("=" * 60)
    
    # Initialize Milvus
    try:
        milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
    except Exception as e:
        rprint(f"[red]❌ Failed to connect to Milvus:[/red] {e}")
        return {"success": False, "error": str(e)}
    
    # Check if episode exists
    if not milvus.episode_exists(episode_id):
        rprint(f"[yellow]⚠️  Episode '{episode_id}' not found[/yellow]")
        return {"success": False, "error": "Episode not found"}
    
    # Get episode info
    segments = milvus.get_segments_by_episode(episode_id, limit=1)
    if segments:
        episode_title = segments[0].get("episode_title", "Unknown")
        rprint(f"[cyan]Title:[/cyan] {episode_title}")
    
    # Count segments
    all_segments = milvus.get_segments_by_episode(episode_id)
    segment_count = len(all_segments)
    rprint(f"[cyan]Segments:[/cyan] {segment_count}")
    
    # Confirm deletion
    if confirm:
        should_delete = Confirm.ask(
            f"\n[bold yellow]Delete episode '{episode_id}' ({segment_count} segments)?[/bold yellow]",
            default=False
        )
        
        if not should_delete:
            rprint("[yellow]❌ Deletion cancelled[/yellow]")
            return {"success": False, "cancelled": True}
    
    # Delete episode
    rprint("\n[bold]Deleting...[/bold]")
    result = milvus.delete_episode(episode_id)
    
    if result["success"]:
        rprint(f"[green]✅ Successfully deleted {result['segments_deleted']} segments[/green]")
    else:
        rprint(f"[red]❌ Deletion failed: {result['message']}[/red]")
    
    return result


def delete_episodes_batch(episode_ids: List[str], confirm: bool = True) -> dict:
    """
    Delete multiple episodes.
    
    Args:
        episode_ids: List of episode IDs to delete
        confirm: Whether to ask for confirmation
    
    Returns:
        Dictionary with batch deletion results
    """
    rprint(f"\n[bold red]🗑️  Batch Delete: {len(episode_ids)} Episodes[/bold red]")
    rprint("=" * 60)
    
    # Initialize Milvus
    try:
        milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
    except Exception as e:
        rprint(f"[red]❌ Failed to connect to Milvus:[/red] {e}")
        return {"success": False, "error": str(e)}
    
    # Validate episodes exist
    valid_episodes = []
    total_segments = 0
    
    for ep_id in episode_ids:
        if milvus.episode_exists(ep_id):
            segments = milvus.get_segments_by_episode(ep_id)
            valid_episodes.append({
                "episode_id": ep_id,
                "segment_count": len(segments)
            })
            total_segments += len(segments)
        else:
            rprint(f"[yellow]⚠️  Episode '{ep_id}' not found - skipping[/yellow]")
    
    if not valid_episodes:
        rprint("[red]❌ No valid episodes to delete[/red]")
        return {"success": False, "error": "No valid episodes"}
    
    # Show summary
    rprint(f"\n[cyan]Episodes to delete:[/cyan] {len(valid_episodes)}")
    rprint(f"[cyan]Total segments:[/cyan] {total_segments}")
    
    # Confirm
    if confirm:
        should_delete = Confirm.ask(
            f"\n[bold yellow]Delete {len(valid_episodes)} episodes ({total_segments} segments)?[/bold yellow]",
            default=False
        )
        
        if not should_delete:
            rprint("[yellow]❌ Deletion cancelled[/yellow]")
            return {"success": False, "cancelled": True}
    
    # Delete episodes
    results = {
        "total": len(valid_episodes),
        "successful": 0,
        "failed": 0,
        "total_segments_deleted": 0,
        "episodes": []
    }
    
    for ep in valid_episodes:
        ep_id = ep["episode_id"]
        rprint(f"\n[bold]Deleting {ep_id}...[/bold]")
        
        result = milvus.delete_episode(ep_id)
        
        if result["success"]:
            results["successful"] += 1
            results["total_segments_deleted"] += result["segments_deleted"]
            rprint(f"[green]✅ Deleted {result['segments_deleted']} segments[/green]")
        else:
            results["failed"] += 1
            rprint(f"[red]❌ Failed: {result['message']}[/red]")
        
        results["episodes"].append({
            "episode_id": ep_id,
            "success": result["success"],
            "segments_deleted": result.get("segments_deleted", 0)
        })
    
    # Summary
    rprint("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    rprint("[bold]📊 Deletion Summary[/bold]")
    
    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="white")
    
    table.add_row("Total Episodes", str(results["total"]))
    table.add_row("✅ Successful", f"[green]{results['successful']}[/green]")
    table.add_row("❌ Failed", f"[red]{results['failed']}[/red]")
    table.add_row("Total Segments Deleted", str(results["total_segments_deleted"]))
    
    console.print(table)
    
    results["success"] = results["failed"] == 0
    return results


def delete_all_episodes(confirm: bool = True) -> dict:
    """
    Delete ALL episodes from the database.
    
    Args:
        confirm: Whether to ask for confirmation
    
    Returns:
        Dictionary with deletion results
    """
    rprint("\n[bold red]🗑️  DELETE ALL EPISODES[/bold red]")
    rprint("=" * 60)
    rprint("[red]⚠️  WARNING: This will delete EVERYTHING in the collection![/red]")
    
    # Initialize Milvus
    try:
        milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
    except Exception as e:
        rprint(f"[red]❌ Failed to connect to Milvus:[/red] {e}")
        return {"success": False, "error": str(e)}
    
    # Get stats
    stats = milvus.get_collection_stats()
    episode_count = milvus.get_episode_count()
    
    rprint(f"\n[cyan]Total episodes:[/cyan] {episode_count}")
    rprint(f"[cyan]Total segments:[/cyan] {stats['num_entities']}")
    
    # Confirm (ALWAYS ask, even if confirm=False)
    rprint("\n[bold red]⚠️  THIS CANNOT BE UNDONE![/bold red]")
    
    if confirm:
        # Double confirmation for safety
        first_confirm = Confirm.ask(
            "[bold yellow]Are you SURE you want to delete ALL episodes?[/bold yellow]",
            default=False
        )
        
        if not first_confirm:
            rprint("[yellow]❌ Deletion cancelled[/yellow]")
            return {"success": False, "cancelled": True}
        
        second_confirm = Confirm.ask(
            "[bold red]FINAL CONFIRMATION: Delete EVERYTHING?[/bold red]",
            default=False
        )
        
        if not second_confirm:
            rprint("[yellow]❌ Deletion cancelled[/yellow]")
            return {"success": False, "cancelled": True}
    
    # Delete
    rprint("\n[bold]Clearing collection...[/bold]")
    success = milvus.clear_collection()
    
    if success:
        rprint(f"[green]✅ Successfully deleted all {stats['num_entities']} segments[/green]")
    else:
        rprint("[red]❌ Deletion failed[/red]")
    
    return {
        "success": success,
        "episodes_deleted": episode_count,
        "segments_deleted": stats['num_entities']
    }


def list_episodes_for_deletion() -> None:
    """
    List all episodes with their IDs (for choosing what to delete).
    """
    rprint("\n[bold cyan]📋 Episodes in Database[/bold cyan]")
    rprint("=" * 60)
    
    # Initialize Milvus
    try:
        milvus = MilvusStore(
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            collection_name=settings.milvus_collection
        )
    except Exception as e:
        rprint(f"[red]❌ Failed to connect to Milvus:[/red] {e}")
        return
    
    # Get episodes
    episodes = milvus.get_unique_episodes()
    
    if not episodes:
        rprint("[yellow]No episodes found in database[/yellow]")
        return
    
    # Create table
    table = Table(title=f"Episodes ({len(episodes)} total)", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Episode ID", style="cyan", width=20)
    table.add_column("Title", style="white")
    
    for i, ep in enumerate(episodes, 1):
        # Get segment count
        segments = milvus.get_segments_by_episode(ep["episode_id"], limit=1)
        
        table.add_row(
            str(i),
            ep["episode_id"],
            ep["episode_title"]
        )
    
    console.print(table)
    rprint(f"\n[cyan]Total:[/cyan] {len(episodes)} episodes")


def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete episodes from the vector store"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List episodes
    list_parser = subparsers.add_parser("list", help="List all episodes")
    
    # Delete single episode
    single_parser = subparsers.add_parser("episode", help="Delete a single episode")
    single_parser.add_argument("episode_id", help="Episode ID to delete")
    single_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    
    # Delete multiple episodes
    batch_parser = subparsers.add_parser("batch", help="Delete multiple episodes")
    batch_parser.add_argument("episode_ids", nargs="+", help="Episode IDs to delete")
    batch_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    
    # Delete all
    all_parser = subparsers.add_parser("all", help="Delete ALL episodes")
    all_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation (still asks once)")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_episodes_for_deletion()
    
    elif args.command == "episode":
        result = delete_episode(
            episode_id=args.episode_id,
            confirm=not args.yes
        )
        sys.exit(0 if result["success"] else 1)
    
    elif args.command == "batch":
        result = delete_episodes_batch(
            episode_ids=args.episode_ids,
            confirm=not args.yes
        )
        sys.exit(0 if result["success"] else 1)
    
    elif args.command == "all":
        result = delete_all_episodes(confirm=True)  # Always confirm for safety
        sys.exit(0 if result["success"] else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()