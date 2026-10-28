"""Core URL shortener logic - ties all data structures together."""
import re
import time
import heapq
import threading
from functools import wraps
from urllib.parse import urlparse

from dsa import (HashTable, LRUCache, Stack, CircularQueue, LinkedList, Trie, Graph,
                 encode_base62, merge_sort, linear_search, binary_search)

ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")
RESERVED = {"api", "static", "favicon.ico"}


def synchronized(fn):
    @wraps(fn)
    def wrapper(self, *a, **kw):
        with self.lock:
            return fn(self, *a, **kw)
    return wrapper


class Shortener:
    def __init__(self, db, cache_size=5, queue_size=5):
        self.db = db
        self.lock = threading.RLock()
        self.table = HashTable()                 # CO3  code -> record
        self.reverse = HashTable()               # CO3  long url -> code
        self.cache = LRUCache(cache_size)        # CO2/3 hot links
        self.expiry_heap = []                    # min-heap of (expires_at, code)
        self.undo_stack = Stack()                # CO1
        self.click_queue = CircularQueue(queue_size)  # CO1
        self.recent = LinkedList()               # CO2
        self.trie = Trie()                       # CO4
        self.graph = Graph()                     # CO5
        self.hits = self.misses = 0
        self.counter = 100000
        self._load()

    # ---- startup: rebuild in-memory structures from Supabase
    def _load(self):
        rows = self.db.load_all() or []
        rows.sort(key=lambda r: r.get("created_at") or "")
        for r in rows:
            self._index({"code": r["code"], "long_url": r["long_url"],
                         "clicks": r.get("clicks") or 0, "expires_at": r.get("expires_at")})
        self.counter = 100000 + len(rows)

    def _index(self, rec):
        code = rec["code"]
        self.table.put(code, rec)
        self.trie.insert(code)
        self.recent.add_front(code)
        host = urlparse(rec["long_url"]).netloc
        self.graph.add_edge("L:" + code, "D:" + host)
        if rec["expires_at"]:
            heapq.heappush(self.expiry_heap, (rec["expires_at"], code))
        else:
            self.reverse.put(rec["long_url"], code)

    # ---- core features
    @synchronized
    def shorten(self, long_url, alias=None, ttl=None):
        parsed = urlparse(long_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Enter a full URL starting with http:// or https://")
        if alias is None and ttl is None and self.reverse.contains(long_url):
            return self.reverse.get(long_url)

        if alias:
            if not ALIAS_RE.match(alias):
                raise ValueError("Alias must be 3-30 letters, digits, - or _")
            if alias in RESERVED or self.table.contains(alias):
                raise ValueError(f"Alias '{alias}' is already taken")
            code = alias
        else:
            code = encode_base62(self.counter)
            self.counter += 1
            while self.table.contains(code):
                code = encode_base62(self.counter)
                self.counter += 1

        expires_at = time.time() + ttl if ttl else None
        rec = {"code": code, "long_url": long_url, "clicks": 0, "expires_at": expires_at}
        self._index(rec)
        self.undo_stack.push(code)
        self.db.insert(rec)
        return code

    @synchronized
    def resolve(self, code):
        self.purge_expired()
        rec = self.cache.get(code)
        if rec:
            self.hits += 1
        else:
            self.misses += 1
            rec = self.table.get(code)
            if rec is None:
                return None
            self.cache.put(code, rec)
        rec["clicks"] += 1
        if self.click_queue.is_full():
            self.flush_clicks()
        self.click_queue.enqueue(code)
        return rec["long_url"]

    @synchronized
    def flush_clicks(self):
        """Drain the circular queue and write updated click counts to Supabase."""
        touched = set()
        while not self.click_queue.is_empty():
            touched.add(self.click_queue.dequeue())
        for code in touched:
            rec = self.table.get(code)
            if rec:
                self.db.update_clicks(code, rec["clicks"])
        return len(touched)

    @synchronized
    def purge_expired(self):
        now = time.time()
        while self.expiry_heap and self.expiry_heap[0][0] <= now:
            _, code = heapq.heappop(self.expiry_heap)
            self._remove(code)

    def _remove(self, code):
        rec = self.table.get(code)
        if not rec:
            return False
        self.table.delete(code)
        self.cache.delete(code)
        self.trie.remove(code)
        self.graph.remove_node("L:" + code)
        self.recent.remove(code)
        if self.reverse.get(rec["long_url"]) == code:
            self.reverse.delete(rec["long_url"])
        self.db.delete(code)
        return True

    @synchronized
    def undo(self):
        while not self.undo_stack.is_empty():
            code = self.undo_stack.pop()
            if self._remove(code):
                return code
        return None

    # ---- read-only views
    @synchronized
    def stats(self, code):
        self.flush_clicks()
        return self.table.get(code)

    @synchronized
    def top(self, n=5):
        ranked = merge_sort(self.table.values(), key=lambda r: r["clicks"], reverse=True)
        return ranked[:n]

    @synchronized
    def recent_links(self, n=5):
        return [self.table.get(c) for c in self.recent.to_list(n)]

    @synchronized
    def search(self, prefix, limit=10):
        return self.trie.starts_with(prefix, limit)

    @synchronized
    def related(self, code):
        return [n[2:] for n in self.graph.bfs("L:" + code, 2) if n.startswith("L:")]

    @synchronized
    def info(self):
        total = self.hits + self.misses
        return {"links": self.table.size, "cache_keys": self.cache.keys(),
                "hits": self.hits, "misses": self.misses,
                "hit_rate": round(self.hits / total, 2) if total else 0,
                "pending_clicks_in_queue": self.click_queue.count,
                "hash_capacity": self.table.capacity,
                "database": "supabase" if self.db.enabled else "memory-only"}

    @staticmethod
    def benchmark(n=20000, trials=100):
        """Compare linear search, binary search and hash lookup on n codes."""
        codes = [encode_base62(100000 + i) for i in range(n)]
        t = time.perf_counter()
        sorted_codes = merge_sort(codes)
        sort_ms = (time.perf_counter() - t) * 1000
        ht = HashTable()
        for c in codes:
            ht.put(c, 1)
        target = codes[-1]  # worst case for linear search

        def timeit(fn):
            t = time.perf_counter()
            for _ in range(trials):
                fn()
            return round((time.perf_counter() - t) * 1000, 3)

        return {"n": n, "trials": trials, "merge_sort_ms": round(sort_ms, 2),
                "linear_ms": timeit(lambda: linear_search(codes, target)),
                "binary_ms": timeit(lambda: binary_search(sorted_codes, target)),
                "hash_ms": timeit(lambda: ht.get(target))}
