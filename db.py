"""Supabase persistence layer. Falls back to memory-only if env vars are missing."""
import os

try:
    from supabase import create_client
except ImportError:
    create_client = None


class DB:
    def __init__(self):
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        self.client = create_client(url, key) if (url and key and create_client) else None
        print("Supabase connected" if self.client else "No Supabase config -> memory-only mode")

    @property
    def enabled(self):
        return self.client is not None

    def _run(self, fn, default=None):
        if not self.enabled:
            return default
        try:
            return fn()
        except Exception as e:
            print("DB error:", e)
            return default

    def load_all(self):
        return self._run(lambda: self.client.table("urls").select("*").execute().data, [])

    def insert(self, rec):
        self._run(lambda: self.client.table("urls").insert(rec).execute())

    def update_clicks(self, code, clicks):
        self._run(lambda: self.client.table("urls").update({"clicks": clicks}).eq("code", code).execute())

    def delete(self, code):
        self._run(lambda: self.client.table("urls").delete().eq("code", code).execute())
