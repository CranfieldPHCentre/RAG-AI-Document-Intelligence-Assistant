"""
Document management routes: upload, list, delete, clear, sample questions
"""

import os
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from pydantic import ValidationError

from config import Config
from extensions import limiter
from schemas import DeleteDocumentRequest

logger = logging.getLogger(__name__)

documents_bp = Blueprint('documents', __name__, url_prefix='/api')


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def _cleanup_and_error(filepath: str, message: str, status: int = 400):
    """Remove a partially-processed upload and return an error response"""
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({'error': message}), status


@documents_bp.route('/upload', methods=['POST'])
@limiter.limit(Config.UPLOAD_RATE_LIMIT)
def upload_file():
    """Handle document upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not supported. Allowed: {", ".join(Config.ALLOWED_EXTENSIONS)}'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

    file.save(filepath)

    try:
        chunks = current_app.document_processor.process_file(filepath)

        if not chunks:
            return _cleanup_and_error(filepath, 'No text could be extracted from the document')

        num_added = current_app.vector_store.add_documents(chunks)
        doc_stats = current_app.document_processor.get_document_stats(chunks)

        return jsonify({
            'success': True,
            'filename': filename,
            'chunks_created': num_added,
            'stats': doc_stats
        })

    except Exception as e:
        logger.exception("Failed to process upload %s", filename)
        return _cleanup_and_error(filepath, str(e))


@documents_bp.route('/stats')
def get_stats():
    """Get vector store statistics"""
    stats = current_app.vector_store.get_stats()
    stats['has_api'] = current_app.rag_engine.has_api
    return jsonify(stats)


@documents_bp.route('/clear_documents', methods=['POST'])
def clear_documents():
    """Clear all documents from vector store"""
    try:
        current_app.vector_store.clear_all()

        upload_folder = current_app.config['UPLOAD_FOLDER']
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

        return jsonify({
            'success': True,
            'message': 'All documents cleared'
        })

    except Exception as e:
        logger.exception("Failed to clear documents")
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/delete_document', methods=['POST'])
def delete_document():
    """Delete a specific document"""
    try:
        payload = DeleteDocumentRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({'error': e.errors()[0]['msg'] if e.errors() else str(e)}), 400

    try:
        deleted_count = current_app.vector_store.delete_by_source(payload.source)

        return jsonify({
            'success': True,
            'deleted_chunks': deleted_count,
            'message': f'Deleted {deleted_count} chunks from {payload.source}'
        })

    except Exception as e:
        logger.exception("Failed to delete document %s", payload.source)
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/sample_questions')
def get_sample_questions():
    """Get sample questions based on uploaded documents"""
    stats = current_app.vector_store.get_stats()

    if stats['total_chunks'] == 0:
        return jsonify([
            "Upload a document to get started!",
            "Try uploading a PDF, DOCX, or TXT file",
            "Then ask questions about its content"
        ])

    samples = [
        "What are the main topics covered in these documents?",
        "Can you summarize the key points?",
        "What are the most important takeaways?",
        "Are there any specific recommendations or conclusions?",
        "What details are provided about [specific topic]?"
    ]

    return jsonify(samples)
