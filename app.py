import atexit
from flask import Flask, jsonify, request, redirect, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from db import DB
from service import Shortener

app = Flask(__name__, static_folder="static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
svc = Shortener(DB())
atexit.register(svc.flush_clicks)


def view(rec):
    return {"code": rec["code"], "long_url": rec["long_url"], "clicks": rec["clicks"],
            "short_url": request.host_url + rec["code"], "expires_at": rec["expires_at"]}


@app.get("/")
def home():
    return send_from_directory("static", "index.html")


@app.post("/api/shorten")
def shorten():
    d = request.get_json(silent=True) or {}
    try:
        ttl = int(d["ttl"]) if d.get("ttl") else None
        code = svc.shorten((d.get("url") or "").strip(), (d.get("alias") or "").strip() or None, ttl)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(code=code, short_url=request.host_url + code)


@app.get("/api/stats/<code>")
def stats(code):
    rec = svc.stats(code)
    return (jsonify(view(rec)) if rec else (jsonify(error="Not found"), 404))


@app.get("/api/top")
def top():
    return jsonify([view(r) for r in svc.top()])


@app.get("/api/recent")
def recent():
    return jsonify([view(r) for r in svc.recent_links()])


@app.get("/api/search")
def search():
    return jsonify(svc.search(request.args.get("prefix", "")))


@app.get("/api/related/<code>")
def related(code):
    return jsonify(svc.related(code))


@app.post("/api/undo")
def undo():
    code = svc.undo()
    return jsonify(undone=code) if code else (jsonify(error="Nothing to undo"), 404)


@app.get("/api/info")
def info():
    return jsonify(svc.info())


@app.get("/api/benchmark")
def benchmark():
    return jsonify(Shortener.benchmark())


@app.get("/<code>")
def go(code):
    url = svc.resolve(code)
    if url:
        return redirect(url, 302)
    return jsonify(error="Link not found or expired"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
