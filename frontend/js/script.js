// Backend API base URL (the API is a separately served Flask app, see backend/)
const API_BASE_URL = 'http://localhost:5000';

// Global state
let isProcessing = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    loadSampleQuestions();
    updateStats();
    updateApiStatus();

    // Auto-resize textarea
    const textarea = document.getElementById('questionInput');
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
    
    // Enter key handling
    textarea.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askQuestion();
        }
    });
    
    // Range slider display
    const rangeInput = document.getElementById('numResults');
    const rangeDisplay = document.getElementById('numResultsValue');
    rangeInput.addEventListener('input', function() {
        rangeDisplay.textContent = this.value;
    });
});

// Initialize file upload
function initializeApp() {
    const fileInput = document.getElementById('fileInput');
    const uploadLabel = document.querySelector('.upload-label');
    
    fileInput.addEventListener('change', handleFileUpload);
    
    // Drag and drop
    uploadLabel.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadLabel.style.borderColor = '#667eea';
        uploadLabel.style.background = '#edf2f7';
    });
    
    uploadLabel.addEventListener('dragleave', (e) => {
        uploadLabel.style.borderColor = '#cbd5e0';
        uploadLabel.style.background = '#f7fafc';
    });
    
    uploadLabel.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadLabel.style.borderColor = '#cbd5e0';
        uploadLabel.style.background = '#f7fafc';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileUpload({ target: fileInput });
        }
    });
}

// Handle file upload
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    showUploadProgress(true);
    updateProgressBar(30, `Processing ${file.name}...`);
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        updateProgressBar(70, 'Creating embeddings...');
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Upload failed');
        }
        
        updateProgressBar(100, 'Complete!');
        
        showToast(`✓ ${data.filename} uploaded successfully! (${data.chunks_created} chunks)`, 'success');
        
        // Update UI
        await updateStats();
        await loadSampleQuestions();
        
        setTimeout(() => showUploadProgress(false), 1000);
        
        // Reset file input
        event.target.value = '';
        
    } catch (error) {
        showToast(`✗ ${error.message}`, 'error');
        showUploadProgress(false);
    }
}

function showUploadProgress(show) {
    document.getElementById('uploadProgress').style.display = show ? 'block' : 'none';
    if (!show) {
        updateProgressBar(0, '');
    }
}

function updateProgressBar(percent, text) {
    document.getElementById('progressFill').style.width = percent + '%';
    document.getElementById('progressText').textContent = text;
}

// Ask question
async function askQuestion() {
    if (isProcessing) return;
    
    const input = document.getElementById('questionInput');
    const question = input.value.trim();
    
    if (!question) {
        showToast('Please enter a question', 'error');
        return;
    }
    
    isProcessing = true;
    document.getElementById('sendButton').disabled = true;
    
    // Add user message
    addMessage(question, 'question');
    
    // Show thinking indicator
    const thinkingId = addThinkingIndicator();
    
    // Clear input
    input.value = '';
    input.style.height = 'auto';
    
    try {
        // Get settings
        const numResults = parseInt(document.getElementById('numResults').value);
        const useHybrid = document.getElementById('hybridSearch').checked;
        const useContext = document.getElementById('conversationContext').checked;
        
        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                n_results: numResults,
                use_hybrid: useHybrid,
                use_context: useContext
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Query failed');
        }
        
        // Remove thinking indicator
        removeThinkingIndicator(thinkingId);
        
        // Add answer
        addMessage(data.answer, 'answer');
        
        // Update context info
        updateContextInfo(data);
        
        // Update sources
        updateSources(data.sources);
        
    } catch (error) {
        removeThinkingIndicator(thinkingId);
        showToast(`✗ ${error.message}`, 'error');
        addMessage(`Error: ${error.message}`, 'answer');
    } finally {
        isProcessing = false;
        document.getElementById('sendButton').disabled = false;
        input.focus();
    }
}

