"""
OpenAI API client for LLM operations.
Handles query rewriting, answer generation, and streaming responses.
"""
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from typing import List, Dict, Optional, Union, Generator, Any
import os


class OpenAIClient:
    """
    Client for interacting with OpenAI's API for RAG operations.
    
    Supports:
    - Query rewriting for better search results
    - Context-aware query enhancement
    - Answer generation with streaming
    - Conversation history management
    
    Attributes:
        client: OpenAI client instance
        model: Model name for completions
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use for completions
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            
        Raises:
            ValueError: If API key is not found
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        print(f"✅ OpenAI client initialized (model: {model})")
    
    # ============================================
    # Query Rewriting
    # ============================================
    
    def rewrite_query(
        self,
        query: str,
        style: str = "semantic"
    ) -> str:
        """
        Rewrite a user query to improve search results.
        
        This method enhances queries by making them more semantically rich,
        extracting keywords, or expanding with related concepts.
        
        Args:
            query: Original user query
            style: Rewriting style - one of:
                - 'semantic': Make query more semantically rich
                - 'keywords': Extract and expand key terms
                - 'expanded': Add related concepts and synonyms
        
        Returns:
            Rewritten query string (or original if rewriting fails)
            
        Examples:
            >>> client.rewrite_query("paul grace", style="semantic")
            "What did the Apostle Paul teach about grace and salvation?"
            
            >>> client.rewrite_query("paul grace", style="keywords")
            "Paul apostle grace salvation faith justification Romans"
        """
        # Select system prompt based on style
        if style == "semantic":
            system_prompt = (
                "You are a query optimization expert. Rewrite the user's query to be more "
                "semantically rich and specific for semantic search over podcast transcripts. "
                "Keep it concise but add relevant context and terminology."
            )
        elif style == "keywords":
            system_prompt = (
                "You are a query optimization expert. Extract and expand key search terms "
                "from the user's query. Return only the essential keywords and phrases."
            )
        elif style == "expanded":
            system_prompt = (
                "You are a query optimization expert. Expand the user's query with related "
                "concepts, synonyms, and theological terminology that might appear in "
                "biblical/theological podcasts."
            )
        else:
            system_prompt = (
                "You are a query optimization expert. Improve the user's query for "
                "better semantic search results."
            )
        
        # Build messages with proper typing
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Original query: {query}\n\nRewritten query:"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.5  # Lower temperature for more focused rewriting
            )
            
            # Extract content with null check
            content = response.choices[0].message.content
            if content is None:
                print("⚠️  Query rewriting returned no content")
                return query  # Fallback if no content
            
            rewritten = content.strip()
            
            # Clean up common LLM prefixes
            rewritten = self._clean_llm_response(rewritten)
            
            # Fallback to original if cleaned result is empty
            return rewritten if rewritten else query
            
        except Exception as e:
            print(f"⚠️  Query rewriting failed: {e}")
            return query  # Fallback to original query
    
    def rewrite_query_with_context(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        max_history: int = 3
    ) -> str:
        """
        Rewrite a query using conversation context for better continuity.
        
        This method creates standalone queries that incorporate relevant
        context from previous conversation exchanges.
        
        Args:
            query: Current user query
            conversation_history: List of previous messages with 'role' and 'content' keys
            max_history: Maximum number of previous exchanges to consider
        
        Returns:
            Context-aware rewritten query (or original if rewriting fails)
            
        Examples:
            >>> history = [
            ...     {"role": "user", "content": "Who is Paul?"},
            ...     {"role": "assistant", "content": "Paul was an apostle..."}
            ... ]
            >>> client.rewrite_query_with_context("What did he teach?", history)
            "What did the Apostle Paul teach about theology and doctrine?"
        """
        # Limit history to recent exchanges
        recent_history = conversation_history[-max_history * 2:] if conversation_history else []
        
        # Build context string
        context_str = "\n".join([
            f"{msg.get('role', 'user').title()}: {msg.get('content', '')}"
            for msg in recent_history
        ])
        
        system_prompt = (
            "You are a query optimization expert. The user is having a conversation about "
            "podcast content. Rewrite their latest query to be a standalone, semantically "
            "rich query that incorporates relevant context from the conversation history. "
            "The rewritten query should work well for semantic search."
        )
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Conversation history:
{context_str}

Current query: {query}

Rewrite this query to be standalone and semantically rich:"""}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.5
            )
            
            # Extract content with null check
            content = response.choices[0].message.content
            if content is None:
                print("⚠️  Context-aware query rewriting returned no content")
                return query
            
            rewritten = content.strip()
            
            # Clean up common LLM prefixes
            rewritten = self._clean_llm_response(rewritten)
            
            # Fallback to original if cleaned result is empty
            return rewritten if rewritten else query
            
        except Exception as e:
            print(f"⚠️  Context-aware query rewriting failed: {e}")
            return query  # Fallback to original query
    
    # ============================================
    # Answer Generation
    # ============================================
    
    def answer_query(
        self,
        query: str,
        context_segments: Union[List[Dict[str, Any]], List[str]],
        conversation_context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a complete answer to a query using retrieved context.
        
        Args:
            query: User's question
            context_segments: List of relevant transcript segments (dicts or strings)
            conversation_context: Previous conversation as formatted string
            conversation_history: Alternative - list of message dicts
            system_prompt: Optional custom system prompt
        
        Returns:
            Complete answer as a string
            
        Examples:
            >>> segments = [
            ...     {"text": "Paul discusses grace...", "episode_title": "Romans Study"}
            ... ]
            >>> client.answer_query("What did Paul say about grace?", segments)
            "Based on the transcript, Paul discusses grace as..."
        """
        messages = self._build_answer_messages(
            query=query,
            context_segments=context_segments,
            conversation_context=conversation_context,
            conversation_history=conversation_history,
            system_prompt=system_prompt
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Extract content with null check
            content = response.choices[0].message.content
            if content is None:
                return "Error: No response generated"
            
            answer = content.strip()
            return answer
            
        except Exception as e:
            error_msg = f"Error generating answer: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def answer_query_stream(
        self,
        query: str,
        context_segments: Union[List[Dict[str, Any]], List[str]],
        conversation_context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Stream an answer to a query using retrieved context segments.
        
        NOTE: This returns a SYNC generator because OpenAI's stream=True
        returns a synchronous iterator. Use asyncio.run_in_executor to
        consume this in async contexts (like FastAPI endpoints).
        
        Args:
            query: User's question
            context_segments: List of relevant transcript segments
            conversation_context: Previous conversation as string
            conversation_history: Alternative - list of message dicts
            system_prompt: Optional custom system prompt
        
        Yields:
            Answer chunks as strings
            
        Examples:
            >>> for chunk in client.answer_query_stream("What is grace?", segments):
            ...     print(chunk, end="", flush=True)
            Grace is the unmerited favor of God...
        """
        messages = self._build_answer_messages(
            query=query,
            context_segments=context_segments,
            conversation_context=conversation_context,
            conversation_history=conversation_history,
            system_prompt=system_prompt
        )
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            
            for chunk in stream:
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    yield delta_content
                    
        except Exception as e:
            error_msg = f"Error generating answer: {str(e)}"
            print(f"❌ {error_msg}")
            yield error_msg
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _build_answer_messages(
        self,
        query: str,
        context_segments: Union[List[Dict[str, Any]], List[str]],
        conversation_context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> List[ChatCompletionMessageParam]:
        """
        Build message list for answer generation with proper type safety.
        
        Args:
            query: User's question
            context_segments: List of relevant transcript segments (dict or string)
            conversation_context: Previous conversation as formatted string
            conversation_history: Alternative - list of message dicts
            system_prompt: Optional custom system prompt
        
        Returns:
            List of properly typed message dicts for OpenAI API
        """
        # Default system prompt
        if not system_prompt:
            system_prompt = (
                "You are a knowledgeable assistant specializing in biblical and theological content. "
                "Answer questions based on the provided podcast transcript context. "
                "Be specific, cite relevant information from the context, and acknowledge when "
                "the context doesn't contain enough information to fully answer the question. "
                "Maintain an academic yet accessible tone."
            )
        
        # Format context segments based on type
        context_text = self._format_context_segments(context_segments)
        
        # Build conversation history string
        history_text = self._format_conversation_history(
            conversation_context,
            conversation_history
        )
        
        # Add history to prompt if present
        history_prompt = ""
        if history_text:
            history_prompt = f"\n\nPrevious conversation:\n{history_text}\n"
        
        # Build user prompt
        user_prompt = f"""Answer the following question based on the provided context from podcast transcripts.

Be specific and cite information from the context when possible. If the context doesn't contain 
enough information to fully answer the question, acknowledge this honestly and provide what 
information is available.{history_prompt}

Context from podcast transcripts:
{context_text}

Question: {query}

Answer:"""
        
        # Build messages with proper typing
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return messages
    
    def _format_context_segments(
        self,
        context_segments: Union[List[Dict[str, Any]], List[str]]
    ) -> str:
        """
        Format context segments into a string, handling both dict and string formats.
        
        Args:
            context_segments: List of segments (either dicts with metadata or strings)
            
        Returns:
            Formatted context string
        """
        if not context_segments:
            return ""
        
        # Check the type of the first item
        first_item = context_segments[0]
        
        if isinstance(first_item, dict):
            # Rich format with metadata
            context_parts = []
            for seg in context_segments:
                # Type guard: ensure we're working with a dict
                if isinstance(seg, dict):
                    episode_title = seg.get('episode_title', 'Unknown')
                    start_time = seg.get('start_time', 'N/A')
                    end_time = seg.get('end_time', 'N/A')
                    text = seg.get('text', '')
                    
                    context_parts.append(
                        f"[Episode: {episode_title}] "
                        f"(Timestamp: {start_time} - {end_time})\n"
                        f"{text}"
                    )
            return "\n\n".join(context_parts)
        else:
            # Simple string format
            return "\n\n".join(str(seg) for seg in context_segments)
    
    def _format_conversation_history(
        self,
        conversation_context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Format conversation history into a string.
        
        Args:
            conversation_context: Pre-formatted conversation string
            conversation_history: List of message dicts with 'role' and 'content'
            
        Returns:
            Formatted conversation history string
        """
        # Use provided context if available
        if conversation_context:
            return conversation_context
        
        # Build from message list
        if conversation_history:
            history_parts = []
            for msg in conversation_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                history_parts.append(f"{role.title()}: {content}")
            return "\n".join(history_parts)
        
        return ""
    
    def _clean_llm_response(self, response: str) -> str:
        """
        Clean common prefixes and formatting from LLM responses.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Cleaned response string
        """
        # Remove common prefixes
        prefixes_to_remove = [
            "Rewritten query:",
            "Rewritten:",
            "Query:",
            "Standalone query:",
            "Here is the rewritten query:",
            "Here's the rewritten query:",
            "The rewritten query is:",
        ]
        
        cleaned = response.strip()
        
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove surrounding quotes
        cleaned = cleaned.strip('"\'')
        
        return cleaned
    
    # ============================================
    # Utility Methods
    # ============================================
    
    def test_connection(self) -> bool:
        """
        Test if the OpenAI API connection is working.
        
        Returns:
            True if connection successful, False otherwise
            
        Examples:
            >>> client = OpenAIClient()
            >>> if client.test_connection():
            ...     print("Connected!")
            Connected!
        """
        try:
            messages: List[ChatCompletionMessageParam] = [
                {"role": "user", "content": "Hello"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=5
            )
            
            print("✅ OpenAI connection test successful")
            return True
            
        except Exception as e:
            print(f"❌ OpenAI connection test failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get current model configuration.
        
        Returns:
            Dictionary with model settings
        """
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "api_key_set": bool(self.api_key)
        }
    
    def update_settings(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> None:
        """
        Update client settings.
        
        Args:
            temperature: New temperature value (0.0-2.0)
            max_tokens: New max tokens value
        """
        if temperature is not None:
            if not 0.0 <= temperature <= 2.0:
                raise ValueError("Temperature must be between 0.0 and 2.0")
            self.temperature = temperature
            print(f"✅ Temperature updated to {temperature}")
        
        if max_tokens is not None:
            if max_tokens < 1:
                raise ValueError("Max tokens must be positive")
            self.max_tokens = max_tokens
            print(f"✅ Max tokens updated to {max_tokens}")
    
    def __repr__(self) -> str:
        """String representation of the client."""
        return (
            f"OpenAIClient(model={self.model}, "
            f"temperature={self.temperature}, "
            f"max_tokens={self.max_tokens})"
        )
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"OpenAI Client using {self.model}"


# ============================================
# Convenience Functions
# ============================================

def create_client(
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 500
) -> OpenAIClient:
    """
    Factory function to create an OpenAI client with validation.
    
    Args:
        api_key: Optional API key (uses env var if not provided)
        model: Model to use for completions
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
    
    Returns:
        Configured OpenAIClient instance
        
    Raises:
        ValueError: If parameters are invalid
        
    Examples:
        >>> client = create_client(model="gpt-4")
        >>> client.test_connection()
        True
    """
    return OpenAIClient(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )


def test_openai_setup() -> bool:
    """
    Test if OpenAI is properly configured.
    
    Returns:
        True if setup is valid, False otherwise
    """
    try:
        client = create_client()
        return client.test_connection()
    except Exception as e:
        print(f"❌ OpenAI setup test failed: {e}")
        return False


# ============================================
# Module-level test
# ============================================

if __name__ == "__main__":
    print("🧪 Testing OpenAI client setup...")
    
    if test_openai_setup():
        print("✅ All tests passed!")
    else:
        print("❌ Setup test failed. Check your API key.")