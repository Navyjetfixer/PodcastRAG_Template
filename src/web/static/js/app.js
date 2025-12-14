/**
 * Data Over Dogma - Complete Frontend Application
 * WITH DEBUGGING FOR CONVERSATION BUTTONS
 */

// ============================================================================
// GLOBAL STATE
// ============================================================================

let currentConversationId = null;
let currentConversationName = null;
let messageCount = 0;
let availableEpisodes = [];
let availableBooks = [];
let selectedEpisodes = [];
let selectedBooks = [];

// Pagination state
let currentResults = [];
let displayedCount = 0;
const RESULTS_PER_PAGE = 5;

// Search suggestions for autocomplete
const searchSuggestions = [
    'grace', 'faith', 'salvation', 'justification', 'sanctification',
    'atonement', 'redemption', 'covenant', 'eschatology', 'soteriology',
    'predestination', 'election', 'free will', 'trinity', 'incarnation',
    'baptism', 'communion', 'prayer', 'worship', 'holy spirit',
    'sin', 'repentance', 'forgiveness', 'love', 'mercy',
    'judgment', 'heaven', 'hell', 'resurrection', 'second coming',
    'Genesis', 'Exodus', 'Psalms', 'Proverbs', 'Isaiah',
    'Matthew', 'John', 'Acts', 'Romans', 'Corinthians',
    'Galatians', 'Ephesians', 'Philippians', 'Hebrews', 'Revelation',
    'What is grace?', 'What is faith?', 'What is salvation?',
    'How to be saved?', 'What does the Bible say about?',
    'Is there slavery in the Bible?', 'What is the gospel?',
    'Who is Jesus?', 'What is sin?', 'What is love?'
];

// ============================================================================
// SIDEBAR MANAGEMENT
// ============================================================================

function initializeSidebar() {
    const toggleBtn = document.getElementById('conversationSidebarToggle');
    const sidebar = document.getElementById('conversationSidebar');
    const closeBtn = document.getElementById('closeSidebarBtn');
    const overlay = document.getElementById('sidebarOverlay');
    
    console.log('🔧 Initializing sidebar...');
    console.log('  Toggle button:', toggleBtn);
    console.log('  Sidebar:', sidebar);
    console.log('  Close button:', closeBtn);
    console.log('  Overlay:', overlay);
    
    if (!toggleBtn || !sidebar || !overlay) {
        console.error('❌ Sidebar elements missing!');
        return;
    }
    
    toggleBtn.addEventListener('click', () => {
        console.log('✅ Sidebar toggle clicked!');
        sidebar.classList.add('active');
        overlay.classList.add('active');
    });
    
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            console.log('✅ Sidebar close clicked!');
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        });
    }
    
    overlay.addEventListener('click', () => {
        console.log('✅ Overlay clicked!');
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
    });
    
    console.log('✅ Sidebar initialized successfully');
}



// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Data Over Dogma app...');
    
    initializeSidebar();
    setupConversationControls(); // ← SEPARATE FUNCTION
    loadEpisodes();
    loadBooks();
    setupEventListeners();
    updateWordDisplay();
    initBackToSearchButton();
    loadConversationName();
    
    console.log('✅ App initialized');
});

function updateConversationUI() {
    const sidebarCount = document.getElementById('sidebarMessageCount');
    const conversationHeader = document.getElementById('conversationHeader');
    const messageCountEl = document.getElementById('messageCount');
    
    if (sidebarCount) {
        sidebarCount.textContent = messageCount;
    }
    
    if (conversationHeader) {
        if (currentConversationName) {
            conversationHeader.textContent = currentConversationName;
        } else if (currentConversationId) {
            conversationHeader.textContent = `Conversation ${currentConversationId.slice(0, 8)}...`;
        } else {
            conversationHeader.textContent = 'No conversation';
        }
    }
    
    if (messageCountEl) {
        messageCountEl.textContent = `${messageCount} messages`;
    }
}

