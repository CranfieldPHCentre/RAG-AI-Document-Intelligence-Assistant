"""
Shared Flask extension instances (avoids circular imports between app.py and routes/)
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
