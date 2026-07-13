"""
AI Document Intelligence Assistant - Flask API
JSON API backend for RAG-based document Q&A, consumed by the frontend/ static site
"""

import logging
import os
import sys

# Console output uses ✓/⚠ throughout; Windows terminals often default to a
# non-UTF-8 codepage (e.g. cp1252), which raises UnicodeEncodeError on those
# characters. Force UTF-8 for stdout/stderr before anything else prints.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, 'reconfigure', None)
    if _reconfigure is not None:
        _reconfigure(encoding='utf-8')

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from config import Config
from extensions import limiter
import services
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

    app.register_blueprint(documents_bp)
    app.register_blueprint(query_bp)

    @app.route('/')
    def home():
        """API health check"""
        return jsonify({'status': 'ok', 'service': 'AI Document Intelligence Assistant API'})

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({
            'error': f'File too large. Maximum size is {Config.MAX_FILE_SIZE // (1024 * 1024)}MB'
        }), 413

    @app.errorhandler(500)
    def internal_error(_error):
        logger.exception("Unhandled internal server error")
        return jsonify({'error': 'Internal server error occurred'}), 500

    logger.info("=" * 60)
    logger.info("AI Document Intelligence Assistant")
    logger.info("Upload folder: %s", Config.UPLOAD_FOLDER)
    logger.info("Vector DB: %s", Config.VECTOR_DB_PATH)
    logger.info("API status: %s", "Connected" if services.rag_engine.has_api else "Demo Mode")
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
