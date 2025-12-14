/**
 * Conversation Management System - Frontend
 * Integrates with existing FastAPI backend for conversation features
 */

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

// let currentConversationId = null;
// let currentConversationName = null;
let conversationMessages = [];
let allConversations = [];

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Conversation manager initialized');
    
    // Initialize conversation UI
    initializeConversationUI();
    
    // Load conversation list on startup
    loadConversationList();
});

function initializeConversationUI() {
    // Get conversation controls
    const newConvBtn = document.getElementById('newConversationBtn');
    const loadConvBtn = document.getElementById('loadConversationBtn');
    const renameConvBtn = document.getElementById('renameConversationBtn');
    const searchConvBtn = document.getElementById('searchConversationBtn');
    const exportConvBtn = document.getElementById('exportConversationBtn');
    
    // Add event listeners
    if (newConvBtn) {
        newConvBtn.addEventListener('click', createNewConversation);
    }
    
    if (loadConvBtn) {
        loadConvBtn.addEventListener('click', showConversationListModal);
    }
    
    if (renameConvBtn) {
        renameConvBtn.addEventListener('click', renameCurrentConversation);
    }
    
    if (searchConvBtn) {
        searchConvBtn.addEventListener('click', searchInConversation);
    }
    
    if (exportConvBtn) {
        exportConvBtn.addEventListener('click', showExportModal);
    }
    
    console.log('✅ Conversation UI initialized');
}

// ============================================================================
// CONVERSATION OPERATIONS
// ============================================================================

/**
 * Create a new conversation
 */
async function createNewConversation() {
    const name = prompt('Enter conversation name (optional):');
    
    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: '', // Empty query to initialize
                create_conversation: true,
                conversation_name: name || undefined
            })
        });
        
        const data = await response.json();
        
        if (data.conversation_id) {
            window.currentConversationId = data.conversation_id;
            await loadConversation(window.currentConversationId);
            showNotification('✅ New conversation created', 'success');
        }
    } catch (error) {
        console.error('Error creating conversation:', error);
        showNotification('❌ Failed to create conversation', 'error');
    }
}

/**
 * Load conversation list
 */
async function loadConversationList() {
    try {
        const response = await fetch('/api/conversations/list');
        const data = await response.json();
        
        allConversations = data;
        console.log(`📚 Loaded ${allConversations.length} conversations`);
        
    } catch (error) {
        console.error('Error loading conversations:', error);
    }
}

/**
 * Load a specific conversation
 */
async function loadConversation(conversationId) {
    try {
        const response = await fetch(`/api/conversation/${conversationId}`);
        const data = await response.json();
        
        if (data) {
            window.currentConversationId = conversationId;
            window.currentConversationName = data.name || 'Unnamed Conversation';
            conversationMessages = data.messages || [];
            
            updateConversationHeader();
            displayConversationHistory();
            
            showNotification(`📂 Loaded: ${window.currentConversationName}`, 'info');
        }
    } catch (error) {
        console.error('Error loading conversation:', error);
        showNotification('❌ Failed to load conversation', 'error');
    }
}

/**
 * Rename current conversation
 */
async function renameCurrentConversation() {
    if (!window.currentConversationId) {
        showNotification('⚠️ No active conversation', 'warning');
        return;
    }
    
    const newName = prompt('Enter new name:', window.currentConversationName);
    
    if (!newName || newName === window.currentConversationName) {
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${window.currentConversationId}/rename`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: newName })
        });
        
        const data = await response.json();
        
        if (data.new_name) {
            window.currentConversationName = newName;
            updateConversationHeader();
            showNotification(`✅ Renamed to: ${newName}`, 'success');
        }
    } catch (error) {
        console.error('Error renaming conversation:', error);
        showNotification('❌ Failed to rename', 'error');
    }
}

/**
 * Delete current conversation
 */
async function deleteCurrentConversation() {
    if (!window.currentConversationId) {
        showNotification('⚠️ No active conversation', 'warning');
        return;
    }
    
    if (!confirm(`Delete "${window.currentConversationName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${window.currentConversationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('✅ Conversation deleted', 'success');
            
            // Reset state
            window.currentConversationId = null;
            window.currentConversationName = null;
            conversationMessages = [];
            
            updateConversationHeader();
            clearResults();
            
            // Create new conversation
            await createNewConversation();
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        showNotification('❌ Failed to delete', 'error');
    }
}

