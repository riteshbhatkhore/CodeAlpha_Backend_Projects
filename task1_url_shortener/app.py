from flask import Flask, request, jsonify, redirect, render_template_string
import sqlite3
import string
import random
import os
from urllib.parse import urlparse

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "urls.db")

# ── Database setup ──────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT    UNIQUE NOT NULL,
                long_url   TEXT    NOT NULL,
                clicks     INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# ── Helper ───────────────────────────────────────────────────────────────────
def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        with get_db() as conn:
            row = conn.execute("SELECT id FROM urls WHERE short_code = ?", (code,)).fetchone()
        if not row:
            return code


def normalize_url(raw_url):
  url = raw_url.strip()
  if not url:
    return None

  parsed = urlparse(url)
  if not parsed.scheme:
    url = "https://" + url
    parsed = urlparse(url)

  if parsed.scheme not in {"http", "https"} or not parsed.netloc:
    return None

  return url

# ── Frontend (single-page) ────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CodeAlpha URL Shortener</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #f0f4ff; display: flex;
           justify-content: center; align-items: flex-start; min-height: 100vh; padding: 40px 20px; }
    .card { background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,.1);
            width: 100%; max-width: 600px; padding: 40px; }
    h1 { color: #3b5bdb; margin-bottom: 6px; }
    p.sub { color: #666; margin-bottom: 30px; }
    input[type=text] { width: 100%; padding: 12px 16px; border: 2px solid #dee2e6;
                        border-radius: 8px; font-size: 15px; outline: none; transition: border .2s; }
    input[type=text]:focus { border-color: #3b5bdb; }
    button { margin-top: 14px; width: 100%; padding: 13px; background: #3b5bdb;
             color: white; border: none; border-radius: 8px; font-size: 16px;
             cursor: pointer; transition: background .2s; }
    button:hover { background: #2f4abf; }
    .result { margin-top: 24px; padding: 16px; background: #f0f4ff;
              border-radius: 8px; display: none; }
    .result a { color: #3b5bdb; font-weight: 600; word-break: break-all; }
    .error { color: #e03131; margin-top: 10px; font-size: 14px; display: none; }
    table { width: 100%; border-collapse: collapse; margin-top: 30px; font-size: 14px; }
    th { background: #3b5bdb; color: white; padding: 10px 12px; text-align: left; }
    td { padding: 9px 12px; border-bottom: 1px solid #e9ecef; word-break: break-all; }
    tr:hover td { background: #f8f9ff; }
  </style>
</head>
<body>
<div class="card">
  <h1>🔗 URL Shortener</h1>
  <p class="sub">Shorten any long URL instantly</p>

  <input type="text" id="longUrl" placeholder="Paste your long URL here..." />
  <button onclick="shorten()">Shorten URL</button>

  <div class="error" id="error"></div>
  <div class="result" id="result">
    ✅ Short URL: <a id="shortLink" href="#" target="_blank"></a>
  </div>

  <table id="statsTable" style="display:none">
    <thead><tr><th>Short Code</th><th>Original URL</th><th>Clicks</th><th>Created</th></tr></thead>
    <tbody id="statsBody"></tbody>
  </table>
</div>

<script>
  const BASE = window.location.origin;

  async function shorten() {
    const url = document.getElementById('longUrl').value.trim();
    document.getElementById('error').style.display = 'none';
    document.getElementById('result').style.display = 'none';
    if (!url) { showError('Please enter a URL.'); return; }
    const res = await fetch('/shorten', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({long_url: url})
    });
    const data = await res.json();
    if (!res.ok) { showError(data.error || 'Something went wrong'); return; }
    const link = `${BASE}/${data.short_code}`;
    document.getElementById('shortLink').href = link;
    document.getElementById('shortLink').textContent = link;
    document.getElementById('result').style.display = 'block';
    loadStats();
  }

  function showError(msg) {
    const el = document.getElementById('error');
    el.textContent = msg;
    el.style.display = 'block';
  }

  async function loadStats() {
    const res = await fetch('/stats');
    const data = await res.json();
    if (!data.length) return;
    const tbody = document.getElementById('statsBody');
    tbody.innerHTML = data.map(r => `
      <tr>
        <td><a href="${BASE}/${r.short_code}" target="_blank">${r.short_code}</a></td>
        <td><a href="${r.long_url}" target="_blank">${r.long_url.substring(0,60)}${r.long_url.length>60?'...':''}</a></td>
        <td>${r.clicks}</td>
        <td>${r.created_at}</td>
      </tr>`).join('');
    document.getElementById('statsTable').style.display = 'table';
  }

  loadStats();
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json()
    long_url = (data or {}).get("long_url", "").strip()
    if not long_url:
        return jsonify({"error": "long_url is required"}), 400

    long_url = normalize_url(long_url)
    if not long_url:
        return jsonify({"error": "Please enter a valid http or https URL."}), 400

    for _ in range(5):
        short_code = generate_code()
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO urls (short_code, long_url) VALUES (?, ?)", (short_code, long_url))
                conn.commit()
            break
        except sqlite3.IntegrityError:
            continue
    else:
        return jsonify({"error": "Could not generate a unique short code."}), 500

    return jsonify({"short_code": short_code, "long_url": long_url}), 201

@app.route("/<short_code>")
def redirect_url(short_code):
    with get_db() as conn:
        row = conn.execute("SELECT long_url FROM urls WHERE short_code = ?", (short_code,)).fetchone()
        if not row:
            return jsonify({"error": "Short URL not found"}), 404
        conn.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,))
        conn.commit()
    return redirect(row["long_url"])

@app.route("/stats")
def stats():
    with get_db() as conn:
        rows = conn.execute("SELECT short_code, long_url, clicks, created_at FROM urls ORDER BY id DESC LIMIT 20").fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)


init_db()
