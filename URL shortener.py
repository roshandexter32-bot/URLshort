import time
import sys
from lu4_trees import MinHeap

BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DOMAIN = "http://sho.rt/"


# ---------------------------------------------------------------- Animation Helpers
def animate_loading(message="Processing"):
    """Displays a smooth terminal spinner animation."""
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(3):
        for char in chars:
            sys.stdout.write(f"\r  {char} {message}...")
            sys.stdout.flush()
            time.sleep(0.05)
    sys.stdout.write("\r" + " " * (len(message) + 15) + "\r")
    sys.stdout.flush()


# ---------------------------------------------------------------- Base62
def encode_base62(num: int) -> str:
    """Convert an integer ID into a Base62 string. O(log62 n)"""
    if num == 0:
        return BASE62[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62[rem])
    return "".join(reversed(chars))


def decode_base62(code: str) -> int:
    """Convert a Base62 string back to an integer ID."""
    num = 0
    for ch in code:
        num = num * 62 + BASE62.index(ch)
    return num


# ------------------------------------------------------------ Hash Table
class HashTable:
    """Hash table with separate chaining and auto-resize (load factor 0.75)."""

    def __init__(self, capacity=8):
        self.capacity = capacity
        self.size = 0
        self.buckets = [[] for _ in range(capacity)]

    def _hash(self, key: str) -> int:
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % self.capacity
        return h

    def put(self, key, value):
        bucket = self.buckets[self._hash(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self.size += 1
        if self.size / self.capacity > 0.75:
            self._resize()

    def get(self, key):
        for k, v in self.buckets[self._hash(key)]:
            if k == key:
                return v
        return None

    def delete(self, key) -> bool:
        bucket = self.buckets[self._hash(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                bucket.pop(i)
                self.size -= 1
                return True
        return False

    def contains(self, key) -> bool:
        return self.get(key) is not None

    def _resize(self):
        old = self.buckets
        self.capacity *= 2
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
        for bucket in old:
            for k, v in bucket:
                self.put(k, v)


# ------------------------------------------------------------- LRU Cache
class _Node:
    def __init__(self, key=None, value=None):
        self.key, self.value = key, value
        self.prev = self.next = None


class LRUCache:
    """O(1) get/put. Most recently used sits next to head; LRU sits next to tail."""

    def __init__(self, capacity=3):
        self.capacity = capacity
        self.map = HashTable()
        self.head, self.tail = _Node(), _Node()
        self.head.next, self.tail.prev = self.tail, self.head

    def _remove(self, node):
        node.prev.next, node.next.prev = node.next, node.prev

    def _add_front(self, node):
        node.next, node.prev = self.head.next, self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key):
        node = self.map.get(key)
        if node is None:
            return None
        self._remove(node)
        self._add_front(node)
        return node.value

    def put(self, key, value):
        node = self.map.get(key)
        if node:
            node.value = value
            self._remove(node)
            self._add_front(node)
            return
        if self.map.size >= self.capacity:
            lru = self.tail.prev
            self._remove(lru)
            self.map.delete(lru.key)
        node = _Node(key, value)
        self.map.put(key, node)
        self._add_front(node)

    def delete(self, key):
        node = self.map.get(key)
        if node:
            self._remove(node)
            self.map.delete(key)


# ------------------------------------------------------- URL Shortener
class URLShortener:
    def __init__(self, cache_size=3):
        self.table = HashTable()
        self.reverse = HashTable()
        self.cache = LRUCache(cache_size)
        self.expiry_heap = MinHeap()
        self.counter = 100000
        self.cache_hits = 0
        self.cache_misses = 0

    def shorten(self, long_url: str, custom_alias: str = None, ttl: int = None) -> str:
        if not long_url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        animate_loading("Generating Base62 Code & Updating Hash Table")

        if custom_alias is None and ttl is None and self.reverse.contains(long_url):
            print("  ℹ️ Existing short URL found in reverse index. Reusing...")
            return DOMAIN + self.reverse.get(long_url)

        if custom_alias:
            if self.table.contains(custom_alias):
                raise ValueError(f"Alias '{custom_alias}' already taken")
            code = custom_alias
        else:
            code = encode_base62(self.counter)
            self.counter += 1
            while self.table.contains(code):
                code = encode_base62(self.counter)
                self.counter += 1

        expires_at = time.time() + ttl if ttl else None
        self.table.put(code, {"long": long_url, "clicks": 0, "expires_at": expires_at})
        if custom_alias is None and ttl is None:
            self.reverse.put(long_url, code)
        if expires_at:
            animate_loading("Pushing Expiry Deadline to Min-Heap")
            self.expiry_heap.push((expires_at, code))
        return DOMAIN + code

    def resolve(self, short_url: str):
        code = short_url.replace(DOMAIN, "")
        self.purge_expired()

        animate_loading("Checking LRU Cache & Hash Table Lookup")
        record = self.cache.get(code)
        if record:
            self.cache_hits += 1
            print("  ⚡ [Cache HIT!] Retrieved in O(1) time.")
        else:
            self.cache_misses += 1
            print("  🐢 [Cache MISS] Fetched from Hash Table & Loaded into LRU Cache.")
            record = self.table.get(code)
            if record is None:
                return None
            self.cache.put(code, record)

        record["clicks"] += 1
        return record["long"]

    def purge_expired(self):
        now = time.time()
        while len(self.expiry_heap) and self.expiry_heap.peek()[0] <= now:
            _, code = self.expiry_heap.pop()
            self.table.delete(code)
            self.cache.delete(code)

    def stats(self, short_url: str):
        animate_loading("Fetching Link Statistics")
        return self.table.get(short_url.replace(DOMAIN, ""))


# ------------------------------------------------------------------ CLI Menu
def demo():
    s = URLShortener(cache_size=2)
    print("\n⚡ [ANNOUNCEMENT] Running Animated Demonstration ⚡")
    animate_loading("Initializing System")

    a = s.shorten("https://www.google.com/search?q=data+structures")
    b = s.shorten("https://github.com/")
    print(f"\n  ✨ Shortened URLs Created:\n    1. {a}\n    2. {b}")

    print("\n== Testing LRU Cache & Animations ==")
    for u in (a, b, a):
        print(f"\nResolving: {u}")
        s.resolve(u)
        time.sleep(0.5)


def menu():
    s = URLShortener()
    while True:
        print("\n" + "=" * 45)
        print(" 🔗 DYNAMIC URL SHORTENER - DSA PROJECT (LU-III, IV)")
        print("=" * 45)
        print(" 1. Shorten URL (Standard)")
        print(" 2. Shorten URL (Custom Alias / Expiry TTL)")
        print(" 3. Resolve / Open Short URL")
        print(" 4. View Analytics & Stats")
        print(" 5. Run Animated Demo")
        print(" 6. Exit")
        print("-" * 45)

        ch = input("👉 Select Option (1-6): ").strip()
        try:
            if ch == "1":
                url = input("Enter Long URL: ").strip()
                res = s.shorten(url)
                print(f"\n✅ Success! Short URL: {res}")
            elif ch == "2":
                u = input("Enter Long URL: ").strip()
                alias = input("Custom alias (leave blank for none): ").strip() or None
                ttl = input("Expire in seconds (leave blank for never): ").strip()
                res = s.shorten(u, alias, int(ttl) if ttl else None)
                print(f"\n✅ Success! Short URL: {res}")
            elif ch == "3":
                u = input("Enter Short URL (e.g., http://sho.rt/abc): ").strip()
                r = s.resolve(u)
                if r:
                    print(f"\n🚀 Redirecting to -> {r}")
                else:
                    print("\n❌ Error: Short URL not found or has expired.")
            elif ch == "4":
                u = input("Enter Short URL to check stats: ").strip()
                st = s.stats(u)
                if st:
                    print(f"\n📊 Stats for {u}:")
                    print(f"   • Destination: {st['long']}")
                    print(f"   • Total Clicks: {st['clicks']}")
                    print(f"   • Expires At: {st['expires_at'] if st['expires_at'] else 'Never'}")
                else:
                    print("\n❌ Error: URL not found.")
            elif ch == "5":
                demo()
            elif ch == "6":
                print("\nExiting system. Goodbye! 👋")
                break
            else:
                print("\n❌ Invalid choice. Please choose between 1 and 6.")
        except ValueError as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    menu()