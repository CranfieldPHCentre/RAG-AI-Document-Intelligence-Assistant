"""
AI Document Intelligence Assistant - Flask API
JSON API backend for RAG-based document Q&A, consumed by the frontend/ static site
"""

import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from config import Config
from extensions import limiter
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_engine import RAGEngine
from routes.documents import documents_bp
from routes.query import query_bp

load_dotenv()


def create_app() -> Flask:
    """Application factory: builds the Flask app, wires extensions and shared components"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )
    logger = logging.getLogger(__name__)

    app = Flask(__name__)

    app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.VECTOR_DB_PATH, exist_ok=True)

    # Only the frontend origin may call the API; no cookies/credentials are used
    # (conversation history is stateless, supplied by the client on each request)
    CORS(app, resources={r"/api/*": {"origins": Config.FRONTEND_ORIGIN}})

    limiter.init_app(app)

    # Shared components, attached to the app object so blueprints reach them via current_app
    app.document_processor = DocumentProcessor(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
    app.vector_store = VectorStore(persist_directory=Config.VECTOR_DB_PATH)
    app.rag_engine = RAGEngine(app.vector_store)

    app.register_blueprint(documents_bp)
    app.register_blueprint(query_bp)

    @app.route('/')
    def home():
        """API health check"""
        return jsonify({'status': 'ok', 'service': 'AI Document Intelligence Assistant API'})

    @app.errorhandler(413)
    def file_too_large(e):
        return jsonify({
            'error': f'File too large. Maximum size is {Config.MAX_FILE_SIZE // (1024 * 1024)}MB'
        }), 413

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Unhandled internal server error")
        return jsonify({'error': 'Internal server error occurred'}), 500

    logger.info("=" * 60)
    logger.info("AI Document Intelligence Assistant")
    logger.info("Upload folder: %s", Config.UPLOAD_FOLDER)
    logger.info("Vector DB: %s", Config.VECTOR_DB_PATH)
    logger.info("API status: %s", "Connected" if app.rag_engine.has_api else "Demo Mode")
    logger.info("=" * 60)

    return app


if __name__ == '__main__':
    app = create_app()
    logger = logging.getLogger(__name__)

    logger.info("Starting AI Document Intelligence Assistant API...")
    logger.info("API listening on http://localhost:5000")
    logger.info("Allowing requests from frontend origin: %s", Config.FRONTEND_ORIGIN)
    logger.info("Serve the frontend/ directory separately and open it in your browser")

    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.warning("ANTHROPIC_API_KEY not found - running in demo mode. Set it in .env for full functionality.")

    # threaded=True lets the dev server handle concurrent requests; use waitress (see README) for production
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
