// Backend API base URL (the API is a separately served Flask app, see backend/)
const API_BASE_URL = 'http://localhost:5000';

// Max number of prior Q&A turns kept client-side and sent with each query.
// The backend is stateless - it never stores conversation history itself,
// so each browser tab/user naturally gets its own isolated context.
const MAX_HISTORY_TURNS = 6;

// Global state
let isProcessing = false;
let conversationHistory = [];

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

// Ask question (streams the answer back so it appears incrementally)
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

    // Show thinking indicator until the first event arrives
    const thinkingId = addThinkingIndicator();

    // Clear input
    input.value = '';
    input.style.height = 'auto';

    const numResults = parseInt(document.getElementById('numResults').value, 10);
    const useHybrid = document.getElementById('hybridSearch').checked;
    const useContext = document.getElementById('conversationContext').checked;

    let answerBubble = null;
    let fullAnswer = '';

    try {
        const response = await fetch(`${API_BASE_URL}/api/query/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                n_results: numResults,
                use_hybrid: useHybrid,
                use_context: useContext,
                history: conversationHistory
            })
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Query failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            let boundary;
            while ((boundary = buffer.indexOf('\n\n')) !== -1) {
                const rawEvent = buffer.slice(0, boundary);
                buffer = buffer.slice(boundary + 2);

                if (!rawEvent.startsWith('data: ')) continue;
                const streamEvent = JSON.parse(rawEvent.slice(6));

                if (streamEvent.type === 'sources') {
                    removeThinkingIndicator(thinkingId);
                    answerBubble = createAnswerBubble();
                    updateContextInfo(streamEvent);
                    updateSources(streamEvent.sources);
                } else if (streamEvent.type === 'delta') {
                    fullAnswer += streamEvent.text;
                    if (answerBubble) {
                        answerBubble.contentDiv.textContent = fullAnswer;
                        scrollMessagesToBottom();
                    }
                } else if (streamEvent.type === 'error') {
                    throw new Error(streamEvent.message);
                }
            }
        }

        conversationHistory.push({ question, answer: fullAnswer });
        if (conversationHistory.length > MAX_HISTORY_TURNS) {
            conversationHistory.shift();
        }

    } catch (error) {
        removeThinkingIndicator(thinkingId);
        showToast(`✗ ${error.message}`, 'error');
        if (answerBubble) {
            answerBubble.contentDiv.textContent = fullAnswer
                ? `${fullAnswer}\n\n[Error: ${error.message}]`
                : `Error: ${error.message}`;
        } else {
            addMessage(`Error: ${error.message}`, 'answer');
        }
    } finally {
        isProcessing = false;
        document.getElementById('sendButton').disabled = false;
        input.focus();
    }
}

function scrollMessagesToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Add a static message to the chat (question, or a non-streamed answer/error)
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
    scrollMessagesToBottom();
}

// Create an empty answer bubble whose content gets filled in incrementally as the stream arrives
function createAnswerBubble() {
    const messagesContainer = document.getElementById('chatMessages');

    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-answer';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    messageDiv.appendChild(contentDiv);

    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    metaDiv.textContent = new Date().toLocaleTimeString();
    messageDiv.appendChild(metaDiv);

    messagesContainer.appendChild(messageDiv);
    scrollMessagesToBottom();

    return { messageDiv, contentDiv };
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
    scrollMessagesToBottom();

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

// Update sources panel (built via DOM APIs, not innerHTML, since source name/preview come from
// user-uploaded filenames/documents and must never be interpreted as HTML)
function updateSources(sources) {
    const sourcesList = document.getElementById('sourcesList');
    sourcesList.innerHTML = '';

    if (!sources || sources.length === 0) {
        sourcesList.innerHTML = `
            <div class="empty-state">
                <p>No sources found</p>
            </div>
        `;
        return;
    }

    sources.forEach(source => {
        const item = document.createElement('div');
        item.className = 'source-item';

        const header = document.createElement('div');
        header.className = 'source-header';

        const name = document.createElement('span');
        name.className = 'source-name';
        name.textContent = source.source;

        const badge = document.createElement('span');
        badge.className = 'relevance-badge';
        badge.textContent = `${(source.relevance * 100).toFixed(0)}%`;

        header.appendChild(name);
        header.appendChild(badge);

        const preview = document.createElement('div');
        preview.className = 'source-preview';
        preview.textContent = source.preview;

        item.appendChild(header);
        item.appendChild(preview);
        sourcesList.appendChild(item);
    });
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

// Update document list (built via DOM APIs - document names are user-controlled filenames)
function updateDocumentList(sources) {
    const documentList = document.getElementById('documentList');
    documentList.innerHTML = '';

    if (sources.length === 0) {
        documentList.innerHTML = `
            <div class="empty-state">
                <p>No documents yet</p>
                <p class="empty-hint">Upload your first document to get started</p>
            </div>
        `;
        return;
    }

    sources.forEach(source => {
        const item = document.createElement('div');
        item.className = 'document-item';

        const icon = document.createElement('span');
        icon.className = 'doc-icon';
        icon.textContent = '📄';

        const name = document.createElement('span');
        name.className = 'doc-name';
        name.textContent = source;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-icon';
        deleteBtn.textContent = '🗑️';
        deleteBtn.addEventListener('click', () => deleteDocument(source));

        item.appendChild(icon);
        item.appendChild(name);
        item.appendChild(deleteBtn);
        documentList.appendChild(item);
    });
}

// Load sample questions
async function loadSampleQuestions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sample_questions`);
        const questions = await response.json();

        const container = document.getElementById('sampleQuestions');
        container.innerHTML = '';

        if (questions.length > 0 && !questions[0].includes('Upload')) {
            questions.slice(0, 3).forEach(q => {
                const chip = document.createElement('div');
                chip.className = 'sample-chip';
                chip.textContent = q.length > 40 ? q.substring(0, 40) + '...' : q;
                chip.addEventListener('click', () => useSampleQuestion(q));
                container.appendChild(chip);
            });
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

// Reset the chat UI and local conversation history (no confirmation, no backend call -
// the backend keeps no conversation state, so this is purely a client-side reset)
function resetChatUI() {
    conversationHistory = [];

    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🎯</div>
            <h3>History Cleared!</h3>
            <p>Start a new conversation with your documents.</p>
        </div>
    `;

    document.getElementById('retrievedChunks').textContent = '-';
    document.getElementById('modelUsed').textContent = '-';
    document.getElementById('avgRelevance').textContent = '-';

    document.getElementById('sourcesList').innerHTML = `
        <div class="empty-state">
            <p>No sources yet</p>
        </div>
    `;
}

// "Clear History" button handler
function clearHistory() {
    if (!confirm('Clear conversation history?')) {
        return;
    }

    resetChatUI();
    showToast('Conversation history cleared', 'success');
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
        resetChatUI();
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
