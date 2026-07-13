# 🤖 AI Document Intelligence Assistant

A state-of-the-art **RAG (Retrieval Augmented Generation)** system that enables intelligent Q&A over your documents using vector embeddings, semantic search, and Claude AI.

## 🎯 Project Overview

This advanced AI application demonstrates cutting-edge technologies in natural language processing, information retrieval, and large language model integration. Upload your documents, and ask questions - the system will find relevant information and generate accurate, cited answers.

**This is a production-grade showcase of:**
- ✅ Retrieval Augmented Generation (RAG) architecture
- ✅ Vector embeddings with Sentence Transformers
- ✅ Semantic search using ChromaDB
- ✅ Claude API integration (Sonnet 4)
- ✅ Multi-format document processing (PDF, DOCX, TXT, MD)
- ✅ Hybrid search (semantic + keyword matching)
- ✅ Conversational memory and context
- ✅ Real-time source citations with relevance scores

## 💼 Skills Demonstrated

### Advanced AI/ML
- RAG system architecture and implementation
- Vector embeddings and semantic search
- Large Language Model (LLM) integration
- Prompt engineering for accurate responses
- Hybrid retrieval strategies

### NLP & Document Processing
- Multi-format document parsing
- Text chunking with optimal overlap
- Named entity recognition
- Semantic similarity scoring
- Citation extraction

### Software Engineering
- Modular, production-ready architecture
- RESTful API design
- Real-time web application
- Error handling and validation
- State management

### Modern Tech Stack
- LangChain ecosystem concepts
- Vector databases (ChromaDB)
- Latest Claude API (2025)
- Sentence Transformers
- Flask web framework

## 🛠️ Technologies Used

| Category | Technology | Purpose |
|----------|-----------|---------|
| **LLM** | Claude Sonnet 4 | Answer generation |
| **Embeddings** | all-MiniLM-L6-v2 | Text vectorization |
| **Vector DB** | ChromaDB | Embedding storage & search |
| **Backend** | Flask | Web application framework |
| **Document Processing** | pypdf, python-docx | File parsing |
| **NLP** | Sentence Transformers | Semantic encoding |
| **Frontend** | HTML5, CSS3, JavaScript | User interface |

## 📂 Project Structure

