from slowapi import Limiter

from app.auth.security import client_key

limiter = Limiter(key_func=client_key)