// ============================================================================
// CONVERSATION BRANCHING
// ============================================================================

/**
 * Branch conversation at specific message index
 */
async function branchConversation(messageIndex, branchName) {
    if (!window.currentConversationId) {
        showNotification('⚠️ No active conversation', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${window.currentConversationId}/branch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                branch_point: messageIndex,
                name: branchName
            })
        });
        
        const data = await response.json();
        
        if (data.branch_id) {
            showNotification(`✅ Branch created: ${branchName}`, 'success');
            
            // Load the new branch
            await loadConversation(data.branch_id);
        }
    } catch (error) {
        console.error('Error branching conversation:', error);
        showNotification('❌ Failed to create branch', 'error');
    }
}

/**
 * Prompt user to branch at specific message
 */
function promptBranch(messageIndex) {
    const branchName = prompt('Enter branch name (optional):') || `Branch from ${window.currentConversationName}`;
    branchConversation(messageIndex, branchName);
}

// ============================================================================
// SEARCH IN CONVERSATION
// ============================================================================

/**
 * Search within current conversation
 */
async function searchInConversation() {
    if (!window.currentConversationId) {
        showNotification('⚠️ No active conversation', 'warning');
        return;
    }
    
    const query = prompt('Search in conversation:');
    
    if (!query) {
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${window.currentConversationId}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });
        
        const results = await response.json();
        
        displaySearchResults(results, query);
        
    } catch (error) {
        console.error('Error searching conversation:', error);
        showNotification('❌ Search failed', 'error');
    }
}

/**
 * Display search results in modal
 */
function displaySearchResults(results, query) {
    if (!results || results.length === 0) {
        showNotification('No results found', 'info');
        return;
    }
    
    const modal = createModal('searchResultsModal', `🔍 Search Results for "${query}"`);
    
    let html = `<p class="mb-4">Found ${results.length} matches</p>`;
    html += `<div class="search-results-list">`;
    
    results.forEach((result, idx) => {
        const roleIcon = result.role === 'user' ? '👤' : '🤖';
        html += `
            <div class="search-result-item" onclick="scrollToMessage(${result.message_index})">
                <div class="search-result-header">
                    ${roleIcon} Message #${result.message_index + 1}
                </div>
                <div class="search-result-preview">
                    ${highlightText(result.match_preview, query)}
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    
    showModal(modal, html);
}

// ============================================================================
// EXPORT CONVERSATION
// ============================================================================

/**
 * Show export modal
 */
function showExportModal() {
    if (!window.currentConversationId) {
        showNotification('⚠️ No active conversation', 'warning');
        return;
    }
    
    const modal = createModal('exportModal', '📤 Export Conversation');
    
    const html = `
        <p class="mb-4">Export "${window.currentConversationName}" as:</p>
        <div class="export-options">
            <button onclick="exportConversation('json')" class="btn btn-primary">
                📄 JSON
            </button>
            <button onclick="exportConversation('txt')" class="btn btn-secondary">
                📝 Text
            </button>
        </div>
    `;
    
    showModal(modal, html);
}

/**
 * Export conversation in specified format
 */
async function exportConversation(format) {
    if (!window.currentConversationId) {
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${window.currentConversationId}/export/${format}`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${window.currentConversationName}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification(`✅ Exported as ${format.toUpperCase()}`, 'success');
            closeModal('exportModal');
        }
    } catch (error) {
        console.error('Error exporting conversation:', error);
        showNotification('❌ Export failed', 'error');
    }
}

// ============================================================================
// CONVERSATION LIST MODAL
// ============================================================================

/**
 * Show conversation list modal
 */
