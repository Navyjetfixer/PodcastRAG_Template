"""
Conversation history management for multi-turn queries.
Enhanced with naming, branching, search, and export capabilities.
"""
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path
from datetime import datetime
import re


class ConversationHistory:
    """Manages conversation history for contextual queries with enhanced features."""
    
    def __init__(self, conversation_id: str, storage_dir: str = ".conversations"):
        """
        Initialize conversation history.
        
        Args:
            conversation_id: Unique conversation identifier
            storage_dir: Directory to store conversation files
        """
        self.conversation_id = conversation_id
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.file_path = self.storage_dir / f"{conversation_id}.json"
        
        # Conversation metadata
        self.name: str = ""
        self.created_at: str = ""
        self.updated_at: str = ""
        self.parent_id: Optional[str] = None
        self.branch_point: Optional[int] = None
        self.messages: List[Dict] = []
        
        self._load()
    
    def _load(self):
        """Load conversation from file if it exists."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load metadata
                self.name = data.get("name", f"Conversation {self.conversation_id[:8]}")
                self.created_at = data.get("created_at", datetime.now().isoformat())
                self.updated_at = data.get("updated_at", datetime.now().isoformat())
                self.parent_id = data.get("parent_id")
                self.branch_point = data.get("branch_point")
                self.messages = data.get("messages", [])
                
            except Exception as e:
                print(f"Warning: Could not load conversation: {e}")
                self._initialize_new()
        else:
            self._initialize_new()
    
    def _initialize_new(self):
        """Initialize a new conversation with default metadata."""
        self.name = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.messages = []
    
    def _save(self):
        """Save conversation to file."""
        try:
            self.updated_at = datetime.now().isoformat()
            
            data = {
                "conversation_id": self.conversation_id,
                "name": self.name,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "parent_id": self.parent_id,
                "branch_point": self.branch_point,
                "message_count": len(self.messages),
                "messages": self.messages
            }
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Warning: Could not save conversation: {e}")
    
    def set_name(self, name: str):
        """
        Set conversation name.
        
        Args:
            name: New conversation name
        """
        self.name = name
        self._save()
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a message to the conversation.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
            metadata: Optional metadata dict
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            message["metadata"] = metadata
        
        self.messages.append(message)
        self._save()
    
    def get_history(self, last_n: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history.
        
        Args:
            last_n: Get only the last N messages
        
        Returns:
            List of message dictionaries
        """
        if last_n:
            return self.messages[-last_n:]
        return self.messages
    
    def search(self, query: str) -> List[Tuple[int, Dict, str]]:
        """
        Search within conversation messages.
        
        Args:
            query: Search term (case-insensitive)
        
        Returns:
            List of tuples: (message_index, message_dict, match_type)
            match_type is either 'user' or 'assistant'
        """
        query_lower = query.lower()
        results = []
        
        for idx, message in enumerate(self.messages):
            role = message.get("role", "")
            content = message.get("content", "")
            
            if query_lower in content.lower():
                results.append((idx, message, role))
        
        return results
    
    def branch(self, branch_point: int, new_conversation_id: str, 
               branch_name: Optional[str] = None) -> 'ConversationHistory':
        """
        Create a new conversation branch from a specific message.
        
        Args:
            branch_point: Index of message to branch from
            new_conversation_id: ID for the new branched conversation
            branch_name: Optional name for the branch
        
        Returns:
            New ConversationHistory object
        """
        if branch_point < 0 or branch_point >= len(self.messages):
            raise ValueError(f"Invalid branch point: {branch_point}")
        
        # Create new conversation
        new_conv = ConversationHistory(new_conversation_id, str(self.storage_dir))
        
        # Set metadata
        new_conv.name = branch_name or f"Branch from {self.name}"
        new_conv.parent_id = self.conversation_id
        new_conv.branch_point = branch_point
        
        # Copy messages up to branch point
        new_conv.messages = self.messages[:branch_point + 1].copy()
        
        # Save
        new_conv._save()
        
        return new_conv
    
    def export_json(self) -> str:
        """
        Export conversation as JSON string.
        
        Returns:
            JSON string representation of conversation
        """
        data = {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_id": self.parent_id,
            "branch_point": self.branch_point,
            "message_count": len(self.messages),
            "messages": self.messages
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def export_text(self) -> str:
        """
        Export conversation as formatted text.
        
        Returns:
            Human-readable text representation
        """
        lines = [
            f"Conversation: {self.name}",
            f"ID: {self.conversation_id}",
            f"Created: {self.created_at}",
            f"Updated: {self.updated_at}",
            f"Messages: {len(self.messages)}",
            "=" * 80,
            ""
        ]
        
        if self.parent_id:
            lines.insert(4, f"Branched from: {self.parent_id} (at message {self.branch_point})")
        
        for idx, msg in enumerate(self.messages, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            
            lines.append(f"--- Message {idx} [{timestamp}] ---")
            lines.append(f"{role.upper()}: {content}")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_metadata(self) -> Dict:
        """
        Get conversation metadata.
        
        Returns:
            Dictionary with conversation metadata
        """
        return {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_id": self.parent_id,
            "branch_point": self.branch_point,
            "message_count": len(self.messages),
            "is_branch": self.parent_id is not None
        }
    
    def clear(self):
        """Clear conversation history."""
        self.messages = []
        if self.file_path.exists():
            self.file_path.unlink()
    
    def __len__(self):
        """Get number of messages in conversation."""
        return len(self.messages)