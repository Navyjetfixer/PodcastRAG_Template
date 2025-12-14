"""
Conversation management routes for the DataOverDogma search interface.
Handles conversation CRUD operations, branching, naming, export, and search.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO

router = APIRouter()

# Conversation storage directory
CONVERSATIONS_DIR = Path("src/.web_conversations")
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ConversationCreate(BaseModel):
    name: Optional[str] = None

class ConversationUpdate(BaseModel):
    name: Optional[str] = None
    message: Optional[Dict[str, Any]] = None

class ConversationBranch(BaseModel):
    message_index: int
    name: Optional[str] = None

class ConversationSearch(BaseModel):
    query: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_conversation_path(conversation_id: str) -> Path:
    """Get file path for a conversation."""
    return CONVERSATIONS_DIR / f"{conversation_id}.json"


def load_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation from disk."""
    path = get_conversation_path(conversation_id)
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading conversation {conversation_id}: {e}")
        return None


def save_conversation(conversation: Dict[str, Any]) -> bool:
    """Save a conversation to disk."""
    try:
        path = get_conversation_path(conversation['id'])
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return False


def delete_conversation_file(conversation_id: str) -> bool:
    """Delete a conversation file from disk."""
    try:
        path = get_conversation_path(conversation_id)
        if path.exists():
            path.unlink()
        return True
    except Exception as e:
        print(f"Error deleting conversation {conversation_id}: {e}")
        return False


def create_new_conversation(name: Optional[str] = None) -> Dict[str, Any]:
    """Create a new conversation object."""
    conversation_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    return {
        "id": conversation_id,
        "name": name or f"Conversation {timestamp[:10]}",
        "created_at": timestamp,
        "updated_at": timestamp,
        "parent_id": None,
        "branch_point": None,
        "messages": [],
        "message_count": 0
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/list")
async def list_conversations():
    """
    List all conversations.
    Returns conversations sorted by updated_at (newest first).
    """
    try:
        conversations = []
        
        for conv_file in CONVERSATIONS_DIR.glob("*.json"):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv = json.load(f)
                    conversations.append({
                        "conversation_id": conv["id"],
                        "name": conv["name"],
                        "created_at": conv["created_at"],
                        "updated_at": conv["updated_at"],
                        "message_count": conv.get("message_count", len(conv.get("messages", []))),
                        "parent_id": conv.get("parent_id"),
                        "is_branch": conv.get("parent_id") is not None
                    })
            except Exception as e:
                print(f"Error loading conversation {conv_file}: {e}")
                continue
        
        # Sort by updated_at (newest first)
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)
        
        return conversations
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all messages."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@router.post("")
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    conversation = create_new_conversation(data.name)
    
    if save_conversation(conversation):
        return conversation
    else:
        raise HTTPException(status_code=500, detail="Failed to save conversation")


