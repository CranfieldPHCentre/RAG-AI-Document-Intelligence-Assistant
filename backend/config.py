"""
Application configuration, read from environment variables (see .env.example)
"""

import os


class Config:
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    VECTOR_DB_PATH = os.environ.get('VECTOR_DB_PATH', 'vector_db')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md'}
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB

    FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'http://localhost:8080')

    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 1000))
    CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', 200))

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Rate limits (Flask-Limiter syntax), tune via env for deployments
    UPLOAD_RATE_LIMIT = os.environ.get('UPLOAD_RATE_LIMIT', '20 per minute')
    QUERY_RATE_LIMIT = os.environ.get('QUERY_RATE_LIMIT', '60 per minute')

    # Max number of client-supplied conversation turns the server will actually use
    MAX_HISTORY_TURNS = int(os.environ.get('MAX_HISTORY_TURNS', 6))