async function showConversationListModal() {
    // Reload list
    await loadConversationList();
    
    const modal = createModal('conversationListModal', '📚 Your Conversations');
    
    let html = '';
    
    if (allConversations.length === 0) {
        html = '<p class="text-center text-gray-500">No conversations yet</p>';
    } else {
        html = '<div class="conversation-list">';
        
        allConversations.forEach(conv => {
            const isActive = conv.conversation_id === window.currentConversationId;
            const date = new Date(conv.updated_at).toLocaleDateString();
            const branchIcon = conv.is_branch ? '🔀 ' : '';
            
            html += `
                <div class="conversation-item ${isActive ? 'active' : ''}" 
                     onclick="loadConversationFromList('${conv.conversation_id}')">
                    <div class="conversation-info">
                        <div class="conversation-name">${branchIcon}${conv.name}</div>
                        <div class="conversation-meta">
                            ${conv.message_count} messages • ${date}
                        </div>
                    </div>
                    <div class="conversation-actions">
                        <button onclick="event.stopPropagation(); deleteConversationById('${conv.conversation_id}')" 
                                title="Delete">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    }
    
    showModal(modal, html);
}

/**
 * Load conversation from list and close modal
 */
async function loadConversationFromList(conversationId) {
    closeModal('conversationListModal');
    await loadConversation(conversationId);
}

/**
 * Delete conversation by ID
 */
async function deleteConversationById(conversationId) {
    if (!confirm('Delete this conversation?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/conversation/${conversationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('✅ Conversation deleted', 'success');
            
            if (conversationId === window.currentConversationId) {
                window.currentConversationId = null;
                window.currentConversationName = null;
                conversationMessages = [];
                updateConversationHeader();
                clearResults();
            }
            
            // Refresh list
            closeModal('conversationListModal');
            showConversationListModal();
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        showNotification('❌ Failed to delete', 'error');
    }
}

// ============================================================================
// UI HELPER FUNCTIONS
// ============================================================================

/**
 * Update conversation header display
 */
function updateConversationHeader() {
    const header = document.getElementById('conversationHeader');
    const messageCount = document.getElementById('messageCount');
    
    if (header) {
        header.textContent = window.currentConversationName || 'No Conversation';
    }
    
    if (messageCount) {
        messageCount.textContent = `${conversationMessages.length} messages`;
    }
}

/**
 * Display conversation history
 */
function displayConversationHistory() {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;
    
    resultsDiv.innerHTML = '';
    
    conversationMessages.forEach((msg, idx) => {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-pair';
        messageDiv.dataset.messageIndex = idx;
        
        const role = msg.role;
        const content = msg.content;
        const timestamp = new Date(msg.timestamp).toLocaleString();
        
        messageDiv.innerHTML = `
            <div class="${role}-message">
                <strong>${role === 'user' ? 'You' : 'Assistant'}:</strong>
                <div class="message-content">${content}</div>
                <div class="message-timestamp">${timestamp}</div>
            </div>
            <button class="branch-btn" onclick="promptBranch(${idx})" title="Branch from here">
                🔀 Branch
            </button>
        `;
        
        resultsDiv.appendChild(messageDiv);
    });
}

/**
 * Clear results display
 */
function clearResults() {
    const resultsDiv = document.getElementById('results');
    if (resultsDiv) {
        resultsDiv.innerHTML = '';
    }
}

/**
 * Scroll to specific message
 */
function scrollToMessage(messageIndex) {
    closeModal('searchResultsModal');
    
    const messageElements = document.querySelectorAll('.message-pair');
    if (messageElements[messageIndex]) {
        messageElements[messageIndex].scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
        });
        
        // Highlight briefly
        messageElements[messageIndex].classList.add('highlight');
        setTimeout(() => {
            messageElements[messageIndex].classList.remove('highlight');
        }, 2000);
    }
}

/**
 * Highlight text with query
 */
function highlightText(text, query) {
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

// ============================================================================
// MODAL SYSTEM
// ============================================================================

/**
 * Create modal element
 */
function createModal(id, title) {
    // Remove existing modal if present
    const existing = document.getElementById(id);
    if (existing) {
        existing.remove();
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = id;
    
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close" onclick="closeModal('${id}')">&times;</button>
            </div>
            <div class="modal-body" id="${id}-body">
                <!-- Content will be inserted here -->
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    return modal;
}

/**
 * Show modal with content
 */
function showModal(modal, htmlContent) {
    const body = modal.querySelector('.modal-body');
    if (body) {
        body.innerHTML = htmlContent;
    }
    
    modal.classList.add('active');
    
    // Close on outside click
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

/**
 * Close modal
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

// ============================================================================
// NOTIFICATION SYSTEM
// ============================================================================

/**
 * Show toast notification
 */
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================================
// EXPORT FOR GLOBAL ACCESS
// ============================================================================

window.ConversationManager = {
    createNew: createNewConversation,
    load: loadConversation,
    rename: renameCurrentConversation,
    deleteCurrent: deleteCurrentConversation,
    branch: branchConversation,
    search: searchInConversation,
    export: exportConversation,
    getCurrentId: () => window.currentConversationId
};

console.log('✅ Conversation manager loaded');