The backend (Flask JSON API) and frontend (static HTML/CSS/JS) are fully independent — each can be run, deployed, or replaced on its own. The backend is stateless: it keeps no per-user data in memory, so it scales horizontally without sticky sessions (see [Conversational Memory](#5-conversational-memory)).

```
rag_assistant/
├── backend/
│   ├── app.py                  # Flask app factory (create_app), logging, error handlers
│   ├── wsgi.py                 # Production entrypoint (waitress-serve wsgi:app)
│   ├── config.py               # Env-driven configuration
│   ├── extensions.py           # Shared Flask extensions (Flask-Limiter)
│   ├── services.py             # Shared component singletons (vector store, RAG engine, doc processor)
│   ├── schemas.py               # Pydantic request validation (QueryRequest, DeleteDocumentRequest)
│   ├── routes/
│   │   ├── documents.py        # /api/upload, /api/stats, /api/delete_document, /api/clear_documents, /api/sample_questions
│   │   └── query.py            # /api/query, /api/query/stream (SSE)
│   ├── document_processor.py   # Multi-format document parsing & chunking
│   ├── vector_store.py         # ChromaDB vector database management (thread-safe, cached embeddings)
│   ├── rag_engine.py           # RAG orchestration & Claude integration (stateless)
│   ├── tests/                  # pytest unit tests
│   ├── requirements.txt        # Python dependencies
│   ├── requirements-dev.txt    # + pytest, for running the test suite
│   ├── .env.example            # Environment variables template
│   ├── uploads/                # Uploaded documents (auto-created)
│   └── vector_db/              # Vector database storage (auto-created)
├── frontend/
│   ├── index.html              # Main web interface
│   ├── css/
│   │   └── style.css           # Modern, responsive styling
│   └── js/
│       └── script.js           # Frontend interactivity (calls backend API, keeps chat history client-side)
└── README.md                   # This file
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Anthropic API key (get free credits at [console.anthropic.com](https://console.anthropic.com/))

### Step-by-Step Installation

1. **Navigate to the backend directory:**
```bash
cd rag_assistant/backend
```

2. **Create virtual environment:**
```bash
python -m venv venv

# Activate on Windows:
venv\Scripts\activate

# Activate on macOS/Linux:
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
# Or, to also run the test suite:
pip install -r requirements-dev.txt
```

4. **Set up environment variables:**
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=your_actual_api_key_here
```

5. **Run the backend API (from `backend/`):**
```bash
python app.py
```
This starts the JSON API on `http://localhost:5000` (dev server, threaded, auto-reload). For production, see [Deployment Options](#-deployment-options).

6. **Run the frontend (from `frontend/`, in a separate terminal):**
```bash
cd ../frontend
python -m http.server 8080
```

7. **Open your browser:**
Navigate to `http://localhost:8080`

> The backend only allows requests from the origin set in `FRONTEND_ORIGIN` (default `http://localhost:8080`). If you serve the frontend from a different port, set `FRONTEND_ORIGIN` in `backend/.env` to match.

## 💻 How to Use

### 1. Upload Documents
- Click the upload area or drag & drop files
- Supported formats: PDF, DOCX, TXT, MD
- Maximum size: 10MB per file
- Documents are automatically processed and embedded

### 2. Ask Questions
- Type your question in the chat input
- Press Enter or click the send button
- The system will:
  - Search for relevant document sections
  - Retrieve top matching chunks
  - Generate an answer using Claude
  - Cite sources with relevance scores

### 3. View Sources
- See which documents were used
- Check relevance scores
- View text previews from each source

### 4. Adjust Settings
- **Hybrid Search:** Combine semantic + keyword matching
- **Conversation Context:** Use previous Q&A for better answers
- **Results Count:** Number of chunks to retrieve (3-10)

## 🧠 How It Works

### RAG Pipeline

```
User Question
    ↓
1. RETRIEVAL
   ├── Generate query embedding (384-dim vector)
   ├── Search ChromaDB vector store
   ├── Rank by cosine similarity
   └── Optional: Hybrid scoring with keyword overlap
    ↓
2. AUGMENTATION
   ├── Retrieve top K document chunks
   ├── Format as context with metadata
   └── Build conversation history
    ↓
3. GENERATION
   ├── Send to Claude API with context
   ├── Structured prompt for accuracy
   ├── Citation instructions
   └── Generate grounded answer
    ↓
Answer with Sources
```

### Document Processing

**Chunking Strategy:**
- Default chunk size: 1000 characters
- Overlap: 200 characters
- Smart boundary detection (sentence endings)
- Metadata preservation (source, position, timestamp)

**Embedding Generation:**
- Model: all-MiniLM-L6-v2 (384-dimensional)
- Batch processing for efficiency
- Persistent storage in ChromaDB

### Hybrid Search

Combines two retrieval methods:
1. **Semantic Search (70%):** Vector similarity matching
2. **Keyword Search (30%):** Term overlap scoring

This handles both conceptual queries and specific terminology.

## 📊 Key Features Explained

### 1. Vector Embeddings
Documents are converted into high-dimensional vectors that capture semantic meaning. Similar concepts have similar vectors, enabling intelligent retrieval.

### 2. Semantic Search
Unlike keyword search, semantic search understands meaning:
- "How do I reduce costs?" matches "cost-cutting strategies"
- "ML algorithms" matches "machine learning techniques"

### 3. Context Window Management
The system intelligently manages context:
- Retrieves relevant chunks
- Maintains conversation history
- Stays within Claude's token limits

### 4. Source Attribution
Every answer includes:
- Source document name
- Relevance score (0-1)
- Text preview
- Chunk position

### 5. Conversational Memory (stateless)
The backend keeps **no** per-user conversation state — it never mutates shared memory between requests, which is what lets it scale across multiple worker threads/processes without cross-user data ever bleeding together. Instead:
- The frontend keeps the last few Q&A turns in memory (`conversationHistory` in `script.js`)
- Each `/api/query` or `/api/query/stream` request sends that history in the `history` field
- The server uses whatever history is sent for that single request, then forgets it
- "Clear History" is a purely client-side action (clears the chat UI + the local history array)

## 🔧 Advanced Configuration

Most settings are read from environment variables — see `backend/.env.example` and `backend/config.py` (chunk size/overlap, upload limits, rate limits, log level, frontend origin, max history turns).

### Adjust Chunk Size
```bash
# In backend/.env
CHUNK_SIZE=1500     # Larger chunks for more context
CHUNK_OVERLAP=300   # More overlap for better continuity
```

### Change Embedding Model
```python
# In backend/vector_store.py
self.embedding_model = SentenceTransformer('all-mpnet-base-v2')  # Higher quality
```

### Modify Claude Parameters
```python
# In backend/rag_engine.py
response = self.client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,     # Longer answers
    temperature=0.3,     # More focused responses
    system=system_prompt,
    messages=messages
)
```

## 📈 Performance & Scalability

**Already built in:**
- Stateless request handling (see [Conversational Memory](#5-conversational-memory-stateless)) — no sticky sessions needed to scale to multiple workers/instances
- Query-embedding LRU cache in `VectorStore` (repeat/backtracked chat questions skip re-encoding)
- A `threading.Lock` around `SentenceTransformer.encode()` so concurrent requests can't corrupt each other
- O(1) `get_stats()` source counting (a running set, updated on add/delete/clear, instead of re-sampling the collection)
- Streaming answers over SSE (`/api/query/stream`) so the UI shows tokens as they're generated instead of waiting for the full response
- Flask-Limiter rate limits on `/api/upload` and `/api/query*` (tune via `UPLOAD_RATE_LIMIT`/`QUERY_RATE_LIMIT` in `.env`)

**For Large Document Sets:**
1. Use approximate nearest neighbor search (ChromaDB's HNSW index is already in use)
2. Consider a managed/sharded vector DB if a single-node ChromaDB store outgrows disk/RAM

**For Production:**
1. Serve with `waitress` (see Deployment below) instead of the Flask dev server
2. Use Flask-Limiter's Redis storage backend instead of in-memory (required once you run more than one worker process)
3. Add authentication in front of the API if it's exposed beyond a trusted network
4. Put NGINX (or similar) in front for TLS/compression

## 🚀 Deployment Options

### Local Development
Already configured! Run the backend (`python backend/app.py`) and frontend (`python -m http.server 8080` from `frontend/`) separately.

### Production (waitress)
`waitress` is a pure-Python, cross-platform WSGI server (works on Windows, unlike gunicorn) and is included in `requirements.txt`:
```bash
cd backend
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```
`wsgi.py` exposes the app built by `create_app()` as `app`, so any WSGI-compatible server (gunicorn on Linux, uWSGI, etc.) can target `wsgi:app` the same way.

### Docker
```dockerfile
# Backend
FROM python:3.9-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["waitress-serve", "--listen=0.0.0.0:5000", "wsgi:app"]
```
The frontend/ directory can be served by any static file host (nginx, Netlify, S3, etc.) — it makes no assumptions about the backend's deployment.

### Cloud Platforms
- **Heroku:** Add `Procfile` with `web: waitress-serve --listen=0.0.0.0:$PORT wsgi:app` in `backend/`
- **AWS:** Deploy the backend on ECS with a persistent volume for `vector_db`; host the frontend on S3/CloudFront
- **Google Cloud:** Use Cloud Run for the backend and Cloud Storage/Firebase Hosting for the frontend

## ⚠️ Important Notes

### API Key Required
- Demo mode works without API key (shows retrieval only)
- Full functionality requires Anthropic API key
- Free tier includes generous credits

### Document Privacy
- Documents stored locally in `backend/uploads/` folder
- Vector embeddings stored in `backend/vector_db/` directory
- No data sent to external services except Claude API queries

### Limitations
- Max file size: 10MB (configurable)
- Max document length: Limited by memory
- API rate limits apply (varies by tier)

## 🐛 Troubleshooting

### "No API key found"
**Solution:** Create `backend/.env` file and add `ANTHROPIC_API_KEY=your_key`

### Frontend can't reach the API / CORS errors in browser console
**Solution:** Make sure the backend is running on `http://localhost:5000` and that `FRONTEND_ORIGIN` in `backend/.env` matches the URL you're serving the frontend from.

### Slow embedding generation
**Normal:** First-time model download takes ~500MB
**Solution:** Model caches after first run

### "CUDA not available" warning
**Normal:** CPU inference works fine for this model
**Optional:** Install torch with CUDA for GPU acceleration

### ChromaDB errors
**Solution:** Delete `backend/vector_db/` folder and restart

### Running the test suite
```bash
cd backend
pip install -r requirements-dev.txt
pytest
```
Tests cover document chunking/cleaning, vector store add/search/delete/stats tracking, and the RAG engine's stateless query handling — no API key or network access required (they run in demo mode).

## 📚 Learning Resources

### Understanding RAG
- [Anthropic's RAG Guide](https://docs.anthropic.com/claude/docs/retrieval-augmented-generation-rag)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/use_cases/question_answering/)

### Vector Databases
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Embeddings Explained](https://www.pinecone.io/learn/vector-embeddings/)

### Sentence Transformers
- [Official Documentation](https://www.sbert.net/)
- [Model Hub](https://huggingface.co/sentence-transformers)

## 💡 Extension Ideas

**Advanced Features:**
- Multi-language support
- Table/chart extraction from PDFs
- Audio transcription integration
- Comparative analysis mode
- Automated summarization

**Enterprise Features:**
- Multi-user support
- Document versioning
- Audit logging
- SSO authentication
- Role-based access control

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
