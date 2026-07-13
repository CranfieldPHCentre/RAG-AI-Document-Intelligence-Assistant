"""
Query routes: ask a question against the document store (regular + streaming)
"""

import json
import logging
from typing import List, Dict, Optional

from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from pydantic import ValidationError

from config import Config
from extensions import limiter
from schemas import QueryRequest

logger = logging.getLogger(__name__)

query_bp = Blueprint('query', __name__, url_prefix='/api')


def _parse_request() -> QueryRequest:
    return QueryRequest.model_validate(request.get_json(silent=True) or {})


def _history_for(payload: QueryRequest) -> Optional[List[Dict]]:
    if not payload.use_context or not payload.history:
        return None
    return [turn.model_dump() for turn in payload.history]


def _no_documents_response():
    return jsonify({'error': 'No documents uploaded yet. Please upload documents first.'}), 400


@query_bp.route('/query', methods=['POST'])
@limiter.limit(Config.QUERY_RATE_LIMIT)
def query():
    """Handle a single-shot user query"""
    try:
        payload = _parse_request()
    except ValidationError as e:
        return jsonify({'error': e.errors()[0]['msg'] if e.errors() else str(e)}), 400

    stats = current_app.vector_store.get_stats()
    if stats['total_chunks'] == 0:
        return _no_documents_response()

    try:
        result = current_app.rag_engine.query(
            question=payload.question,
            n_results=payload.n_results,
            use_hybrid=payload.use_hybrid,
            history=_history_for(payload)
        )
        return jsonify(result)
    except Exception as e:
        logger.exception("Query failed")
        return jsonify({'error': str(e)}), 500


@query_bp.route('/query/stream', methods=['POST'])
@limiter.limit(Config.QUERY_RATE_LIMIT)
def query_stream():
    """Handle a user query, streaming the answer back as Server-Sent Events"""
    try:
        payload = _parse_request()
    except ValidationError as e:
        return jsonify({'error': e.errors()[0]['msg'] if e.errors() else str(e)}), 400

    stats = current_app.vector_store.get_stats()
    if stats['total_chunks'] == 0:
        return _no_documents_response()

    rag_engine = current_app.rag_engine
    history = _history_for(payload)

    def generate():
        try:
            for event in rag_engine.query_stream(
                question=payload.question,
                n_results=payload.n_results,
                use_hybrid=payload.use_hybrid,
                history=history
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("Streaming query failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
