/**
 * Data Over Dogma - Frontend Application
 * Semantic search and AI Q&A for podcast transcripts
 */

// ============================================================================
// GLOBAL STATE
// ============================================================================

let currentConversationId = null;
let messageCount = 0;
let availableEpisodes = [];
let availableBooks = [];
let selectedEpisodes = [];
let selectedBooks = [];

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Data Over Dogma app...');
    
    loadEpisodes();
    loadBooks();
    setupEventListeners();
    updateWordDisplay();
    
    console.log('✅ App initialized');
});

// Setup all event listeners
function setupEventListeners() {
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    const hasVerses = document.getElementById('hasVerses');
    
    if (minWords) minWords.addEventListener('input', updateWordDisplay);
    if (maxWords) maxWords.addEventListener('input', updateWordDisplay);
    if (hasVerses) hasVerses.addEventListener('change', updateActiveFilters);
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.multiselect')) {
            document.querySelectorAll('.multiselect-dropdown').forEach(d => {
                d.classList.remove('open');
            });
        }
    });
}

// Expose functions globally for onclick handlers in HTML
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

// ============================================================================
// DATA LOADING
// ============================================================================

// Load episodes from API
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

// Load Bible books from API
async function loadBooks() {
    try {
        const response = await fetch('/api/verses/api/verses/books');
        const data = await response.json();
        
        availableBooks = data.books;
        const bookOptions = document.getElementById('bookOptions');
        if (!bookOptions) return;
        
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
    }
}

// ============================================================================
// MULTISELECT DROPDOWN CONTROLS
// ============================================================================

// Toggle multiselect dropdown visibility
function toggleDropdown(type) {
    const dropdown = document.getElementById(`${type}Dropdown`);
    if (!dropdown) return;
    
    dropdown.classList.toggle('open');
    
    // Close other dropdowns
    const allDropdowns = document.querySelectorAll('.multiselect-dropdown');
    allDropdowns.forEach(d => {
        if (d !== dropdown) {
            d.classList.remove('open');
        }
    });
}

// Filter multiselect options by search text
function filterOptions(type) {
    const searchInput = document.getElementById(`${type}Search`);
    const options = document.getElementById(`${type}Options`);
    if (!searchInput || !options) return;
    
    const filter = searchInput.value.toLowerCase();
    
    Array.from(options.children).forEach((option, index) => {
        if (index === 0) return; // Skip "All" option
        const text = option.textContent.toLowerCase();
        option.style.display = text.includes(filter) ? 'flex' : 'none';
    });
}

// ============================================================================
// EPISODE SELECTION
// ============================================================================

// Select/deselect all episodes
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

