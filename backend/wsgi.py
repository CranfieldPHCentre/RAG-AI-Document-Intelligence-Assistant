"""
Production entrypoint, e.g.: waitress-serve --listen=0.0.0.0:5000 wsgi:app
"""

from app import create_app

app = create_app()
