"""
DSA building blocks - every structure below is written from scratch.

Structure        Used for                                   Syllabus CO
---------------  -----------------------------------------  -----------
Stack            "Undo last link" feature                   CO1
CircularQueue    Click-event buffer (batch DB updates)      CO1
LinkedList       Recently created links (add/remove)        CO2
binary_search    Locate a code in a sorted list             CO2
HashTable        code -> record lookup, chaining + resize   CO3
merge_sort       Top links ranked by clicks                 CO3
Trie             Prefix search on short codes / aliases     CO4
Graph            Link <-> domain graph, BFS related links   CO5
LRUCache         Hot-link cache (linked list + hash table)  CO2 + CO3
"""

BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62[0]
    out = []
    while num > 0:
        num, rem = divmod(num, 62)
        out.append(BASE62[rem])
    return "".join(reversed(out))


def decode_base62(code: str) -> int:
    num = 0
    for ch in code:
        num = num * 62 + BASE62.index(ch)
    return num


# ------------------------------------------------------------ CO1: Stack
class Stack:
    def __init__(self):
        self.items = []

    def push(self, x):
        self.items.append(x)

    def pop(self):
        if not self.items:
            raise IndexError("stack is empty")
        return self.items.pop()

    def peek(self):
        return self.items[-1] if self.items else None

    def is_empty(self):
        return not self.items

    def __len__(self):
        return len(self.items)


# ------------------------------------------------- CO1: Circular Queue
class CircularQueue:
    def __init__(self, capacity):
        self.cap = capacity
        self.data = [None] * capacity
        self.front = 0
        self.count = 0

    def is_full(self):
        return self.count == self.cap

    def is_empty(self):
        return self.count == 0

    def enqueue(self, x):
        if self.is_full():
            raise OverflowError("queue is full")
        self.data[(self.front + self.count) % self.cap] = x
        self.count += 1

    def dequeue(self):
        if self.is_empty():
            raise IndexError("queue is empty")
        x = self.data[self.front]
        self.data[self.front] = None
        self.front = (self.front + 1) % self.cap
        self.count -= 1
        return x


# ------------------------------------------------- CO2: Singly Linked List
class _LNode:
    def __init__(self, val):
        self.val = val
        self.next = None


class LinkedList:
    def __init__(self):
        self.head = None
        self.size = 0

    def add_front(self, val):
        node = _LNode(val)
        node.next = self.head
        self.head = node
        self.size += 1

    def remove(self, val) -> bool:
        prev, cur = None, self.head
        while cur:
            if cur.val == val:
                if prev:
                    prev.next = cur.next
                else:
                    self.head = cur.next
                self.size -= 1
                return True
            prev, cur = cur, cur.next
        return False

    def to_list(self, limit=None):
        out, cur = [], self.head
        while cur and (limit is None or len(out) < limit):
            out.append(cur.val)
            cur = cur.next
        return out


# --------------------------------------------------- CO2: Searching
def linear_search(arr, target) -> int:
    for i, x in enumerate(arr):
        if x == target:
            return i
    return -1


def binary_search(sorted_arr, target) -> int:
    lo, hi = 0, len(sorted_arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_arr[mid] == target:
            return mid
        if sorted_arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


# ------------------------------------------------- CO3: Hash Table
class HashTable:
    """Separate chaining, doubles capacity when load factor > 0.75."""

    def __init__(self, capacity=16):
        self.capacity = capacity
        self.size = 0
        self.buckets = [[] for _ in range(capacity)]

    def _hash(self, key):
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

    def contains(self, key):
        return self.get(key) is not None

    def values(self):
        return [v for b in self.buckets for _, v in b]

    def _resize(self):
        old = self.buckets
        self.capacity *= 2
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
        for bucket in old:
            for k, v in bucket:
                self.put(k, v)


# ------------------------------------------------- CO3: Merge Sort
def merge_sort(arr, key=lambda x: x, reverse=False):
    if len(arr) <= 1:
        return arr[:]
    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key, reverse)
    right = merge_sort(arr[mid:], key, reverse)
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        take_left = a >= b if reverse else a <= b
        if take_left:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out


# ------------------------------------------------- CO2/CO3: LRU Cache
class _DNode:
    def __init__(self, key=None, value=None):
        self.key, self.value = key, value
        self.prev = self.next = None


class LRUCache:
    """Doubly linked list (recency order) + hash table (O(1) access)."""

    def __init__(self, capacity=5):
        self.capacity = capacity
        self.map = HashTable()
        self.head, self.tail = _DNode(), _DNode()
        self.head.next, self.tail.prev = self.tail, self.head

    def _remove(self, n):
        n.prev.next, n.next.prev = n.next, n.prev

    def _add_front(self, n):
        n.next, n.prev = self.head.next, self.head
        self.head.next.prev = n
        self.head.next = n

    def get(self, key):
        n = self.map.get(key)
        if n is None:
            return None
        self._remove(n)
        self._add_front(n)
        return n.value

    def put(self, key, value):
        n = self.map.get(key)
        if n:
            n.value = value
            self._remove(n)
            self._add_front(n)
            return
        if self.map.size >= self.capacity:
            lru = self.tail.prev
            self._remove(lru)
            self.map.delete(lru.key)
        n = _DNode(key, value)
        self.map.put(key, n)
        self._add_front(n)

    def delete(self, key):
        n = self.map.get(key)
        if n:
            self._remove(n)
            self.map.delete(key)

    def keys(self):
        out, cur = [], self.head.next
        while cur is not self.tail:
            out.append(cur.key)
            cur = cur.next
        return out


# ------------------------------------------------- CO4: Trie (tree)
class Trie:
    def __init__(self):
        self.root = {}

    def insert(self, word):
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node["$"] = True

    def remove(self, word):
        node = self.root
        for ch in word:
            node = node.get(ch)
            if node is None:
                return
        node.pop("$", None)

    def starts_with(self, prefix, limit=10):
        node = self.root
        for ch in prefix:
            node = node.get(ch)
            if node is None:
                return []
        results = []
        self._collect(node, prefix, results, limit)
        return results

    def _collect(self, node, path, results, limit):
        if len(results) >= limit:
            return
        if "$" in node:
            results.append(path)
        for ch in sorted(k for k in node if k != "$"):
            self._collect(node[ch], path + ch, results, limit)


# ------------------------------------------------- CO5: Graph
class Graph:
    """Undirected graph as an adjacency list."""

    def __init__(self):
        self.adj = {}

    def add_edge(self, u, v):
        self.adj.setdefault(u, set()).add(v)
        self.adj.setdefault(v, set()).add(u)

    def remove_node(self, u):
        for v in self.adj.pop(u, set()):
            self.adj[v].discard(u)
            if not self.adj[v]:
                del self.adj[v]

    def bfs(self, start, max_depth):
        if start not in self.adj:
            return []
        seen, order = {start}, []
        queue, i = [(start, 0)], 0
        while i < len(queue):
            node, d = queue[i]; i += 1
            if d == max_depth:
                continue
            for nb in sorted(self.adj[node]):
                if nb not in seen:
                    seen.add(nb)
                    order.append(nb)
                    queue.append((nb, d + 1))
        return order
