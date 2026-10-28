import time
import io
import streamlit as st
import qrcode
import cv2
import numpy as np

# Page Configuration
st.set_page_config(page_title="URL Shortener System", page_icon="🔗", layout="centered")

BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DOMAIN = "http://shortlink/"


# ------------------------------------------------------------- Min-Heap Implementation
class MinHeap:
    def __init__(self):
        self.heap = []

    def __len__(self):
        return len(self.heap)

    def push(self, item):
        self.heap.append(item)
        self._sift_up(len(self.heap) - 1)

    def pop(self):
        if not self.heap:
            return None
        self._swap(0, len(self.heap) - 1)
        item = self.heap.pop()
        self._sift_down(0)
        return item

    def peek(self):
        return self.heap[0] if self.heap else None

    def _sift_up(self, idx):
        parent = (idx - 1) // 2
        while idx > 0 and self.heap[idx][0] < self.heap[parent][0]:
            self._swap(idx, parent)
            idx = parent
            parent = (idx - 1) // 2

    def _sift_down(self, idx):
        last = len(self.heap) - 1
        while (left := 2 * idx + 1) <= last:
            smallest = left
            right = left + 1
            if right <= last and self.heap[right][0] < self.heap[left][0]:
                smallest = right
            if self.heap[idx][0] <= self.heap[smallest][0]:
                break
            self._swap(idx, smallest)
            idx = smallest

    def _swap(self, i, j):
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]


# ---------------------------------------------------------------- Base62
def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62[rem])
    return "".join(reversed(chars))


def decode_base62(code: str) -> int:
    num = 0
    for ch in code:
        num = num * 62 + BASE62.index(ch)
    return num


# ------------------------------------------------------------ Hash Table
class HashTable:
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


# ------------------------------------------------------- QR Code Helpers
def generate_qr_code(url: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def decode_qr_code(image_bytes) -> str:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)
    return data if data else None


# ------------------------------------------------------- URL Shortener State
if "shortener" not in st.session_state:
    st.session_state.shortener = {
        "table": HashTable(),
        "reverse": HashTable(),
        "cache": LRUCache(3),
        "expiry_heap": MinHeap(),
        "counter": 100000,
        "cache_hits": 0,
        "cache_misses": 0
    }

s = st.session_state.shortener


def shorten_url(long_url, custom_alias=None, ttl=None):
    if not long_url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    if custom_alias is None and ttl is None and s["reverse"].contains(long_url):
        return DOMAIN + s["reverse"].get(long_url)

    if custom_alias:
        if s["table"].contains(custom_alias):
            raise ValueError(f"Alias '{custom_alias}' already taken")
        code = custom_alias
    else:
        code = encode_base62(s["counter"])
        s["counter"] += 1
        while s["table"].contains(code):
            code = encode_base62(s["counter"])
            s["counter"] += 1

    expires_at = time.time() + ttl if ttl else None
    s["table"].put(code, {"long": long_url, "clicks": 0, "expires_at": expires_at})
    if custom_alias is None and ttl is None:
        s["reverse"].put(long_url, code)
    if expires_at:
        s["expiry_heap"].push((expires_at, code))
    return DOMAIN + code


def resolve_url(short_url):
    code = short_url.replace(DOMAIN, "")
    # Purge expired
    now = time.time()
    while len(s["expiry_heap"]) and s["expiry_heap"].peek()[0] <= now:
        _, c = s["expiry_heap"].pop()
        s["table"].delete(c)
        s["cache"].delete(c)

    record = s["cache"].get(code)
    if record:
        s["cache_hits"] += 1
    else:
        s["cache_misses"] += 1
        record = s["table"].get(code)
        if record is None:
            return None
        s["cache"].put(code, record)

    record["clicks"] += 1
    return record["long"]


# ------------------------------------------------------------------ Web UI Layout
st.title("🔗 Dynamic URL Shortener & QR Studio")
st.markdown("### *DSA Micro-Project (Hash Table, Base62, LRU Cache, Min-Heap, QR Code)*")
st.markdown("---")

menu_option = st.sidebar.radio("📌 Navigation Menu", [
    "1. Shorten URL (Standard)",
    "2. Shorten URL (Custom Alias / TTL)",
    "3. Resolve / Open Short URL",
    "4. View Analytics & Stats",
    "5. System Cache & Metrics",
    "6. QR Code Generator & Scanner"
])