function addMessageToHistory(role, content) {
    const historyDiv = document.getElementById('conversationHistory');
    if (!historyDiv) return;
    
    // Remove "no messages" text
    const noMessages = historyDiv.querySelector('.no-messages');
    if (noMessages) {
        noMessages.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message-item ${role}-message`;
    
    const timestamp = new Date().toLocaleTimeString();
    
    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="message-role">${role === 'user' ? '👤 You' : '🤖 AI'}</span>
            <span class="message-time">${timestamp}</span>
        </div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;
    
    historyDiv.appendChild(messageDiv);
    historyDiv.scrollTop = historyDiv.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// CONVERSATION CONTROLS (NEW/LOAD/RENAME/EXPORT)
// ============================================================================

function newConversation() {
    console.log('🆕 newConversation() called');
    
    if (currentConversationId && messageCount > 0) {
        if (!confirm('Start a new conversation? Current conversation will be cleared.')) {
            return;
        }
    }
    
    // Reset state
    currentConversationId = null;
    currentConversationName = null;
    messageCount = 0;
    
    // Clear UI
    const historyDiv = document.getElementById('conversationHistory');
    if (historyDiv) {
        historyDiv.innerHTML = '<p class="no-messages">No messages yet</p>';
    }
    
    // Clear panels
    const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
    const answerPanel = document.getElementById('answerPanel');
    const searchResults = document.getElementById('searchResults');
    
    if (rewrittenPanel) rewrittenPanel.style.display = 'none';
    if (answerPanel) answerPanel.style.display = 'none';
    if (searchResults) searchResults.innerHTML = '';
    
    // Clear input
    const queryInput = document.getElementById('queryInput');
    if (queryInput) queryInput.value = '';
    
    updateConversationUI();
    
    // Close sidebar
    const sidebar = document.getElementById('conversationSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.remove('active');
    if (overlay) overlay.classList.remove('active');
    
    alert('✅ New conversation started!');
    console.log('✅ New conversation started');
}

function loadConversation() {
    console.log('📂 loadConversation() called');
    
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
            const text = await file.text();
            const data = JSON.parse(text);
            
            // Validate structure
            if (!data.conversation_id || !Array.isArray(data.messages)) {
                throw new Error('Invalid conversation file format');
            }
            
            // Restore state
            currentConversationId = data.conversation_id;
            currentConversationName = data.conversation_name || null;
            messageCount = data.messages.length;
            
            // Restore message history UI
            const historyDiv = document.getElementById('conversationHistory');
            if (historyDiv) {
                historyDiv.innerHTML = '';
                
                data.messages.forEach(msg => {
                    addMessageToHistory(msg.role, msg.content);
                });
            }
            
            // Save name to localStorage if present
            if (currentConversationName) {
                saveConversationName();
            }
            
            updateConversationUI();
            
            // Close sidebar
            const sidebar = document.getElementById('conversationSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if (sidebar) sidebar.classList.remove('active');
            if (overlay) overlay.classList.remove('active');
            
            console.log('✅ Conversation loaded:', currentConversationId);
            alert('✅ Conversation loaded successfully!');
            
        } catch (error) {
            console.error('❌ Failed to load conversation:', error);
            alert('❌ Failed to load conversation file. Please check the file format.');
        }
    };
    
    input.click();
}

function renameConversation() {
    console.log('✏️ renameConversation() called');
    
    if (!currentConversationId) {
        alert('No active conversation to rename');
        return;
    }
    
    const currentName = currentConversationName || `Conversation ${currentConversationId.slice(0, 8)}`;
    const newName = prompt('Enter new conversation name:', currentName);
    
    if (!newName || newName.trim() === '') {
        return;
    }
    
    currentConversationName = newName.trim();
    saveConversationName();
    updateConversationUI();
    
    alert(`✅ Conversation renamed to: ${currentConversationName}`);
    console.log('✅ Conversation renamed to:', currentConversationName);
}

function exportConversation() {
    console.log('📤 exportConversation() called');
    
    if (!currentConversationId) {
        alert('No conversation to export');
        return;
    }
    
    // Collect messages from UI
    const historyDiv = document.getElementById('conversationHistory');
    const messages = [];
    
    if (historyDiv) {
        historyDiv.querySelectorAll('.message-item').forEach(msg => {
            const role = msg.classList.contains('user-message') ? 'user' : 'assistant';
            const contentEl = msg.querySelector('.message-content');
            const content = contentEl ? contentEl.textContent : '';
            messages.push({ role, content });
        });
    }
    
    // Create export data
    const exportData = {
        conversation_id: currentConversationId,
        conversation_name: currentConversationName,
        message_count: messageCount,
        messages: messages,
        exported_at: new Date().toISOString(),
        app_version: '1.0'
    };
    
    // Create download
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    const filename = currentConversationName 
        ? `${sanitizeFilename(currentConversationName)}_${Date.now()}.json`
        : `conversation_${currentConversationId.slice(0, 8)}_${Date.now()}.json`;
    
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    
    alert(`✅ Conversation exported as: ${filename}`);
    console.log('✅ Conversation exported:', filename);
}

function sanitizeFilename(name) {
    return name.replace(/[^a-z0-9]/gi, '_').toLowerCase();
}

function saveConversationName() {
    if (currentConversationId && currentConversationName) {
        localStorage.setItem(`conversation_name_${currentConversationId}`, currentConversationName);
    }
}

function loadConversationName() {
    if (currentConversationId) {
        const saved = localStorage.getItem(`conversation_name_${currentConversationId}`);
        if (saved) {
            currentConversationName = saved;
            updateConversationUI();
        }
    }
}

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    const hasVerses = document.getElementById('hasVerses');
    const queryInput = document.getElementById('queryInput');
    const searchSection = document.querySelector('.search-section');
    
    // Range sliders
    if (minWords) minWords.addEventListener('input', updateWordDisplay);
    if (maxWords) maxWords.addEventListener('input', updateWordDisplay);
    if (hasVerses) hasVerses.addEventListener('change', updateActiveFilters);
    
    // Autocomplete
    if (queryInput) {
        const parent = queryInput.parentElement;
        if (parent && !parent.style.position) {
            parent.style.position = 'relative';
        }
        
        queryInput.addEventListener('input', (e) => {
            const value = e.target.value.trim();
            showAutocomplete(value);
        });
        
        queryInput.addEventListener('blur', () => {
            setTimeout(hideAutocomplete, 200);
        });
        
        queryInput.addEventListener('focus', (e) => {
            const value = e.target.value.trim();
            if (value) showAutocomplete(value);
        });
    
        queryInput.addEventListener('keydown', (e) => {
            const dropdown = document.getElementById('autocompleteDropdown');
            if (!dropdown || dropdown.style.display === 'none') return;
            
            const items = dropdown.querySelectorAll('.autocomplete-item');
            if (items.length === 0) return;
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                items[0].focus();
            }
            if (e.key === 'Escape') {
                hideAutocomplete();
            }
        });
    }
    
    // Sticky header on scroll
    if (searchSection) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 10) {
                searchSection.classList.add('scrolled');
            } else {
                searchSection.classList.remove('scrolled');
            }
        });
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.multiselect')) {
            document.querySelectorAll('.multiselect-dropdown').forEach(d => {
                d.classList.remove('open');
            });
        }
        if (!e.target.closest('#queryInput') && !e.target.closest('#autocompleteDropdown')) {
            hideAutocomplete();
        }
    });
}

// ============================================================================
// CONVERSATION CONTROLS - SETUP WITH DEBUGGING
// ============================================================================

function setupConversationControls() {
    console.log('🔧 Setting up conversation controls...');
    
    const newConvBtn = document.getElementById('newConversationBtn');
    const loadConvBtn = document.getElementById('loadConversationBtn');
    const renameConvBtn = document.getElementById('renameConversationBtn');
    const exportConvBtn = document.getElementById('exportConversationBtn');
    
    console.log('  New button:', newConvBtn);
    console.log('  Load button:', loadConvBtn);
    console.log('  Rename button:', renameConvBtn);
    console.log('  Export button:', exportConvBtn);
    
    if (newConvBtn) {
        newConvBtn.addEventListener('click', () => {
            console.log('🆕 NEW BUTTON CLICKED!');
            newConversation();
        });
        console.log('  ✅ New button listener added');
    } else {
        console.error('  ❌ New button NOT FOUND');
    }
    
    if (loadConvBtn) {
        loadConvBtn.addEventListener('click', () => {
            console.log('📂 LOAD BUTTON CLICKED!');
            loadConversation();
        });
        console.log('  ✅ Load button listener added');
    } else {
        console.error('  ❌ Load button NOT FOUND');
    }
    
    if (renameConvBtn) {
        renameConvBtn.addEventListener('click', () => {
            console.log('✏️ RENAME BUTTON CLICKED!');
            renameConversation();
        });
        console.log('  ✅ Rename button listener added');
    } else {
        console.error('  ❌ Rename button NOT FOUND');
    }
    
    if (exportConvBtn) {
        exportConvBtn.addEventListener('click', () => {
            console.log('📤 EXPORT BUTTON CLICKED!');
            exportConversation();
        });
        console.log('  ✅ Export button listener added');
    } else {
        console.error('  ❌ Export button NOT FOUND');
    }
    
    console.log('✅ Conversation controls setup complete');
}

// Expose functions globally
window.toggleDropdown = toggleDropdown;
window.filterOptions = filterOptions;
window.selectAllEpisodes = selectAllEpisodes;
window.selectAllBooks = selectAllBooks;
window.updateEpisodeSelection = updateEpisodeSelection;
window.updateBookSelection = updateBookSelection;
window.resetFilters = resetFilters;
window.performSearch = performSearch;
window.askAI = askAI;
window.clearHistory = clearHistory;
window.loadMoreResults = loadMoreResults;
window.selectSuggestion = selectSuggestion;

// ============================================================================
// DATA LOADING
// ============================================================================

async function loadEpisodes() {
    try {
        const response = await fetch('/api/episodes/list');
        const episodes = await response.json();
        
        availableEpisodes = episodes;
        const optionsContainer = document.getElementById('episodeOptions');
        if (!optionsContainer) return;
        
        episodes.forEach(ep => {
            const option = document.createElement('div');
            option.className = 'multiselect-option';
            option.innerHTML = `
                <input type="checkbox" id="ep-${ep.episode_id}" value="${ep.episode_id}" 
                       onchange="window.updateEpisodeSelection()">
                <label for="ep-${ep.episode_id}">${ep.title}</label>
            `;
            optionsContainer.appendChild(option);
        });
        
        console.log(`✅ Loaded ${episodes.length} episodes`);
        
    } catch (error) {
        console.error('❌ Failed to load episodes:', error);
    }
}

async function loadBooks() {
    try {
        const response = await fetch('/api/verses/books');
        
        if (!response.ok) {
            console.warn('⚠️ Bible books endpoint returned error:', response.status);
            const bookFilter = document.querySelector('.filter-group:has(#bookDropdown)');
            if (bookFilter) bookFilter.style.display = 'none';
            return;
        }
        
        const data = await response.json();
        
        availableBooks = data.books || [];
        const bookOptions = document.getElementById('bookOptions');
        if (!bookOptions) return;
        
        // Keep the "All Books" option
        const existingOptions = bookOptions.querySelectorAll('.multiselect-option');
        if (existingOptions.length > 1) {
            // Clear all except first (All Books)
            Array.from(existingOptions).slice(1).forEach(opt => opt.remove());
        }
        
        data.books.forEach(book => {
            const option = document.createElement('div');
            option.className = 'multiselect-option';
            option.innerHTML = `
                <input type="checkbox" id="book-${book}" value="${book}" 
                       onchange="window.updateBookSelection()">
                <label for="book-${book}">${book}</label>
            `;
            bookOptions.appendChild(option);
        });
        
        console.log(`✅ Loaded ${data.books.length} Bible books`);
        
    } catch (error) {
        console.error('❌ Failed to load Bible books:', error);
        const bookFilter = document.querySelector('.filter-group:has(#bookDropdown)');
        if (bookFilter) bookFilter.style.display = 'none';
    }
}

// ============================================================================
// AUTOCOMPLETE
// ============================================================================

function showAutocomplete(inputValue) {
    if (!inputValue || inputValue.length < 2) {
        hideAutocomplete();
        return;
    }
    
    const queryInput = document.getElementById('queryInput');
    if (!queryInput) return;
    
    const matches = searchSuggestions.filter(suggestion =>
        suggestion.toLowerCase().includes(inputValue.toLowerCase())
    ).slice(0, 8);
    
    if (matches.length === 0) {
        hideAutocomplete();
        return;
    }
    
    let dropdown = document.getElementById('autocompleteDropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'autocompleteDropdown';
        dropdown.className = 'autocomplete-dropdown';
        queryInput.parentElement.appendChild(dropdown);
        
        dropdown.addEventListener('click', (e) => {
            const item = e.target.closest('.autocomplete-item');
            if (item) {
                const suggestion = item.dataset.suggestion;
                selectSuggestion(suggestion);
            }
        });
    }
    
    dropdown.innerHTML = matches.map(suggestion => {
        const escapedSuggestion = suggestion.replace(/"/g, '&quot;');
        return `<div class="autocomplete-item" data-suggestion="${escapedSuggestion}">${highlightMatch(suggestion, inputValue)}</div>`;
    }).join('');
    dropdown.style.display = 'block';
}

function highlightMatch(text, query) {
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<strong>$1</strong>');
}

function selectSuggestion(suggestion) {
    const queryInput = document.getElementById('queryInput');
    if (queryInput) {
        queryInput.value = suggestion;
        queryInput.focus();
    }
    hideAutocomplete();
}

function hideAutocomplete() {
    const dropdown = document.getElementById('autocompleteDropdown');
    if (dropdown) dropdown.style.display = 'none';
}

// ============================================================================
// MULTISELECT CONTROLS
// ============================================================================

function toggleDropdown(type) {
    const dropdown = document.getElementById(`${type}Dropdown`);
    if (!dropdown) return;
    
    dropdown.classList.toggle('open');
    
    const allDropdowns = document.querySelectorAll('.multiselect-dropdown');
    allDropdowns.forEach(d => {
        if (d !== dropdown) {
            d.classList.remove('open');
        }
    });
}

function filterOptions(type) {
    const searchInput = document.getElementById(`${type}Search`);
    const options = document.getElementById(`${type}Options`);
    if (!searchInput || !options) return;
    
    const filter = searchInput.value.toLowerCase();
    
    Array.from(options.children).forEach((option, index) => {
        if (index === 0) return;
        const text = option.textContent.toLowerCase();
        option.style.display = text.includes(filter) ? 'flex' : 'none';
    });
}

function selectAllEpisodes() {
    const allCheckbox = document.getElementById('ep-all');
    if (!allCheckbox) return;
    
    const checkboxes = document.querySelectorAll('#episodeOptions input[type="checkbox"]:not(#ep-all)');
    const isChecked = allCheckbox.checked;
    
    checkboxes.forEach(cb => {
        cb.checked = isChecked;
    });
    
    updateEpisodeSelection();
}

function updateEpisodeSelection() {
    const allCheckbox = document.getElementById('ep-all');
    const checkboxes = Array.from(document.querySelectorAll('#episodeOptions input[type="checkbox"]:not(#ep-all)'));
    
    selectedEpisodes = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
    
    if (allCheckbox) {
        const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
        allCheckbox.checked = allChecked;
    }
    
    const display = document.getElementById('episodeDisplay');
    if (display) {
        if (selectedEpisodes.length === 0 || selectedEpisodes.length === checkboxes.length) {
            display.textContent = 'All Episodes';
        } else {
            display.textContent = `${selectedEpisodes.length} selected`;
        }
    }
    
    updateActiveFilters();
}

function selectAllBooks() {
    const allCheckbox = document.getElementById('book-all');
    if (!allCheckbox) return;
    
    const checkboxes = document.querySelectorAll('#bookOptions input[type="checkbox"]:not(#book-all)');
    const isChecked = allCheckbox.checked;
    
    checkboxes.forEach(cb => {
        cb.checked = isChecked;
    });
    
    updateBookSelection();
}

function updateBookSelection() {
    const allCheckbox = document.getElementById('book-all');
    const checkboxes = Array.from(document.querySelectorAll('#bookOptions input[type="checkbox"]:not(#book-all)'));
    
    selectedBooks = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
    
    if (allCheckbox) {
        const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
        allCheckbox.checked = allChecked;
    }
    
    const display = document.getElementById('bookDisplay');
    if (display) {
        if (selectedBooks.length === 0 || selectedBooks.length === checkboxes.length) {
            display.textContent = 'All Books';
        } else {
            display.textContent = `${selectedBooks.length} selected`;
        }
    }
    
    updateActiveFilters();
}

// ============================================================================
// FILTER MANAGEMENT
// ============================================================================

function updateWordDisplay() {
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    const minDisplay = document.getElementById('minWordDisplay');
    const maxDisplay = document.getElementById('maxWordDisplay');
    
    if (minWords && minDisplay) {
        minDisplay.textContent = minWords.value;
    }
    if (maxWords && maxDisplay) {
        maxDisplay.textContent = maxWords.value;
    }
    
    updateActiveFilters();
}

function updateActiveFilters() {
    const filters = [];
    
    if (selectedEpisodes.length > 0 && selectedEpisodes.length < availableEpisodes.length) {
        filters.push(`${selectedEpisodes.length} episodes`);
    }
    
    if (selectedBooks.length > 0 && selectedBooks.length < availableBooks.length) {
        filters.push(`${selectedBooks.length} books`);
    }
    
    const hasVerses = document.getElementById('hasVerses');
    if (hasVerses && hasVerses.checked) {
        filters.push('with verses only');
    }
    
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    if (minWords && maxWords) {
        const minVal = parseInt(minWords.value);
        const maxVal = parseInt(maxWords.value);
        if (minVal > 0 || maxVal < 5000) {
            filters.push(`${minVal}-${maxVal} words`);
        }
    }
    
    const panel = document.getElementById('activeFilters');
    const text = document.getElementById('activeFiltersText');
    
    if (panel && text) {
        if (filters.length > 0) {
            text.innerHTML = filters.map(f => `<span class="filter-badge">${f}</span>`).join('');
            panel.style.display = 'block';
        } else {
            panel.style.display = 'none';
        }
    }
}

function resetFilters() {
    const epAll = document.getElementById('ep-all');
    if (epAll) {
        epAll.checked = true;
        const checkboxes = document.querySelectorAll('#episodeOptions input[type="checkbox"]:not(#ep-all)');
        checkboxes.forEach(cb => cb.checked = false);
        selectedEpisodes = [];
        const epDisplay = document.getElementById('episodeDisplay');
        if (epDisplay) epDisplay.textContent = 'All Episodes';
    }
    
    const bookAll = document.getElementById('book-all');
    if (bookAll) {
        bookAll.checked = true;
        const checkboxes = document.querySelectorAll('#bookOptions input[type="checkbox"]:not(#book-all)');
        checkboxes.forEach(cb => cb.checked = false);
        selectedBooks = [];
        const bookDisplay = document.getElementById('bookDisplay');
        if (bookDisplay) bookDisplay.textContent = 'All Books';
    }
    
    const hasVerses = document.getElementById('hasVerses');
    if (hasVerses) hasVerses.checked = false;
    
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    if (minWords) minWords.value = 0;
    if (maxWords) maxWords.value = 5000;
    
    const minScore = document.getElementById('minScore');
    if (minScore) minScore.value = 0.0;
    
    const queryRewriting = document.getElementById('queryRewriting');
    const useContext = document.getElementById('useContext');
    if (queryRewriting) queryRewriting.checked = true;
    if (useContext) useContext.checked = true;
    
    updateWordDisplay();
    updateActiveFilters();
    
    console.log('✅ Filters reset');
}

function getFilters() {
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    const hasVerses = document.getElementById('hasVerses');
    const minScore = document.getElementById('minScore');
    const queryRewriting = document.getElementById('queryRewriting');
    const useContext = document.getElementById('useContext');
    
    const filters = {
        top_k: 20,
        min_score: minScore ? parseFloat(minScore.value) : 0.0,
        use_rewrite: queryRewriting ? queryRewriting.checked : true,
        use_context: useContext ? useContext.checked : true
    };
    
    if (currentConversationId) {
        filters.conversation_id = currentConversationId;
    }
    
    if (selectedEpisodes.length > 0) {
        filters.episodes = selectedEpisodes;
    }
    
    if (hasVerses && hasVerses.checked) {
        filters.has_verses = true;
    }
    
    if (selectedBooks.length > 0) {
        filters.books = selectedBooks;
    }
    
    if (minWords && parseInt(minWords.value) > 0) {
        filters.min_word_count = parseInt(minWords.value);
    }
    
    if (maxWords && parseInt(maxWords.value) < 5000) {
        filters.max_word_count = parseInt(maxWords.value);
    }
    
    return filters;
}

// ============================================================================
// SEARCH
// ============================================================================

function highlightSearchTerms(text, query) {
    if (!query || !text) return text;
    
    const stopWords = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being'];
    const terms = query.toLowerCase()
        .split(/\s+/)
        .filter(term => term.length > 2 && !stopWords.includes(term));
    
    if (terms.length === 0) return text;
    
    const pattern = new RegExp(`\\b(${terms.join('|')})\\b`, 'gi');
    return text.replace(pattern, '<mark class="highlight">$1</mark>');
}

async function performSearch() {
    const queryInput = document.getElementById('queryInput');
    if (!queryInput) return;
    
    const query = queryInput.value.trim();
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
    const answerPanel = document.getElementById('answerPanel');
    const searchResults = document.getElementById('searchResults');
    
    if (rewrittenPanel) rewrittenPanel.style.display = 'none';
    if (answerPanel) answerPanel.style.display = 'none';
    if (searchResults) searchResults.innerHTML = '<p class="loading">🔍 Searching...</p>';
    
    showLoading();
    
    try {
        const filters = getFilters();
        
        const requestBody = {
            query: query,
            ...filters
        };
        
        Object.keys(requestBody).forEach(key => {
            if (requestBody[key] === null || requestBody[key] === undefined) {
                delete requestBody[key];
            }
        });
        
        console.log('🔍 Search request:', JSON.stringify(requestBody, null, 2));
        
        const response = await fetch('/api/query/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            console.error('❌ API Error:', data);
            throw new Error(data.detail || JSON.stringify(data));
        }
        
        // Update conversation
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
            messageCount += 1;
            loadConversationName();
            updateConversationUI();
            addMessageToHistory('user', query);
        }
        
        // Show rewritten query
        if (data.rewritten_query && data.rewritten_query !== query && rewrittenPanel) {
            const rewrittenQuery = document.getElementById('rewrittenQuery');
            if (rewrittenQuery) {
                rewrittenQuery.textContent = data.rewritten_query;
                rewrittenPanel.style.display = 'block';
            }
        }
        
        currentResults = data.results;
        displayedCount = 0;
        displayResultsPage();
        
        console.log(`✅ Found ${data.results.length} results`);
        
    } catch (error) {
        if (searchResults) {
            searchResults.innerHTML = `<p class="loading">❌ Error: ${error.message}</p>`;
        }
        console.error('❌ Search error:', error);
    } finally {
        hideLoading();
    }
}

function displayResultsPage() {
    const container = document.getElementById('searchResults');
    const countEl = document.getElementById('resultCount');
    const queryInput = document.getElementById('queryInput');
    const currentQuery = queryInput ? queryInput.value : '';
    
    if (countEl) {
        countEl.textContent = currentResults.length;
    }
    
    if (!container) return;
    
    if (currentResults.length === 0) {
        container.innerHTML = '<p class="loading">No results found</p>';
        return;
    }
    
    const endIndex = Math.min(displayedCount + RESULTS_PER_PAGE, currentResults.length);
    const resultsToShow = currentResults.slice(displayedCount, endIndex);
    
    const resultsHTML = resultsToShow.map(result => {
        const scorePercent = (result.score * 100).toFixed(1);
        const highlightedText = highlightSearchTerms(result.text, currentQuery);
        
        let versesHTML = '';
        if (result.verse_references) {
            const verses = result.verse_references.split(',').map(v => v.trim());
            versesHTML = `
                <div class="result-verses">
                    📖 ${verses.map(v => `<span class="verse-reference">${v}</span>`).join('')}
                </div>
            `;
        }
        
        let booksHTML = '';
        if (result.books_mentioned) {
            const books = result.books_mentioned.split(',').map(b => b.trim());
            booksHTML = books.map(b => `<span class="book-tag">${b}</span>`).join('');
        }

        const segmentNum = result.segment_id; // segment_id is now an integer
        
        return `
            <div class="result-card">
                <div class="result-header">
                    <h3 class="result-title">${result.episode_title}</h3>
                    <span class="result-score">${scorePercent}%</span>
                </div>
                <div class="result-meta">
                    ⏱️ ${result.start_time} - ${result.end_time} • 
                    📝 ${result.word_count} words • 
                    Segment #${segmentNum}
                </div>
                <div class="result-text">${highlightedText}</div>
                ${versesHTML}
                ${booksHTML ? `<div style="margin-top: 10px;">${booksHTML}</div>` : ''}
            </div>
        `;
    }).join('');
    
    if (displayedCount === 0) {
        container.innerHTML = resultsHTML;
    } else {
        container.innerHTML += resultsHTML;
    }
    
    displayedCount = endIndex;
    
    updateLoadMoreButton();

    setTimeout(() => {
        makeVerseReferencesClickable();
    }, 100);
}

function updateLoadMoreButton() {
    const container = document.getElementById('searchResults');
    if (!container) return;
    
    const existingBtn = document.getElementById('loadMoreBtn');
    if (existingBtn) {
        existingBtn.remove();
    }
    
    if (displayedCount < currentResults.length) {
        const remaining = currentResults.length - displayedCount;
        const button = document.createElement('div');
        button.id = 'loadMoreBtn';
        button.className = 'load-more-container';
        button.innerHTML = `
            <button onclick="loadMoreResults()" class="btn btn-secondary">
                📥 Load More Results (${remaining} remaining)
            </button>
        `;
        container.appendChild(button);
    }
}

function loadMoreResults() {
    displayResultsPage();
}

// ============================================================================
// AI Q&A
// ============================================================================

async function askAI() {
    const queryInput = document.getElementById('queryInput');
    if (!queryInput) return;
    
    const query = queryInput.value.trim();
    if (!query) {
        alert('Please enter a question');
        return;
    }
    
    const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
    const answerPanel = document.getElementById('answerPanel');
    const aiAnswer = document.getElementById('aiAnswer');
    const searchResults = document.getElementById('searchResults');
    
    if (rewrittenPanel) rewrittenPanel.style.display = 'none';
    if (answerPanel) answerPanel.style.display = 'block';
    if (aiAnswer) aiAnswer.textContent = '🤔 Thinking...';
    if (searchResults) searchResults.innerHTML = '';
    
    try {
        const filters = getFilters();
        
        const params = new URLSearchParams({
            query: query,
            top_k: filters.top_k,
            min_score: filters.min_score,
            use_rewrite: filters.use_rewrite,
            use_context: filters.use_context
        });
        
        if (selectedEpisodes.length > 0) {
            selectedEpisodes.forEach(ep => params.append('episodes', ep));
        }
        
        if (filters.has_verses) {
            params.append('has_verses', 'true');
        }
        
        if (selectedBooks.length > 0) {
            selectedBooks.forEach(book => params.append('books', book));
        }
        
        if (filters.min_word_count) {
            params.append('min_word_count', filters.min_word_count);
        }
        
        if (filters.max_word_count) {
            params.append('max_word_count', filters.max_word_count);
        }
        
        if (currentConversationId) {
            params.append('conversation_id', currentConversationId);
        }
        
        console.log('🤖 AI request params:', params.toString());
        
        const eventSource = new EventSource(`/api/query/answer?${params}`);
        
        let fullAnswer = '';
        let searchResultsData = [];
        
        eventSource.addEventListener('rewritten_query', (e) => {
            const rewrittenQuery = document.getElementById('rewrittenQuery');
            if (rewrittenQuery && rewrittenPanel) {
                rewrittenQuery.textContent = e.data;
                rewrittenPanel.style.display = 'block';
            }
        });
        
        eventSource.addEventListener('search_results', (e) => {
            const data = JSON.parse(e.data);
            searchResultsData = data.results;
        });
        
        eventSource.addEventListener('answer_chunk', (e) => {
            fullAnswer += e.data;
            if (aiAnswer) {
                aiAnswer.textContent = fullAnswer;
            }
        });
        
        eventSource.addEventListener('answer_complete', (e) => {
            const data = JSON.parse(e.data);
            
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                messageCount += 2;
                loadConversationName();
                updateConversationUI();
                addMessageToHistory('user', query);
                addMessageToHistory('assistant', fullAnswer);
            }
            
            if (searchResultsData.length > 0) {
                currentResults = searchResultsData;
                displayedCount = 0;
                displayResultsPage();
                setTimeout(() => {
                    const resultsSection = document.querySelector('.results-section');
                    if (resultsSection) {
                        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 100);
            }
            
            eventSource.close();
            console.log('✅ Answer complete');
        });
        
        eventSource.addEventListener('error', (e) => {
            if (aiAnswer) {
                aiAnswer.textContent = '❌ Error generating answer';
            }
            console.error('❌ AI streaming error:', e);
            eventSource.close();
        });
        
        eventSource.onerror = () => {
            if (aiAnswer && aiAnswer.textContent === '🤔 Thinking...') {
                aiAnswer.textContent = '❌ Connection error';
            }
            eventSource.close();
        };
        
    } catch (error) {
        if (aiAnswer) {
            aiAnswer.textContent = `❌ Error: ${error.message}`;
        }
        console.error('❌ AI error:', error);
    }
}

// ============================================================================
// CONVERSATION MANAGEMENT
// ============================================================================

function clearHistory() {
    if (!currentConversationId) {
        alert('No active conversation');
        return;
    }
    
    if (!confirm('Clear conversation history? This will reset everything.')) {
        return;
    }
    
    fetch(`/api/query/conversation/${currentConversationId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to clear conversation');
        }
        
        // Reset conversation state
        currentConversationId = null;
        currentConversationName = null;
        messageCount = 0;
        
        // Get all UI elements
        const panel = document.getElementById('conversationPanel');
        const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
        const answerPanel = document.getElementById('answerPanel');
        const searchResults = document.getElementById('searchResults');
        const queryInput = document.getElementById('queryInput');
        const resultCount = document.getElementById('resultCount');
        const aiAnswer = document.getElementById('aiAnswer');
        const rewrittenQuery = document.getElementById('rewrittenQuery');
        
        // Hide all panels
        if (panel) panel.style.display = 'none';
        if (rewrittenPanel) rewrittenPanel.style.display = 'none';
        if (answerPanel) answerPanel.style.display = 'none';
        
        // Clear all content
        if (searchResults) searchResults.innerHTML = '';
        if (queryInput) queryInput.value = '';
        if (resultCount) resultCount.textContent = '0';
        if (aiAnswer) aiAnswer.textContent = '';
        if (rewrittenQuery) rewrittenQuery.textContent = '';
        
        // Clear history UI
        const historyDiv = document.getElementById('conversationHistory');
        if (historyDiv) {
            historyDiv.innerHTML = '<p class="no-messages">No messages yet</p>';
        }
        
        // Reset pagination state
        currentResults = [];
        displayedCount = 0;
        
        updateConversationUI();
        
        console.log('✅ Everything cleared and reset');
        alert('✅ Conversation and search cleared!');
    })
    .catch(error => {
        console.error('❌ Failed to clear conversation:', error);
        alert('Failed to clear conversation');
    });
}
/* function clearHistory() {
    if (!currentConversationId) {
        alert('No active conversation');
        return;
    }
    
    if (!confirm('Clear conversation history?')) {
        return;
    }
    
    fetch(`/api/query/conversation/${currentConversationId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to clear conversation');
        }
        
        currentConversationId = null;
        currentConversationName = null;
        messageCount = 0;
        
        const panel = document.getElementById('conversationPanel');
        const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
        if (panel) panel.style.display = 'none';
        if (rewrittenPanel) rewrittenPanel.style.display = 'none';
        
        // Clear history UI
        const historyDiv = document.getElementById('conversationHistory');
        if (historyDiv) {
            historyDiv.innerHTML = '<p class="no-messages">No messages yet</p>';
        }
        
        updateConversationUI();
        
        console.log('✅ Conversation cleared');
    })
    .catch(error => {
        console.error('❌ Failed to clear conversation:', error);
        alert('Failed to clear conversation');
    });
} */

