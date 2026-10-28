# URL Shortener System (DSA Micro Project, 23CS2011)

Flask web app. All core data structures are written from scratch in `dsa.py`; Supabase (Postgres) stores the links permanently.

## How the 5 course outcomes are covered
| CO | Practicum | Where in the project |
|----|-----------|----------------------|
| CO1 | Stack | "Undo last link" (`Stack`) |
| CO1 | Queue / Circular Queue | Click-event buffer flushed to DB in batches (`CircularQueue`) |
| CO2 | Linked list | "Recently created" list with add/remove (`LinkedList`) and LRU cache list |
| CO2 | Searching in sorted list | `binary_search` on sorted codes |
| CO3 | Hash table + collision resolution | `HashTable` (chaining + resizing), main store |
| CO3 | Search performance on large data | `/api/benchmark` (linear vs binary vs hash, 20,000 codes) |
| CO3 | Sorting | `merge_sort` for "Most clicked" |
| CO4 | Tree structure for hierarchical data | `Trie` for prefix search of codes |
| CO5 | Graph (adjacency list) + routing/connectivity | `Graph` links <-> domains, BFS "related links" |

## Run locally
```
pip install -r requirements.txt
cp .env.example .env      # fill in Supabase values, then export them
python app.py             # http://localhost:5000
```
Without Supabase variables it runs in memory-only mode.

## Setup Supabase
1. supabase.com -> New project.
2. SQL Editor -> paste `schema.sql` -> Run.
3. Project Settings -> API: copy the Project URL and the **secret / service_role** key.

## Deploy on Render
1. render.com -> New -> Web Service -> connect this GitHub repo.
2. Build: `pip install -r requirements.txt`
3. Start: `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`
4. Add env vars `SUPABASE_URL` and `SUPABASE_KEY`.

Keep `--workers 1`: the in-memory structures live inside one process.
