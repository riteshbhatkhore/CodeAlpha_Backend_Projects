from flask import Flask, request, jsonify, render_template_string
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "events.db")

# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT,
                location    TEXT,
                event_date  TEXT NOT NULL,
                capacity    INTEGER DEFAULT 100,
                organizer   TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                event_id    INTEGER NOT NULL REFERENCES events(id),
                status      TEXT DEFAULT 'confirmed',
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id)
            );
        """)
        conn.commit()
    _seed_events()

def _seed_events():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO events (title, description, location, event_date, capacity, organizer) VALUES (?,?,?,?,?,?)",
                [
                    ("Tech Summit 2025", "Annual technology conference with workshops and keynotes.",
                     "Mumbai Convention Centre", "2025-09-15", 500, "CodeAlpha"),
                    ("Flask Workshop", "Hands-on backend development with Flask and SQLite.",
                     "Online / Zoom", "2025-08-10", 100, "CodeAlpha"),
                    ("Hackathon 4.0", "48-hour coding challenge open to all students.",
                     "Pune Tech Park", "2025-10-05", 200, "CodeAlpha"),
                ]
            )
            conn.commit()


init_db()

# ── Frontend ──────────────────────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CodeAlpha Event Registration</title>
  <style>
    * { box-sizing: border-box; margin:0; padding:0; }
    body { font-family:'Segoe UI',sans-serif; background:#f5f7ff; color:#333; }
    header { background:#2563eb; color:white; padding:20px 40px; }
    header h1 { font-size:24px; } header p { opacity:.8; font-size:14px; }
    .container { max-width:960px; margin:30px auto; padding:0 20px; }
    .tabs { display:flex; gap:8px; margin-bottom:24px; }
    .tab { padding:10px 22px; border:none; border-radius:8px; background:#e0e7ff;
           color:#3730a3; font-size:14px; cursor:pointer; font-weight:600; }
    .tab.active { background:#2563eb; color:white; }
    .panel { display:none; } .panel.active { display:block; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:20px; }
    .card { background:white; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.08); padding:20px; }
    .card h3 { color:#2563eb; margin-bottom:8px; }
    .card .meta { font-size:13px; color:#666; margin-bottom:6px; }
    .card .badge { display:inline-block; padding:3px 10px; border-radius:20px;
                   background:#dbeafe; color:#1d4ed8; font-size:12px; margin-bottom:12px; }
    .btn { padding:9px 18px; border:none; border-radius:7px; cursor:pointer; font-size:14px; font-weight:600; }
    .btn-primary { background:#2563eb; color:white; }
    .btn-danger  { background:#ef4444; color:white; }
    .btn:hover { opacity:.88; }
    .form-group { margin-bottom:16px; }
    label { display:block; font-size:14px; font-weight:600; margin-bottom:5px; color:#374151; }
    input, select, textarea { width:100%; padding:10px 14px; border:2px solid #e5e7eb;
      border-radius:8px; font-size:14px; outline:none; transition:border .2s; }
    input:focus, select:focus { border-color:#2563eb; }
    .msg { padding:12px 16px; border-radius:8px; margin-bottom:16px; font-size:14px; display:none; }
    .msg.ok { background:#dcfce7; color:#16a34a; display:block; }
    .msg.err { background:#fee2e2; color:#dc2626; display:block; }
    table { width:100%; border-collapse:collapse; background:white; border-radius:12px;
            overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,.08); }
    th { background:#2563eb; color:white; padding:12px 16px; text-align:left; font-size:14px; }
    td { padding:11px 16px; border-bottom:1px solid #f1f5f9; font-size:14px; }
    tr:hover td { background:#f8faff; }
    .status-confirmed { color:#16a34a; font-weight:600; }
    .status-cancelled  { color:#dc2626; font-weight:600; }
  </style>
</head>
<body>
<header>
  <h1>🎟 Event Registration System</h1>
  <p>Browse events, register, and manage your bookings</p>
</header>
<div class="container">
  <div class="tabs">
    <button class="tab active" onclick="showTab('events', this)">📅 Events</button>
    <button class="tab" onclick="showTab('register', this)">✏️ Register</button>
    <button class="tab" onclick="showTab('my', this)">📋 My Registrations</button>
    <button class="tab" onclick="showTab('admin', this)">⚙️ Add Event</button>
  </div>

  <!-- Events Panel -->
  <div class="panel active" id="tab-events">
    <div class="grid" id="eventGrid">Loading events...</div>
  </div>

  <!-- Register Panel -->
  <div class="panel" id="tab-register">
    <div class="card" style="max-width:480px">
      <h3 style="margin-bottom:20px">Register for an Event</h3>
      <div class="msg" id="regMsg"></div>
      <div class="form-group"><label>Your Name</label><input id="regName" placeholder="Full name"/></div>
      <div class="form-group"><label>Email</label><input id="regEmail" type="email" placeholder="you@email.com"/></div>
      <div class="form-group"><label>Select Event</label>
        <select id="regEvent"><option value="">-- Choose event --</option></select>
      </div>
      <button class="btn btn-primary" onclick="submitReg()">Register Now</button>
    </div>
  </div>

  <!-- My Registrations Panel -->
  <div class="panel" id="tab-my">
    <div class="card" style="max-width:400px; margin-bottom:20px">
      <div class="form-group"><label>Enter your email to view registrations</label>
        <input id="lookupEmail" placeholder="you@email.com"/>
      </div>
      <button class="btn btn-primary" onclick="loadMyRegs()">View My Registrations</button>
    </div>
    <div id="myRegsTable"></div>
  </div>

  <!-- Admin Panel -->
  <div class="panel" id="tab-admin">
    <div class="card" style="max-width:520px">
      <h3 style="margin-bottom:20px">Add New Event</h3>
      <div class="msg" id="adminMsg"></div>
      <div class="form-group"><label>Title</label><input id="evTitle" placeholder="Event title"/></div>
      <div class="form-group"><label>Description</label>
        <textarea id="evDesc" rows="3" placeholder="Short description" style="resize:vertical"></textarea>
      </div>
      <div class="form-group"><label>Location</label><input id="evLoc" placeholder="Venue or Online"/></div>
      <div class="form-group"><label>Date</label><input id="evDate" type="date"/></div>
      <div class="form-group"><label>Capacity</label><input id="evCap" type="number" value="100"/></div>
      <div class="form-group"><label>Organizer</label><input id="evOrg" placeholder="Your name or org"/></div>
      <button class="btn btn-primary" onclick="addEvent()">Create Event</button>
    </div>
  </div>
</div>

<script>
function showTab(name, tabButton) {
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  if (tabButton) tabButton.classList.add('active');
}

async function loadEvents() {
  const res = await fetch('/api/events');
  const events = await res.json();
  const grid = document.getElementById('eventGrid');
  const sel  = document.getElementById('regEvent');
  sel.innerHTML = '<option value="">-- Choose event --</option>';
  grid.innerHTML = events.map(e=>`
    <div class="card">
      <span class="badge">📅 ${e.event_date}</span>
      <h3>${e.title}</h3>
      <div class="meta">📍 ${e.location}</div>
      <div class="meta">👤 ${e.organizer} &nbsp;|&nbsp; 🎫 ${e.registered}/${e.capacity} registered</div>
      <p style="font-size:13px;color:#555;margin:10px 0 14px">${e.description||''}</p>
      <button class="btn btn-primary" onclick="quickReg(${e.id},'${e.title}')">Register</button>
    </div>`).join('');
  events.forEach(e=>{
    sel.innerHTML += `<option value="${e.id}">${e.title} (${e.event_date})</option>`;
  });
}

function quickReg(id, title) {
  document.querySelectorAll('.tab')[1].click();
  document.getElementById('regEvent').value = id;
}

async function submitReg() {
  const name=document.getElementById('regName').value.trim();
  const email=document.getElementById('regEmail').value.trim();
  const event_id=document.getElementById('regEvent').value;
  const msg=document.getElementById('regMsg');
  msg.className='msg';
  if (!name||!email||!event_id){msg.className='msg err';msg.textContent='All fields are required.';return;}
  const res=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name,email,event_id})});
  const data=await res.json();
  if(res.ok){msg.className='msg ok';msg.textContent='✅ '+data.message;}
  else{msg.className='msg err';msg.textContent='❌ '+(data.error||'Error');}
}

async function loadMyRegs() {
  const email=document.getElementById('lookupEmail').value.trim();
  if(!email)return;
  const res=await fetch(`/api/my-registrations?email=${encodeURIComponent(email)}`);
  const data=await res.json();
  const el=document.getElementById('myRegsTable');
  if(!data.length){el.innerHTML='<p style="color:#666">No registrations found.</p>';return;}
  el.innerHTML='<table><thead><tr><th>Event</th><th>Date</th><th>Location</th><th>Status</th><th>Action</th></tr></thead><tbody>'+
    data.map(r=>`<tr>
      <td>${r.event_title}</td><td>${r.event_date}</td><td>${r.location}</td>
      <td class="status-${r.status}">${r.status}</td>
      <td>${r.status==='confirmed'?`<button class="btn btn-danger" onclick="cancelReg(${r.reg_id})">Cancel</button>`:'-'}</td>
    </tr>`).join('')+'</tbody></table>';
}

async function cancelReg(id) {
  if(!confirm('Cancel this registration?'))return;
  const res=await fetch(`/api/register/${id}`,{method:'DELETE'});
  const data=await res.json();
  alert(data.message||data.error);
  loadMyRegs();
}

async function addEvent() {
  const body={
    title:document.getElementById('evTitle').value.trim(),
    description:document.getElementById('evDesc').value.trim(),
    location:document.getElementById('evLoc').value.trim(),
    event_date:document.getElementById('evDate').value,
    capacity:parseInt(document.getElementById('evCap').value)||100,
    organizer:document.getElementById('evOrg').value.trim()
  };
  const msg=document.getElementById('adminMsg');
  const res=await fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json();
  if(res.ok){msg.className='msg ok';msg.textContent='✅ Event created!';loadEvents();}
  else{msg.className='msg err';msg.textContent='❌ '+(data.error||'Error');}
}

loadEvents();
</script>
</body>
</html>
"""