if menu_option == "1. Shorten URL (Standard)":
    st.subheader("🌐 Standard URL Shortener")
    long_url = st.text_input("Enter Long URL:", placeholder="https://www.google.com")
    if st.button("Generate Short URL", type="primary"):
        if long_url:
            with st.spinner("Encoding via Base62 & storing in Hash Table..."):
                time.sleep(0.5)
                try:
                    res = shorten_url(long_url)
                    st.success(f"Success! Short URL: `{res}`")
                except ValueError as e:
                    st.error(str(e))
        else:
            st.warning("Please enter a valid URL.")

elif menu_option == "2. Shorten URL (Custom Alias / TTL)":
    st.subheader("⚙️ Advanced Custom Shortener")
    long_url = st.text_input("Enter Long URL:", placeholder="https://github.com")
    custom_alias = st.text_input("Custom Alias (Optional):", placeholder="my-github")
    ttl = st.number_input("Expire TTL in seconds (0 for never):", min_value=0, value=0)

    if st.button("Create Advanced Short URL", type="primary"):
        if long_url:
            with st.spinner("Processing custom alias & heap expiry..."):
                time.sleep(0.5)
                try:
                    res = shorten_url(long_url, custom_alias.strip() or None, int(ttl) if ttl > 0 else None)
                    st.success(f"Success! Short URL: `{res}`")
                except ValueError as e:
                    st.error(str(e))
        else:
            st.warning("Please enter a valid URL.")

elif menu_option == "3. Resolve / Open Short URL":
    st.subheader("🚀 Resolve Short URL")
    short_url = st.text_input("Enter Short URL:", placeholder="http://sho.rt/1q")
    if st.button("Resolve & Redirect"):
        if short_url:
            with st.spinner("Checking LRU Cache and Hash Table..."):
                time.sleep(0.5)
                target = resolve_url(short_url)
                if target:
                    st.success(f"Redirects to: [{target}]({target})")
                else:
                    st.error("URL not found or has expired!")

elif menu_option == "4. View Analytics & Stats":
    st.subheader("📊 Link Analytics")
    short_url = st.text_input("Enter Short URL for Stats:", placeholder="http://sho.rt/1q")
    if st.button("Fetch Statistics"):
        if short_url:
            code = short_url.replace(DOMAIN, "")
            stats = s["table"].get(code)
            if stats:
                st.info(f"**Destination:** {stats['long']}")
                st.metric(label="Total Clicks", value=stats['clicks'])
                expires = stats['expires_at']
                st.write(f"**Expires At:** {time.ctime(expires) if expires else 'Never'}")
            else:
                st.error("URL not found.")

elif menu_option == "5. System Cache & Metrics":
    st.subheader("📈 Performance Metrics")
    col1, col2 = st.columns(2)
    col1.metric("Cache Hits", s["cache_hits"])
    col2.metric("Cache Misses", s["cache_misses"])
    st.write(f"**Total Active Stored URLs:** {s['table'].size}")

elif menu_option == "6. QR Code Generator & Scanner":
    st.subheader("📷 QR Code Studio")
    qr_tab1, qr_tab2 = st.tabs(["Generate QR Code", "Scan/Decode QR Code"])

    with qr_tab1:
        st.write("### Create QR Code from URL")
        url_input = st.text_input("Enter URL to encode into QR:", placeholder="http://sho.rt/1q")
        if st.button("Generate QR Image", type="primary"):
            if url_input:
                qr_bytes = generate_qr_code(url_input)
                st.image(qr_bytes, caption="Generated QR Code", width=250)
                st.download_button(
                    label="Download QR Code",
                    data=qr_bytes,
                    file_name="qrcode.png",
                    mime="image/png"
                )
            else:
                st.warning("Please provide a URL.")

    with qr_tab2:
        st.write("### Decode QR Code from Image")
        uploaded_file = st.file_uploader("Upload QR Code Image (PNG/JPG)", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            image_bytes = uploaded_file.read()
            st.image(image_bytes, caption="Uploaded QR Image", width=250)
            if st.button("Decode QR Code"):
                decoded_url = decode_qr_code(image_bytes)
                if decoded_url:
                    st.success(f"Successfully decoded! **URL:** [{decoded_url}]({decoded_url})")
                else:
                    st.error("Could not find or decode a QR code from this image.")