// Add message to chat
function addMessage(text, type) {
    const messagesContainer = document.getElementById('chatMessages');
    
    // Remove welcome message if it exists
    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    messageDiv.appendChild(contentDiv);
    
    // Add timestamp
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    metaDiv.textContent = new Date().toLocaleTimeString();
    messageDiv.appendChild(metaDiv);
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Add thinking indicator
function addThinkingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message message-answer';
    thinkingDiv.id = 'thinking-' + Date.now();
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'thinking';
    contentDiv.innerHTML = `
        <span>Thinking</span>
        <div class="thinking-dots">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        </div>
    `;
    
    thinkingDiv.appendChild(contentDiv);
    messagesContainer.appendChild(thinkingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return thinkingDiv.id;
}

function removeThinkingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

// Update context info
function updateContextInfo(data) {
    document.getElementById('retrievedChunks').textContent = data.retrieved_chunks;
    document.getElementById('modelUsed').textContent = data.model;
    
    if (data.relevance_scores && data.relevance_scores.length > 0) {
        const avgRelevance = data.relevance_scores.reduce((a, b) => a + b, 0) / data.relevance_scores.length;
        document.getElementById('avgRelevance').textContent = (avgRelevance * 100).toFixed(1) + '%';
    } else {
        document.getElementById('avgRelevance').textContent = '-';
    }
}

// Update sources panel
function updateSources(sources) {
    const sourcesList = document.getElementById('sourcesList');
    
    if (!sources || sources.length === 0) {
        sourcesList.innerHTML = `
            <div class="empty-state">
                <p>No sources found</p>
            </div>
        `;
        return;
    }
    
    sourcesList.innerHTML = sources.map((source, index) => `
        <div class="source-item">
            <div class="source-header">
                <span class="source-name">${source.source}</span>
                <span class="relevance-badge">${(source.relevance * 100).toFixed(0)}%</span>
            </div>
            <div class="source-preview">${source.preview}</div>
        </div>
    `).join('');
}

// Update API status badge and demo-mode notice
async function updateApiStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const stats = await response.json();

        const badge = document.getElementById('apiStatus');
        const notice = document.getElementById('apiNotice');

        if (stats.has_api) {
            badge.innerHTML = '<span class="status-badge status-active">✓ Claude API Active</span>';
            notice.style.display = 'none';
        } else {
            badge.innerHTML = '<span class="status-badge status-demo">⚠ Demo Mode</span>';
            notice.style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching API status:', error);
    }
}

// Update stats
async function updateStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const stats = await response.json();
        
        document.getElementById('totalChunks').textContent = stats.total_chunks;
        document.getElementById('totalDocs').textContent = stats.unique_sources;
        
        // Update document list
        updateDocumentList(stats.sources || []);
        
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Update document list
function updateDocumentList(sources) {
    const documentList = document.getElementById('documentList');
    
    if (sources.length === 0) {
        documentList.innerHTML = `
            <div class="empty-state">
                <p>No documents yet</p>
                <p class="empty-hint">Upload your first document to get started</p>
            </div>
        `;
        return;
    }
    
    documentList.innerHTML = sources.map(source => `
        <div class="document-item">
            <span class="doc-icon">📄</span>
            <span class="doc-name">${source}</span>
            <button class="btn-icon" onclick="deleteDocument('${source}')">🗑️</button>
        </div>
    `).join('');
}

// Load sample questions
async function loadSampleQuestions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sample_questions`);
        const questions = await response.json();
        
        const container = document.getElementById('sampleQuestions');
        
        if (questions.length > 0 && !questions[0].includes('Upload')) {
            container.innerHTML = questions.slice(0, 3).map(q => `
                <div class="sample-chip" onclick="useSampleQuestion('${q.replace(/'/g, "\\'")}')">
                    ${q.length > 40 ? q.substring(0, 40) + '...' : q}
                </div>
            `).join('');
        } else {
            container.innerHTML = '';
        }
        
    } catch (error) {
        console.error('Error loading sample questions:', error);
    }
}

function useSampleQuestion(question) {
    document.getElementById('questionInput').value = question;
    document.getElementById('questionInput').focus();
}

// Delete document
async function deleteDocument(source) {
    if (!confirm(`Delete ${source} and all its chunks?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/delete_document`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: source })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error);
        }
        
        showToast(data.message, 'success');
        await updateStats();
        
    } catch (error) {
        showToast(`✗ ${error.message}`, 'error');
    }
}

// Clear conversation history
async function clearHistory() {
    if (!confirm('Clear conversation history?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/clear_history`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error);
        }
        
        showToast(data.message, 'success');
        
        // Clear chat messages
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🎯</div>
                <h3>History Cleared!</h3>
                <p>Start a new conversation with your documents.</p>
            </div>
        `;
        
        // Reset context info
        document.getElementById('retrievedChunks').textContent = '-';
        document.getElementById('modelUsed').textContent = '-';
        document.getElementById('avgRelevance').textContent = '-';
        
        // Clear sources
        document.getElementById('sourcesList').innerHTML = `
            <div class="empty-state">
                <p>No sources yet</p>
            </div>
        `;
        
    } catch (error) {
        showToast(`✗ ${error.message}`, 'error');
    }
}

// Clear all documents
async function clearAllDocuments() {
    if (!confirm('This will delete ALL documents and conversation history. Continue?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/clear_documents`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error);
        }
        
        showToast(data.message, 'success');
        
        await updateStats();
        await clearHistory();
        await loadSampleQuestions();
        
    } catch (error) {
        showToast(`✗ ${error.message}`, 'error');
    }
}

// Toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