# ── API Routes ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/events", methods=["GET"])
def list_events():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT e.*, COUNT(r.id) AS registered
            FROM events e
            LEFT JOIN registrations r ON r.event_id = e.id AND r.status = 'confirmed'
            GROUP BY e.id ORDER BY e.event_date
        """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(dict(row))

@app.route("/api/events", methods=["POST"])
def create_event():
    d = request.get_json() or {}
    required = ["title", "event_date", "organizer"]
    for f in required:
        if not d.get(f):
            return jsonify({"error": f"{f} is required"}), 400
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO events (title,description,location,event_date,capacity,organizer) VALUES (?,?,?,?,?,?)",
            (d["title"], d.get("description",""), d.get("location","TBD"),
             d["event_date"], d.get("capacity", 100), d["organizer"])
        )
        conn.commit()
    return jsonify({"message": "Event created", "event_id": cur.lastrowid}), 201

@app.route("/api/register", methods=["POST"])
def register():
    d = request.get_json() or {}
    name, email, event_id = d.get("name","").strip(), d.get("email","").strip(), d.get("event_id")
    if not name or not email or not event_id:
        return jsonify({"error": "name, email, event_id are required"}), 400

    with get_db() as conn:
        # Upsert user
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            user_id = user["id"]
        else:
            cur = conn.execute("INSERT INTO users (name, email) VALUES (?,?)", (name, email))
            conn.commit()
            user_id = cur.lastrowid

        # Check capacity
        event = conn.execute("SELECT capacity FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return jsonify({"error": "Event not found"}), 404
        count = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'",
            (event_id,)
        ).fetchone()[0]
        if count >= event["capacity"]:
            return jsonify({"error": "Event is fully booked"}), 400

        # Check duplicate
        existing = conn.execute(
            "SELECT id, status FROM registrations WHERE user_id=? AND event_id=?", (user_id, event_id)
        ).fetchone()
        if existing:
            if existing["status"] == "confirmed":
                return jsonify({"error": "Already registered for this event"}), 400
            # Re-activate cancelled registration
            conn.execute("UPDATE registrations SET status='confirmed' WHERE id=?", (existing["id"],))
        else:
            conn.execute("INSERT INTO registrations (user_id, event_id) VALUES (?,?)", (user_id, event_id))
        conn.commit()

    return jsonify({"message": "Registration successful!"}), 201

@app.route("/api/my-registrations", methods=["GET"])
def my_registrations():
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"error": "email is required"}), 400
    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.id AS reg_id, e.title AS event_title, e.event_date,
                   e.location, r.status, r.registered_at
            FROM registrations r
            JOIN events  e ON e.id = r.event_id
            JOIN users   u ON u.id = r.user_id
            WHERE u.email = ?
            ORDER BY r.registered_at DESC
        """, (email,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/register/<int:reg_id>", methods=["DELETE"])
def cancel_registration(reg_id):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM registrations WHERE id = ?", (reg_id,)).fetchone()
        if not row:
            return jsonify({"error": "Registration not found"}), 404
        conn.execute("UPDATE registrations SET status = 'cancelled' WHERE id = ?", (reg_id,))
        conn.commit()
    return jsonify({"message": "Registration cancelled successfully"})

if __name__ == "__main__":
    app.run(debug=True, port=5002)
