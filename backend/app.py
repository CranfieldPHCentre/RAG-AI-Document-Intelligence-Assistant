"""
AI Document Intelligence Assistant - Flask API
JSON API backend for RAG-based document Q&A, consumed by the frontend/ static site
"""

from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime

from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_engine import RAGEngine

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

# Allow the standalone frontend (served from a different origin/port) to call this API
FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'http://localhost:8080')
CORS(app, resources={r"/api/*": {"origins": FRONTEND_ORIGIN}}, supports_credentials=True)

# Configuration
UPLOAD_FOLDER = 'uploads'
VECTOR_DB_PATH = 'vector_db'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VECTOR_DB_PATH, exist_ok=True)

# Initialize components
document_processor = DocumentProcessor(chunk_size=1000, chunk_overlap=200)
vector_store = VectorStore(persist_directory=VECTOR_DB_PATH)
rag_engine = RAGEngine(vector_store)

print("="*60)
print("AI Document Intelligence Assistant")
print("="*60)
print(f"✓ Upload folder: {UPLOAD_FOLDER}")
print(f"✓ Vector DB: {VECTOR_DB_PATH}")
print(f"✓ API Status: {'Connected' if rag_engine.has_api else 'Demo Mode'}")
print("="*60)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session_id():
    """Get or create session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


@app.route('/')
def home():
    """API health check"""
    return jsonify({'status': 'ok', 'service': 'AI Document Intelligence Assistant API'})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle document upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not supported. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # Save file
        # file.filename may be Optional[str]; ensure a str is passed to secure_filename
        filename = secure_filename(file.filename or '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(filepath)
        
        # Process document
        chunks = document_processor.process_file(filepath)
        
        if not chunks:
            return jsonify({'error': 'No text could be extracted from the document'}), 400
        
        # Add to vector store
        num_added = vector_store.add_documents(chunks)
        
        # Get statistics
        doc_stats = document_processor.get_document_stats(chunks)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'chunks_created': num_added,
            'stats': doc_stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def query():
    """Handle user query"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Question cannot be empty'}), 400
        
        # Check if there are documents
        stats = vector_store.get_stats()
        if stats['total_chunks'] == 0:
            return jsonify({
                'error': 'No documents uploaded yet. Please upload documents first.'
            }), 400
        
        # Get query parameters
        n_results = int(data.get('n_results', 5))
        use_hybrid = data.get('use_hybrid', True)
        use_context = data.get('use_context', True)
        
        # Query RAG system
        result = rag_engine.query(
            question=question,
            n_results=n_results,
            use_hybrid=use_hybrid,
            conversation_context=use_context
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get vector store statistics"""
    stats = vector_store.get_stats()
    stats['has_api'] = rag_engine.has_api
    stats['conversation_length'] = len(rag_engine.conversation_history)
    return jsonify(stats)


@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """Clear conversation history"""
    rag_engine.clear_history()
    return jsonify({'success': True, 'message': 'Conversation history cleared'})


@app.route('/api/clear_documents', methods=['POST'])
def clear_documents():
    """Clear all documents from vector store"""
    try:
        vector_store.clear_all()
        rag_engine.clear_history()
        
        # Clean up upload folder
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
        
        return jsonify({
            'success': True,
            'message': 'All documents and history cleared'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete_document', methods=['POST'])
def delete_document():
    """Delete a specific document"""
    try:
        data = request.get_json()
        source = data.get('source')
        
        if not source:
            return jsonify({'error': 'No source specified'}), 400
        
        deleted_count = vector_store.delete_by_source(source)
        
        return jsonify({
            'success': True,
            'deleted_chunks': deleted_count,
            'message': f'Deleted {deleted_count} chunks from {source}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversation_history')
def get_conversation_history():
    """Get conversation history"""
    history = []
    
    for exchange in rag_engine.conversation_history:
        history.append({
            'question': exchange['question'],
            'answer': exchange['answer'],
            'sources': list(set(exchange['sources']))
        })
    
    return jsonify(history)


@app.route('/api/sample_questions')
def get_sample_questions():
    """Get sample questions based on uploaded documents"""
    stats = vector_store.get_stats()
    
    if stats['total_chunks'] == 0:
        return jsonify([
            "Upload a document to get started!",
            "Try uploading a PDF, DOCX, or TXT file",
            "Then ask questions about its content"
        ])
    
    # Generic sample questions
    samples = [
        "What are the main topics covered in these documents?",
        "Can you summarize the key points?",
        "What are the most important takeaways?",
        "Are there any specific recommendations or conclusions?",
        "What details are provided about [specific topic]?"
    ]
    
    return jsonify(samples)


@app.errorhandler(413)
def file_too_large(e):
    """Handle file too large error"""
    return jsonify({
        'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'
    }), 413


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    return jsonify({'error': 'Internal server error occurred'}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Starting AI Document Intelligence Assistant API...")
    print("API listening on http://localhost:5000")
    print(f"Allowing requests from frontend origin: {FRONTEND_ORIGIN}")
    print("Serve the frontend/ directory separately and open it in your browser")
    print("="*60 + "\n")
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("⚠ WARNING: ANTHROPIC_API_KEY not found")
        print("The system will run in demo mode without Claude API")
        print("To enable full functionality, set your API key in .env file")
        print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
