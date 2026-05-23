import time
from functools import wraps

_cache = {}

def cached(ttl=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in _cache:
                value, expiry = _cache[key]
                if now < expiry:
                    return value
            result = func(*args, **kwargs)
            _cache[key] = (result, now + ttl)
            return result
        return wrapper
    return decorator

def clear_cache():
    _cache.clear()
