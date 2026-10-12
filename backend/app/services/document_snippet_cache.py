"""Small process-local cache for headlines after owner-scoped row selection."""
from collections import OrderedDict
import threading
import time


class SnippetCache:
    def __init__(self, *, max_entries=512, ttl_seconds=120):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return False, None
            expires, value = entry
            if expires <= time.monotonic():
                del self.entries[key]
                return False, None
            self.entries.move_to_end(key)
            return True, value

    def put(self, key, value):
        # Large/unusual headlines remain uncached; response behavior is unchanged.
        if value is not None and len(value.encode('utf-8')) > 8192:
            return
        with self.lock:
            self.entries[key] = (time.monotonic() + self.ttl_seconds, value)
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)


snippet_cache = SnippetCache()