// Update episode selection state
function updateEpisodeSelection() {
    const allCheckbox = document.getElementById('ep-all');
    const checkboxes = Array.from(document.querySelectorAll('#episodeOptions input[type="checkbox"]:not(#ep-all)'));
    
    selectedEpisodes = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
    
    // Update "All" checkbox state
    if (allCheckbox) {
        const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
        allCheckbox.checked = allChecked;
    }
    
    // Update display text
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

// ============================================================================
// BIBLE BOOK SELECTION
// ============================================================================

// Select/deselect all books
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

// Update book selection state
function updateBookSelection() {
    const allCheckbox = document.getElementById('book-all');
    const checkboxes = Array.from(document.querySelectorAll('#bookOptions input[type="checkbox"]:not(#book-all)'));
    
    selectedBooks = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
    
    // Update "All" checkbox state
    if (allCheckbox) {
        const allChecked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
        allCheckbox.checked = allChecked;
    }
    
    // Update display text
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

// Update word count slider display
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

// Update active filters display panel
function updateActiveFilters() {
    const filters = [];
    
    // Episode filter
    if (selectedEpisodes.length > 0 && selectedEpisodes.length < availableEpisodes.length) {
        filters.push(`${selectedEpisodes.length} episodes`);
    }
    
    // Book filter
    if (selectedBooks.length > 0 && selectedBooks.length < availableBooks.length) {
        filters.push(`${selectedBooks.length} books`);
    }
    
    // Has verses
    const hasVerses = document.getElementById('hasVerses');
    if (hasVerses && hasVerses.checked) {
        filters.push('with verses only');
    }
    
    // Word count
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    if (minWords && maxWords) {
        const minVal = parseInt(minWords.value);
        const maxVal = parseInt(maxWords.value);
        if (minVal > 0 || maxVal < 5000) {
            filters.push(`${minVal}-${maxVal} words`);
        }
    }
    
    // Display active filters
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

// Reset all filters to default values
function resetFilters() {
    // Reset episodes - uncheck all individual, check "All"
    const epAll = document.getElementById('ep-all');
    if (epAll) {
        epAll.checked = true;
        const checkboxes = document.querySelectorAll('#episodeOptions input[type="checkbox"]:not(#ep-all)');
        checkboxes.forEach(cb => cb.checked = false);
        selectedEpisodes = [];
        const epDisplay = document.getElementById('episodeDisplay');
        if (epDisplay) epDisplay.textContent = 'All Episodes';
    }
    
    // Reset books - uncheck all individual, check "All"
    const bookAll = document.getElementById('book-all');
    if (bookAll) {
        bookAll.checked = true;
        const checkboxes = document.querySelectorAll('#bookOptions input[type="checkbox"]:not(#book-all)');
        checkboxes.forEach(cb => cb.checked = false);
        selectedBooks = [];
        const bookDisplay = document.getElementById('bookDisplay');
        if (bookDisplay) bookDisplay.textContent = 'All Books';
    }
    
    // Reset other filters
    const hasVerses = document.getElementById('hasVerses');
    if (hasVerses) hasVerses.checked = false;
    
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    if (minWords) minWords.value = 0;
    if (maxWords) maxWords.value = 5000;
    
    const topK = document.getElementById('topK');
    const minScore = document.getElementById('minScore');
    if (topK) topK.value = 5;
    if (minScore) minScore.value = 0.0;
    
    const queryRewriting = document.getElementById('queryRewriting');
    const useContext = document.getElementById('useContext');
    if (queryRewriting) queryRewriting.checked = true;
    if (useContext) useContext.checked = true;
    
    updateWordDisplay();
    updateActiveFilters();
    
    console.log('✅ Filters reset');
}

// Get current filter values in backend-compatible format
function getFilters() {
    const minWords = document.getElementById('minWords');
    const maxWords = document.getElementById('maxWords');
    const hasVerses = document.getElementById('hasVerses');
    const topK = document.getElementById('topK');
    const minScore = document.getElementById('minScore');
    const queryRewriting = document.getElementById('queryRewriting');
    const useContext = document.getElementById('useContext');
    
    // Build base filters
    const filters = {
        top_k: topK ? parseInt(topK.value) : 5,
        min_score: minScore ? parseFloat(minScore.value) : 0.0,
        use_rewrite: queryRewriting ? queryRewriting.checked : true,
        use_context: useContext ? useContext.checked : true
    };
    
    // Add conversation ID if exists
    if (currentConversationId) {
        filters.conversation_id = currentConversationId;
    }
    
    // Episodes as ARRAY (backend expects: "episodes": ["episode_001", "episode_002"])
    if (selectedEpisodes.length > 0) {
        filters.episodes = selectedEpisodes;
    }
    
    // Has verses flag
    if (hasVerses && hasVerses.checked) {
        filters.has_verses = true;
    }
    
    // Books as ARRAY (backend expects: "books": ["Genesis", "Exodus"])
    if (selectedBooks.length > 0) {
        filters.books = selectedBooks;
    }
    
    // Word count range
    if (minWords && parseInt(minWords.value) > 0) {
        filters.min_word_count = parseInt(minWords.value);
    }
    
    if (maxWords && parseInt(maxWords.value) < 5000) {
        filters.max_word_count = parseInt(maxWords.value);
    }
    
    return filters;
}

// ============================================================================
// SEARCH FUNCTIONALITY
// ============================================================================

// Perform semantic search
async function performSearch() {
    const queryInput = document.getElementById('queryInput');
    if (!queryInput) return;
    
    const query = queryInput.value.trim();
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    // Hide previous results
    const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
    const answerPanel = document.getElementById('answerPanel');
    const searchResults = document.getElementById('searchResults');
    
    if (rewrittenPanel) rewrittenPanel.style.display = 'none';
    if (answerPanel) answerPanel.style.display = 'none';
    if (searchResults) searchResults.innerHTML = '<p class="loading">🔍 Searching...</p>';
    
    try {
        const filters = getFilters();
        
        // Build request body
        const requestBody = {
            query: query,
            ...filters
        };
        
        // Remove null/undefined values
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
            updateConversationUI();
        }
        
        // Show rewritten query if different
        if (data.rewritten_query && data.rewritten_query !== query && rewrittenPanel) {
            const rewrittenQuery = document.getElementById('rewrittenQuery');
            if (rewrittenQuery) {
                rewrittenQuery.textContent = data.rewritten_query;
                rewrittenPanel.style.display = 'block';
            }
        }
        
        // Display results
        displayResults(data.results);
        
        console.log(`✅ Found ${data.results.length} results`);
        
    } catch (error) {
        if (searchResults) {
            searchResults.innerHTML = `<p class="loading">❌ Error: ${error.message}</p>`;
        }
        console.error('❌ Search error:', error);
    }
}

// ============================================================================
// AI Q&A FUNCTIONALITY
// ============================================================================

// Ask AI a question with streaming response
async function askAI() {
    const queryInput = document.getElementById('queryInput');
    if (!queryInput) return;
    
    const query = queryInput.value.trim();
    if (!query) {
        alert('Please enter a question');
        return;
    }
    
    // Setup UI
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
        
        // Build URL parameters for GET request (SSE endpoint)
        const params = new URLSearchParams({
            query: query,
            top_k: filters.top_k,
            min_score: filters.min_score,
            use_rewrite: filters.use_rewrite,
            use_context: filters.use_context
        });
        
        // Add episodes as multiple params
        if (selectedEpisodes.length > 0) {
            selectedEpisodes.forEach(ep => params.append('episodes', ep));
        }
        
        // Has verses flag
        if (filters.has_verses) {
            params.append('has_verses', 'true');
        }
        
        // Add books as multiple params
        if (selectedBooks.length > 0) {
            selectedBooks.forEach(book => params.append('books', book));
        }
        
        // Word count filters
        if (filters.min_word_count) {
            params.append('min_word_count', filters.min_word_count);
        }
        
        if (filters.max_word_count) {
            params.append('max_word_count', filters.max_word_count);
        }
        
        // Conversation ID
        if (currentConversationId) {
            params.append('conversation_id', currentConversationId);
        }
        
        console.log('🤖 AI request params:', params.toString());
        
        // Open Server-Sent Events connection
        const eventSource = new EventSource(`/api/query/answer?${params}`);
        
        let fullAnswer = '';
        let searchResultsData = [];
        
        // Handle rewritten query event
        eventSource.addEventListener('rewritten_query', (e) => {
            const rewrittenQuery = document.getElementById('rewrittenQuery');
            if (rewrittenQuery && rewrittenPanel) {
                rewrittenQuery.textContent = e.data;
                rewrittenPanel.style.display = 'block';
            }
        });
        
        // Handle search results event
        eventSource.addEventListener('search_results', (e) => {
            const data = JSON.parse(e.data);
            searchResultsData = data.results;
        });
        
        // Handle answer streaming chunks
        eventSource.addEventListener('answer_chunk', (e) => {
            fullAnswer += e.data;
            if (aiAnswer) {
                aiAnswer.textContent = fullAnswer;
            }
        });
        
        // Handle completion
        eventSource.addEventListener('answer_complete', (e) => {
            const data = JSON.parse(e.data);
            
            // Update conversation
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                messageCount += 2;
                updateConversationUI();
            }
            
            // Show sources
            if (searchResultsData.length > 0) {
                displayResults(searchResultsData);
            }
            
            eventSource.close();
            console.log('✅ Answer complete');
        });
        
        // Handle errors
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
// RESULTS DISPLAY
// ============================================================================

// Display search results in the UI
function displayResults(results) {
    const container = document.getElementById('searchResults');
    const countEl = document.getElementById('resultCount');
    
    if (countEl) {
        countEl.textContent = results.length;
    }
    
    if (!container) return;
    
    if (results.length === 0) {
        container.innerHTML = '<p class="loading">No results found</p>';
        return;
    }
    
    container.innerHTML = results.map(result => {
        const scorePercent = (result.score * 100).toFixed(1);
        
        // Build verses HTML
        let versesHTML = '';
        if (result.verse_references) {
            const verses = result.verse_references.split(',').map(v => v.trim());
            versesHTML = `
                <div class="result-verses">
                    📖 ${verses.map(v => `<span class="verse-reference">${v}</span>`).join('')}
                </div>
            `;
        }
        
        // Build books HTML
        let booksHTML = '';
        if (result.books_mentioned) {
            const books = result.books_mentioned.split(',').map(b => b.trim());
            booksHTML = books.map(b => `<span class="book-tag">${b}</span>`).join('');
        }
        
        // Extract segment number from segment_id
        const segmentNum = result.segment_id.split('_').pop();
        
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
                <div class="result-text">${result.text}</div>
                ${versesHTML}
                ${booksHTML ? `<div style="margin-top: 10px;">${booksHTML}</div>` : ''}
            </div>
        `;
    }).join('');
}

// ============================================================================
// CONVERSATION MANAGEMENT
// ============================================================================

// Update conversation UI panel
function updateConversationUI() {
    const panel = document.getElementById('conversationPanel');
    const count = document.getElementById('conversationCount');
    
    if (count) {
        count.textContent = messageCount;
    }
    if (panel) {
        panel.style.display = 'block';
    }
}

// Clear conversation history
function clearHistory() {
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
        messageCount = 0;
        
        const panel = document.getElementById('conversationPanel');
        const rewrittenPanel = document.getElementById('rewrittenQueryPanel');
        if (panel) panel.style.display = 'none';
        if (rewrittenPanel) rewrittenPanel.style.display = 'none';
        
        console.log('✅ Conversation cleared');
    })
    .catch(error => {
        console.error('❌ Failed to clear conversation:', error);
        alert('Failed to clear conversation');
    });
}

// ============================================================================
// END OF FILE
// ============================================================================