// ============================================================================
// UTILITIES
// ============================================================================

function showLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'flex';
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'none';
}

function initBackToSearchButton() {
    const backBtn = document.getElementById('backToSearchBtn');
    const searchSection = document.querySelector('.search-section');
    
    if (!backBtn || !searchSection) return;
    
    function updateButtonVisibility() {
        const searchRect = searchSection.getBoundingClientRect();
        const isSearchVisible = searchRect.top >= 0 && searchRect.top < window.innerHeight / 2;
        
        if (isSearchVisible) {
            // Search is visible, hide button
            backBtn.classList.remove('visible');
            setTimeout(() => {
                if (!backBtn.classList.contains('visible')) {
                    backBtn.style.display = 'none';
                }
            }, 300);
        } else {
            // Search is not visible, show button
            backBtn.classList.add('visible');
            backBtn.style.display = 'block';
        }
    }
    
    backBtn.addEventListener('click', () => {
        searchSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Force update after scroll completes
        setTimeout(updateButtonVisibility, 500);
    });
    
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (scrollTimeout) clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(updateButtonVisibility, 10);
    });
    
    updateButtonVisibility();
}

function makeVerseReferencesClickable() {
    const verseElements = document.querySelectorAll('.verse-reference');
    
    verseElements.forEach(el => {
        if (!el.hasAttribute('data-clickable')) {
            el.setAttribute('data-clickable', 'true');
            el.style.cursor = 'pointer';
            
            el.addEventListener('click', (e) => {
                e.preventDefault();
                const verse = el.textContent.trim();
                openVerseModal(verse);
            });
        }
    });
}

