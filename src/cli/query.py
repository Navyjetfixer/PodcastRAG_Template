"""
Query functionality for semantic search and Q&A with RAG features.
"""
from typing import List, Optional, Dict
import uuid
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.vectorstore.milvus_store import MilvusStore
from src.embeddings.embedder import Embedder
from src.llm.openai_api import OpenAIClient
from src.config.settings import settings
from src.cli.conversation import ConversationHistory

console = Console()


def query_flow(
    query: str,
    top_k: int = 5,
    episode_filter: Optional[str] = None,
    min_score: float = 0.0,
    use_rewrite: bool = True,
    use_context: bool = True,
    conversation_id: Optional[str] = None
):
    """
    Complete query flow with semantic search and AI-powered Q&A.
    
    Args:
        query: User's search query or question
        top_k: Number of results to return
        episode_filter: Optional episode ID to filter by
        min_score: Minimum similarity score threshold
        use_rewrite: Whether to use query rewriting
        use_context: Whether to use conversation context
        conversation_id: Existing conversation ID for context
    """
    
    # Initialize services
    milvus = MilvusStore(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        collection_name=settings.milvus_collection
    )
    embedder = Embedder(model_name=settings.embedding_model)
    llm = OpenAIClient()
    
    # Get or create conversation
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
    
    conversation = ConversationHistory(conversation_id)
    
    # Step 1: Query Rewriting (if enabled)
    query_to_use = query
    rewritten_query = None
    
    if use_rewrite:
        rprint("[dim]🔄 Rewriting query for better retrieval...[/dim]")
        
        if use_context and len(conversation) > 0:
            # Use conversation context for rewriting
            context_messages = conversation.get_history()[-3:]  # Last 3 turns
            rewritten_query = llm.rewrite_query_with_context(query, context_messages)
        else:
            # Simple query expansion
            rewritten_query = llm.rewrite_query(query)
        
        if rewritten_query and rewritten_query != query:
            query_to_use = rewritten_query
            rprint(f"[cyan]📝 Rewritten:[/cyan] {rewritten_query}\n")
    
    # Step 2: Embed Query
    rprint("[dim]🔍 Searching for relevant segments...[/dim]")
    query_embedding = embedder.embed(query_to_use)
    
    # Step 3: Build Filter Expression
    filter_expr = None
    if episode_filter:
        filter_expr = f'episode_id == "{episode_filter}"'
        rprint(f"[dim]📌 Filtering by episode: {episode_filter}[/dim]")
    
    # Step 4: Search Milvus
    results = milvus.search(
        query_embedding=query_embedding,
        top_k=top_k * 2,  # Get more, then filter by score
        filter_expr=filter_expr
    )
    
    # Step 5: Filter by Minimum Score
    filtered_results = [
        r for r in results 
        if r.get("score", 0.0) >= min_score
    ][:top_k]
    
    if not filtered_results:
        rprint("\n[yellow]⚠️  No results found matching your criteria.[/yellow]")
        rprint("[dim]Try lowering --min-score or broadening your query.[/dim]\n")
        return
    
    # Display Search Results
    rprint(f"\n[bold cyan]📊 Found {len(filtered_results)} relevant segments[/bold cyan]\n")
    display_search_results(filtered_results)
    
    # Step 6: Generate AI Answer
    rprint("\n[bold cyan]🤖 Generating AI Answer...[/bold cyan]\n")
    
    # Prepare context
    context_segments = [r.get("text", "") for r in filtered_results[:3]]
    
    # Build conversation context
    conversation_context = ""
    if use_context and len(conversation) > 0:
        conversation_context = "Previous conversation:\n"
        for msg in conversation.get_history()[-3:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation_context += f"{role}: {content}\n"
        conversation_context += "\n"
    
    # Generate answer
    try:
        answer = llm.answer_query(
            query=query,
            context_segments=context_segments,
            conversation_context=conversation_context
        )
        
        # Display answer
        display_answer(answer, filtered_results[:3])
        
        # Store in conversation history
        if use_context:
            conversation.add_message("user", query, {"rewritten": rewritten_query})
            conversation.add_message("assistant", answer)
            
            rprint(f"\n[dim]💬 Conversation ID: {conversation_id}[/dim]")
            rprint("[dim]Use --conversation {id} to continue this conversation[/dim]\n")
    
    except Exception as e:
        rprint(f"\n[bold red]❌ Failed to generate answer: {e}[/bold red]\n")


def display_search_results(results: List[Dict]):
    """
    Display search results in a formatted table.
    
    Args:
        results: List of search result dictionaries
    """
    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Episode", style="cyan", width=30)
    table.add_column("Time", style="yellow", width=20)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Text", width=80)
    
    for i, result in enumerate(results, 1):
        episode_title = result.get("episode_title", "Unknown")
        start_time = result.get("start_time", "")
        end_time = result.get("end_time", "")
        score = result.get("score", 0.0)
        text = result.get("text", "")
        
        # Truncate text if too long
        if len(text) > 200:
            text = text[:200] + "..."
        
        # Color code score
        score_text = f"{score * 100:.1f}%"
        if score >= 0.8:
            score_text = f"[green]{score_text}[/green]"
        elif score >= 0.6:
            score_text = f"[yellow]{score_text}[/yellow]"
        else:
            score_text = f"[red]{score_text}[/red]"
        
        table.add_row(
            str(i),
            episode_title,
            f"{start_time} - {end_time}",
            score_text,
            text
        )
    
    console.print(table)


def display_answer(answer: str, sources: List[Dict]):
    """
    Display AI-generated answer with sources.
    
    Args:
        answer: Generated answer text
        sources: List of source segments
    """
    # Display answer in a panel
    answer_panel = Panel(
        answer,
        title="[bold green]🤖 AI Answer[/bold green]",
        border_style="green",
        padding=(1, 2)
    )
    console.print(answer_panel)
    
    # Display sources
    rprint("\n[bold cyan]📚 Sources:[/bold cyan]\n")
    
    for i, source in enumerate(sources, 1):
        episode = source.get("episode_title", "Unknown")
        start = source.get("start_time", "")
        end = source.get("end_time", "")
        text = source.get("text", "")
        
        # Truncate source text
        if len(text) > 150:
            text = text[:150] + "..."
        
        rprint(f"[bold]{i}. {episode}[/bold]")
        rprint(f"   [dim]{start} - {end}[/dim]")
        rprint(f"   {text}\n")


def search_only(
    query: str,
    top_k: int = 5,
    episode_filter: Optional[str] = None,
    min_score: float = 0.0
):
    """
    Perform semantic search without AI answer generation.
    
    Args:
        query: Search query
        top_k: Number of results
        episode_filter: Optional episode ID filter
        min_score: Minimum similarity score
    """
    # Initialize services
    milvus = MilvusStore(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        collection_name=settings.milvus_collection
    )
    embedder = Embedder(model_name=settings.embedding_model)
    
    rprint("[dim]🔍 Searching...[/dim]")
    
    # Embed query
    query_embedding = embedder.embed(query)
    
    # Build filter
    filter_expr = None
    if episode_filter:
        filter_expr = f'episode_id == "{episode_filter}"'
    
    # Search
    results = milvus.search(
        query_embedding=query_embedding,
        top_k=top_k * 2,
        filter_expr=filter_expr
    )
    
    # Filter by score
    filtered_results = [
        r for r in results 
        if r.get("score", 0.0) >= min_score
    ][:top_k]
    
    if not filtered_results:
        rprint("\n[yellow]⚠️  No results found.[/yellow]\n")
        return
    
    rprint(f"\n[bold cyan]📊 Found {len(filtered_results)} results[/bold cyan]\n")
    display_search_results(filtered_results)