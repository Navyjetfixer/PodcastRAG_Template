/**
 * Bible Verse Filtering Component
 */

class VerseFilter {
    constructor() {
        this.availableBooks = [];
        this.selectedBooks = [];
        this.init();
    }

    async init() {
        await this.loadAvailableBooks();
        this.setupUI();
    }

    async loadAvailableBooks() {
        try {
            const response = await fetch('/api/verses/books');
            const data = await response.json();
            this.availableBooks = data.books;
        } catch (error) {
            console.error('Failed to load books:', error);
        }
    }

    setupUI() {
        // Add verse filter toggle to search UI
        const searchControls = document.querySelector('.search-controls');
        if (!searchControls) return;

        const verseFilterHTML = `
            <div class="verse-filter-container">
                <button id="toggle-verse-filter" class="btn-secondary">
                    📖 Filter by Bible Verses
                </button>
                
                <div id="verse-filter-panel" class="verse-filter-panel hidden">
                    <div class="filter-options">
                        <label>
                            <input type="checkbox" id="verses-only-checkbox">
                            Show only segments with Bible verses
                        </label>
                        
                        <div class="book-filter">
                            <label>Filter by Bible books:</label>
                            <div id="book-checkboxes" class="book-checkboxes">
                                ${this.renderBookCheckboxes()}
                            </div>
                        </div>
                        
                        <button id="apply-verse-filter" class="btn-primary">
                            Apply Filter
                        </button>
                        <button id="clear-verse-filter" class="btn-secondary">
                            Clear Filter
                        </button>
                    </div>
                    
                    <div id="verse-stats" class="verse-stats"></div>
                </div>
            </div>
        `;

        searchControls.insertAdjacentHTML('beforeend', verseFilterHTML);
        this.attachEventListeners();
        this.loadVerseStats();
    }

    renderBookCheckboxes() {
        return this.availableBooks.map(book => `
            <label class="book-checkbox">
                <input type="checkbox" value="${book}" class="book-filter-checkbox">
                ${book}
            </label>
        `).join('');
    }

    attachEventListeners() {
        // Toggle panel
        document.getElementById('toggle-verse-filter')?.addEventListener('click', () => {
            const panel = document.getElementById('verse-filter-panel');
            panel?.classList.toggle('hidden');
        });

        // Apply filter
        document.getElementById('apply-verse-filter')?.addEventListener('click', () => {
            this.applyFilter();
        });

        // Clear filter
        document.getElementById('clear-verse-filter')?.addEventListener('click', () => {
            this.clearFilter();
        });

        // Update selected books
        document.querySelectorAll('.book-filter-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedBooks.push(e.target.value);
                } else {
                    this.selectedBooks = this.selectedBooks.filter(b => b !== e.target.value);
                }
            });
        });
    }

    async applyFilter() {
        const versesOnly = document.getElementById('verses-only-checkbox')?.checked || false;

        if (!versesOnly && this.selectedBooks.length === 0) {
            alert('Please select at least one filter option');
            return;
        }

        try {
            const response = await fetch('/api/verses/filter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    books: this.selectedBooks.length > 0 ? this.selectedBooks : null,
                    has_verses_only: versesOnly
                })
            });

            const data = await response.json();
            this.displayFilteredResults(data.segments);
        } catch (error) {
            console.error('Failed to apply filter:', error);
        }
    }

    clearFilter() {
        // Uncheck all boxes
        document.querySelectorAll('.book-filter-checkbox').forEach(cb => cb.checked = false);
        document.getElementById('verses-only-checkbox').checked = false;
        this.selectedBooks = [];
        
        // Clear results
        const resultsContainer = document.getElementById('search-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
        }
    }

    displayFilteredResults(segments) {
        const resultsContainer = document.getElementById('search-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = `
            <div class="filter-results">
                <h3>📖 Filtered Results (${segments.length} segments)</h3>
                ${segments.map(seg => this.renderSegment(seg)).join('')}
            </div>
        `;
    }

    renderSegment(segment) {
        const verseInfo = segment.verse_references ? 
            `<div class="verse-references">📖 ${segment.verse_references}</div>` : '';

        return `
            <div class="search-result-item">
                <div class="result-header">
                    <strong>${segment.episode_title}</strong>
                    <span class="timestamp">${this.formatTime(segment.start_time)}</span>
                </div>
                <div class="result-text">${this.highlightVerses(segment.text)}</div>
                ${verseInfo}
            </div>
        `;
    }

    highlightVerses(text) {
        // Simple verse highlighting (can be enhanced)
        const versePattern = /\b([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)(?:-(\d+))?\b/g;
        return text.replace(versePattern, '<span class="verse-highlight">$&</span>');
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    async loadVerseStats() {
        try {
            const response = await fetch('/api/verses/stats');
            const stats = await response.json();
            
            const statsContainer = document.getElementById('verse-stats');
            if (!statsContainer) return;

            statsContainer.innerHTML = `
                <h4>📊 Verse Statistics</h4>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${stats.segments_with_verses}</div>
                        <div class="stat-label">Segments with verses</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.total_verses}</div>
                        <div class="stat-label">Total verse references</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.unique_books.length}</div>
                        <div class="stat-label">Unique books</div>
                    </div>
                </div>
                <div class="top-books">
                    <strong>Most mentioned books:</strong>
                    <ul>
                        ${stats.top_books.slice(0, 5).map(b => 
                            `<li>${b.book}: ${b.count} mentions</li>`
                        ).join('')}
                    </ul>
                </div>
            `;
        } catch (error) {
            console.error('Failed to load verse stats:', error);
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.verseFilter = new VerseFilter();
});