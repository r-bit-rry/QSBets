import os
from datetime import datetime
from functools import wraps
import hashlib
from typing import Any, Callable, Optional, Union
from diskcache import Cache
from logger import get_logger

logger = get_logger(__name__)

HOURS2_TTL = 7200  # 2 hours
DAY_TTL = 86400  # 1 day
WEEK_TTL = 604800  # 7 days
MONTH_TTL = 2592000  # 30 days

# Create cache directory if it doesn't exist
CACHE_DIR = "./.cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Initialize the diskcache Cache instance
cache_instance = Cache(CACHE_DIR)

def generate_cache_key(func: Callable, args: tuple, kwargs: dict, prefix: Optional[str] = None) -> str:
    """Generate a unique cache key based on function name, args, and kwargs."""
    key_parts = [func.__name__]
    if prefix:
        key_parts.insert(0, prefix)
    
    key_parts.extend([str(arg) for arg in args])
    key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    
    key_string = "_".join(key_parts)
    return hashlib.md5(key_string.encode('utf-8')).hexdigest()

def cached(ttl_seconds: int = 1800, cache_key: Optional[str] = None) -> Callable:
    """
    Decorator that caches function results with a specified TTL using diskcache.
    
    Args:
        ttl_seconds: Time to live in seconds (default 30 minutes)
        cache_key: Optional custom cache key prefix
    
    Usage:
        @cached(ttl_seconds=3600)
        def my_function(arg1, arg2):
            ...
        
        @cached(ttl_seconds=1800, cache_key="custom_prefix")
        def another_function(arg1, arg2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                # Generate cache key
                actual_cache_key = cache_key or generate_cache_key(func, args, kwargs)
                
                # Try to get from cache
                with cache_instance as cache:
                    if actual_cache_key in cache:
                        return cache[actual_cache_key]
                    
                    # Execute function and cache result with TTL
                    result = func(*args, **kwargs)
                    cache.set(actual_cache_key, result, expire=ttl_seconds)
                    return result
                    
            except Exception as e:
                logger.error(f"Cache error in {func.__name__}: {str(e)}")
                # On cache error, execute function without caching
                return func(*args, **kwargs)
            
        return wrapper
    return decorator

def clear_cache(cache_key: Optional[str] = None) -> None:
    """
    Clear specific cache key or entire cache.
    
    Args:
        cache_key: Optional specific cache key to clear
    """
    try:
        with cache_instance as cache:
            if cache_key:
                if cache_key in cache:
                    del cache[cache_key]
            else:
                cache.clear()
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")

def get_cache_stats() -> dict[str, Union[int, list[str]]]:
    """
    Get statistics about current cache usage.
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        with cache_instance as cache:
            stats = {
                'size': len(cache),
                'directory': cache.directory,
                'max_size': cache.size_limit,
                'cull_limit': cache.cull_limit,
            }
            return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {'error': str(e)}