@router.put("/{conversation_id}/rename")
async def rename_conversation(conversation_id: str, data: ConversationUpdate):
    """Rename a conversation."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if data.name:
        conversation['name'] = data.name
        conversation['updated_at'] = datetime.now().isoformat()
        
        if save_conversation(conversation):
            return {"success": True, "new_name": data.name}
        else:
            raise HTTPException(status_code=500, detail="Failed to save conversation")
    
    raise HTTPException(status_code=400, detail="Name is required")


@router.put("/{conversation_id}")
async def update_conversation(conversation_id: str, data: ConversationUpdate):
    """Update conversation (add message, etc.)."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Add message if provided
    if data.message:
        message = data.message.copy()
        message['timestamp'] = datetime.now().isoformat()
        conversation['messages'].append(message)
        conversation['message_count'] = len(conversation['messages'])
    
    # Update timestamp
    conversation['updated_at'] = datetime.now().isoformat()
    
    if save_conversation(conversation):
        return conversation
    else:
        raise HTTPException(status_code=500, detail="Failed to save conversation")


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if delete_conversation_file(conversation_id):
        return {"success": True, "message": f"Conversation '{conversation['name']}' deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.post("/{conversation_id}/branch")
async def branch_conversation(conversation_id: str, data: ConversationBranch):
    """Create a new conversation branching from a specific message."""
    parent_conversation = load_conversation(conversation_id)
    
    if not parent_conversation:
        raise HTTPException(status_code=404, detail="Parent conversation not found")
    
    if data.message_index < 0 or data.message_index >= len(parent_conversation['messages']):
        raise HTTPException(status_code=400, detail="Invalid message_index")
    
    # Create new conversation with messages up to branch point
    branch_name = data.name or f"Branch from {parent_conversation['name']}"
    new_conversation = create_new_conversation(branch_name)
    new_conversation['parent_id'] = conversation_id
    new_conversation['branch_point'] = data.message_index
    new_conversation['messages'] = parent_conversation['messages'][:data.message_index + 1]
    new_conversation['message_count'] = len(new_conversation['messages'])
    
    if save_conversation(new_conversation):
        return {"success": True, "branch_id": new_conversation['id'], "conversation": new_conversation}
    else:
        raise HTTPException(status_code=500, detail="Failed to save branch")


@router.post("/{conversation_id}/search")
async def search_conversation(conversation_id: str, data: ConversationSearch):
    """Search within a specific conversation."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    query = data.query.lower()
    
    # Search through messages
    results = []
    for idx, message in enumerate(conversation['messages']):
        content = ""
        role = ""
        
        # Handle different message formats
        if 'question' in message:
            content = message['question']
            role = "user"
        elif 'answer' in message:
            content = message['answer']
            role = "assistant"
        elif 'content' in message:
            content = message['content']
            role = message.get('role', 'unknown')
        
        if query in content.lower():
            # Get context (50 chars before and after match)
            match_pos = content.lower().find(query)
            start = max(0, match_pos - 50)
            end = min(len(content), match_pos + len(query) + 50)
            preview = content[start:end]
            
            results.append({
                "message_index": idx,
                "role": role,
                "match_preview": f"...{preview}...",
                "timestamp": message.get('timestamp')
            })
    
    return results


@router.get("/{conversation_id}/export/{format}")
async def export_conversation(conversation_id: str, format: str):
    """Export conversation in various formats (json, txt)."""
    conversation = load_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if format == 'json':
        # Export as JSON
        json_data = json.dumps(conversation, indent=2, ensure_ascii=False)
        buffer = BytesIO(json_data.encode('utf-8'))
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type='application/json',
            headers={"Content-Disposition": f"attachment; filename={conversation['name']}.json"}
        )
    
    elif format == 'txt':
        # Export as formatted text
        lines = [
            f"Conversation: {conversation['name']}",
            f"Created: {conversation['created_at']}",
            f"Messages: {conversation['message_count']}",
            "=" * 80,
            ""
        ]
        
        for idx, msg in enumerate(conversation['messages'], 1):
            lines.append(f"--- Message {idx} ---")
            if 'question' in msg:
                lines.append(f"Q: {msg['question']}")
            if 'answer' in msg:
                lines.append(f"A: {msg['answer']}")
            if 'content' in msg:
                role = msg.get('role', 'unknown')
                lines.append(f"{role.upper()}: {msg['content']}")
            lines.append("")
        
        txt_data = "\n".join(lines)
        buffer = BytesIO(txt_data.encode('utf-8'))
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type='text/plain',
            headers={"Content-Disposition": f"attachment; filename={conversation['name']}.txt"}
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use 'json' or 'txt'")


@router.post("/search")
async def search_all_conversations(data: ConversationSearch):
    """Search across all conversations."""
    query = data.query.lower()
    results = []
    
    for conv_file in CONVERSATIONS_DIR.glob("*.json"):
        try:
            with open(conv_file, 'r', encoding='utf-8') as f:
                conversation = json.load(f)
            
            # Search conversation name
            name_match = query in conversation['name'].lower()
            
            # Search messages
            message_matches = []
            for idx, message in enumerate(conversation['messages']):
                content = ""
                if 'question' in message:
                    content += message['question']
                if 'answer' in message:
                    content += " " + message['answer']
                if 'content' in message:
                    content += message['content']
                
                if query in content.lower():
                    message_matches.append(idx)
            
            if name_match or message_matches:
                results.append({
                    "conversation_id": conversation['id'],
                    "conversation_name": conversation['name'],
                    "name_match": name_match,
                    "message_matches": message_matches,
                    "match_count": len(message_matches)
                })
        
        except Exception as e:
            print(f"Error searching conversation {conv_file}: {e}")
            continue
    
    return {
        "query": query,
        "results": results,
        "conversations_found": len(results)
    }