function openVerseModal(verseReference) {
    const modal = document.getElementById('verseModal');
    const referenceEl = document.getElementById('verseReference');
    const verseTextEl = document.getElementById('verseText');
    const bibleGatewayLink = document.getElementById('bibleGatewayLink');
    const youVersionLink = document.getElementById('youVersionLink');
    
    referenceEl.textContent = verseReference;
    
    const encodedVerse = encodeURIComponent(verseReference);
    bibleGatewayLink.href = `https://www.biblegateway.com/passage/?search=${encodedVerse}&version=NRSVUE`;
    youVersionLink.href = `https://www.bible.com/search/bible?q=${encodedVerse}`;
    
    modal.classList.add('active');
    
    verseTextEl.innerHTML = '<div class="loading">📖 Loading verse text...</div>';
    
    setTimeout(() => {
        verseTextEl.innerHTML = `
            <p style="color: var(--text-secondary); font-style: italic;">
                Click the links below to read the full verse text on Bible Gateway or YouVersion.
            </p>
        `;
    }, 300);
}

function closeVerseModal() {
    const modal = document.getElementById('verseModal');
    modal.classList.remove('active');
}

document.addEventListener('click', (e) => {
    const modal = document.getElementById('verseModal');
    if (e.target === modal) {
        closeVerseModal();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeVerseModal();
    }
});