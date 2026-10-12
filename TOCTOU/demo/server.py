"""
╔══════════════════════════════════════════════════════════╗
║    CyberShop — TOCTOU CTF Demo Server (VULNERABLE)       ║
║    Race the /buy endpoint to grab the flag!              ║
╚══════════════════════════════════════════════════════════╝

Run:  pip install flask   &&   python server.py
Then: open http://localhost:8080
"""

import time, sqlite3, os, secrets
from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, g, render_template_string
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "cybershop.db")
DEMO_USER = "hacker"

# ── Items catalogue ────────────────────────────────────────
ITEMS = [
    {"id": 1, "name": "🚩 FLAG Item",      "price": 100,
     "desc": "Buy this to get the flag!", "flag": True },
    {"id": 2, "name": "💻 Hacker Laptop",  "price": 100,
     "desc": "Ultra-secure, runs Kali.",  "flag": False},
    {"id": 3, "name": "🔑 Zero-Day",       "price": 200,
     "desc": "Fresh 0-day for your CTF.", "flag": False},
]

# ── DB helpers ─────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            balance  REAL DEFAULT 100.0
        );
        CREATE TABLE orders (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            item_id  INTEGER,
            item_name TEXT,
            amount   REAL,
            ts       REAL
        );
    """)
    db.execute("INSERT INTO users (username) VALUES (?)", (DEMO_USER,))
    db.commit()
    db.close()
    print(f"[+] DB initialised — demo user '{DEMO_USER}' has $100")

def get_or_create_demo_user():
    """Auto-login as demo user — no registration needed."""
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (DEMO_USER,)).fetchone()
    if user:
        session["user_id"] = user["id"]
    return user

# ══════════════════════════════════════════════════════════
#  HTML TEMPLATES  (inline for single-file portability)
# ══════════════════════════════════════════════════════════
STYLES = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;400;600;700;800&display=swap');
  :root{--bg:#050810;--surface:#0d1117;--card:#111827;--border:#1f2d3d;
        --accent:#00f5c4;--accent2:#7c3aed;--accent3:#f59e0b;
        --red:#ef4444;--text:#e2e8f0;--muted:#64748b;}
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;min-height:100vh;}
  body::before{content:'';position:fixed;inset:0;
    background-image:linear-gradient(rgba(0,245,196,.03) 1px,transparent 1px),
                     linear-gradient(90deg,rgba(0,245,196,.03) 1px,transparent 1px);
    background-size:60px 60px;pointer-events:none;z-index:0;}
  nav{position:sticky;top:0;z-index:50;background:rgba(5,8,16,.92);
      border-bottom:1px solid var(--border);backdrop-filter:blur(20px);
      display:flex;align-items:center;justify-content:space-between;
      padding:.9rem 2.5rem;}
  .brand{font-weight:800;font-size:1.25rem;
         background:linear-gradient(135deg,var(--accent),var(--accent2));
         -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
  .nav-links{display:flex;gap:1.2rem;align-items:center;}
  .nav-links a{color:var(--muted);text-decoration:none;font-size:.9rem;transition:color .2s;}
  .nav-links a:hover{color:var(--accent);}
  .balance-badge{background:rgba(0,245,196,.1);border:1px solid rgba(0,245,196,.3);
                 color:var(--accent);padding:.3rem .9rem;border-radius:20px;
                 font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:700;}
  main{max-width:1100px;margin:0 auto;padding:2.5rem 1.5rem;position:relative;z-index:1;}
  h1{font-size:2rem;font-weight:800;margin-bottom:.4rem;}
  h2{font-size:1.4rem;font-weight:700;margin-bottom:1rem;}
  .sub{color:var(--muted);margin-bottom:2rem;font-size:.95rem;}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.2rem;}
  .card{background:rgba(17,24,39,.85);border:1px solid var(--border);border-radius:16px;
        padding:1.5rem;backdrop-filter:blur(10px);transition:border-color .25s,transform .25s;}
  .card:hover{border-color:var(--accent);transform:translateY(-3px);}
  .card-icon{font-size:2.5rem;margin-bottom:.75rem;}
  .card h3{font-size:1.1rem;font-weight:700;margin-bottom:.35rem;}
  .card .desc{color:var(--muted);font-size:.88rem;margin-bottom:1rem;line-height:1.5;}
  .price{font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:700;color:var(--accent3);}
  .btn{display:inline-flex;align-items:center;gap:.4rem;padding:.6rem 1.4rem;
       border-radius:8px;font-family:'Outfit',sans-serif;font-weight:600;font-size:.9rem;
       cursor:pointer;border:none;transition:all .2s;text-decoration:none;}
  .btn-primary{background:linear-gradient(135deg,var(--accent),#00c9a7);color:#000;}
  .btn-primary:hover{opacity:.88;transform:translateY(-1px);}
  .btn-secondary{background:rgba(124,58,237,.15);border:1px solid var(--accent2);color:#c4b5fd;}
  .btn-secondary:hover{background:rgba(124,58,237,.25);}
  .btn-danger{background:rgba(239,68,68,.15);border:1px solid var(--red);color:var(--red);}
  .btn-danger:hover{background:rgba(239,68,68,.25);}
  .btn-sm{padding:.4rem 1rem;font-size:.82rem;}
  .flag-reveal{background:linear-gradient(135deg,rgba(0,245,196,.1),rgba(124,58,237,.1));
               border:2px solid var(--accent);border-radius:14px;padding:1.5rem;
               text-align:center;margin-top:1rem;}
  .flag-text{font-family:'JetBrains Mono',monospace;font-size:1.3rem;color:var(--accent);
             font-weight:700;letter-spacing:2px;}
  .orders-table{width:100%;border-collapse:collapse;font-size:.9rem;}
  .orders-table th{text-align:left;padding:.6rem 1rem;color:var(--accent);
                   font-family:'JetBrains Mono',monospace;font-size:.75rem;
                   text-transform:uppercase;border-bottom:1px solid var(--accent);}
  .orders-table td{padding:.65rem 1rem;border-bottom:1px solid var(--border);color:#cbd5e1;}
  .orders-table tr:last-child td{border:none;}
</style>
"""

BASE_HTML = STYLES + """
<nav>
  <div class="brand">⚡ CyberShop</div>
  <div class="nav-links">
    {% if user %}<span class="balance-badge">💰 ${{ "%.2f"|format(user['balance']) }}</span>{% endif %}
    <a href="/shop">Shop</a><a href="/orders">Orders</a><a href="/admin">Admin</a>
    <a href="/reset" class="btn btn-danger btn-sm" onclick="return confirm('Reset the demo?')">↺ Reset</a>
  </div>
</nav>
<main>
"""

# ══════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return redirect(url_for("shop"))

# ── reset (no restart needed) ──────────────────────────────
@app.route("/reset")
def reset():
    session.clear()
    init_db()
    return redirect(url_for("shop"))

# ── shop ───────────────────────────────────────────────────
@app.route("/shop")
def shop():
    user = get_or_create_demo_user()
    return render_template_string(BASE_HTML + """
      <h1>🛒 CyberShop</h1>
      <p class="sub">Your balance: <strong style="color:var(--accent)">${{ "%.2f"|format(user['balance']) }}</strong></p>
      <div class="grid">
        {% for item in items %}
        <div class="card">
          <div class="card-icon">{{ item.name.split(' ')[0] }}</div>
          <h3>{{ item.name.split(' ', 1)[1] }}</h3>
          <p class="desc">{{ item.desc }}</p>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-top:.5rem">
            <span class="price">${{ item.price }}</span>
            <button class="btn btn-primary btn-sm" onclick="buyItem({{ item.id }}, this)">Buy Now</button>
          </div>
          <div id="result-{{ item.id }}" style="margin-top:.75rem;font-size:.85rem;font-family:'JetBrains Mono',monospace;"></div>
        </div>
        {% endfor %}
      </div>
      <script>
      async function buyItem(id, btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Processing…';
        document.getElementById('result-'+id).textContent = '';
        const r = await fetch('/buy', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({item_id: id})
        });
        const data = await r.json();
        const el = document.getElementById('result-'+id);
        if (data.ok) {
          el.style.color = 'var(--accent)';
          el.textContent = '✅ ' + data.message;
          if (data.flag) {
            el.innerHTML += '<br><br><div class="flag-reveal"><div class="flag-text">' + data.flag + '</div></div>';
          }
          location.reload();
        } else {
          el.style.color = 'var(--red)';
          el.textContent = '❌ ' + data.message;
        }
        btn.disabled = false;
        btn.textContent = 'Buy Now';
      }
      </script>
    </main>""", user=user, items=ITEMS)

# ── VULNERABLE buy endpoint ─────────────────────────────────
@app.route("/buy", methods=["POST"])
def buy():
    user = get_or_create_demo_user()
    if not user:
        return jsonify({"ok": False, "message": "No demo user found — visit /reset"}), 500

    data    = request.get_json()
    item_id = data.get("item_id")
    item    = next((i for i in ITEMS if i["id"] == item_id), None)
    if not item:
        return jsonify({"ok": False, "message": "Item not found"}), 404

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

    # ════════════════════════════════════════
    #  ❌ TIME OF CHECK  (vulnerable!)
    # ════════════════════════════════════════
    if user["balance"] < item["price"]:
        return jsonify({"ok": False, "message": "Insufficient funds 💸"}), 403

    # ════════════════════════════════════════
    #  ⚠️  THE GAP — simulated async delay
    #      This is where the race happens!
    # ════════════════════════════════════════
    time.sleep(2)   # simulates payment gateway, fraud check, etc.

    # ════════════════════════════════════════
    #  ❌ TIME OF USE  (uses stale balance!)
    # ════════════════════════════════════════
    db.execute("UPDATE users SET balance = balance - ? WHERE id=?",
               (item["price"], session["user_id"]))
    db.execute("INSERT INTO orders (user_id, item_id, item_name, amount, ts) VALUES (?,?,?,?,?)",
               (session["user_id"], item["id"], item["name"], item["price"], time.time()))
    db.commit()

    # Re-fetch balance to see if the race pushed it negative
    new_balance = db.execute(
        "SELECT balance FROM users WHERE id=?", (session["user_id"],)
    ).fetchone()["balance"]

    resp = {"ok": True, "message": f"You bought: {item['name']}! 🎉"}
    if item.get("flag") and new_balance < 0:
        resp["flag"] = "flag{r4c3_c0nd1t10n_w1ns}"
    return jsonify(resp)

# ── orders ─────────────────────────────────────────────────
@app.route("/orders")
def orders():
    user   = get_or_create_demo_user()
    db     = get_db()
    rows   = db.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY ts DESC", (session["user_id"],)
    ).fetchall()
    return render_template_string(BASE_HTML + """
      <h1>📦 Orders</h1>
      <p class="sub">Current balance: <strong style="color:var(--accent)">${{ "%.2f"|format(user['balance']) }}</strong></p>
      {% if orders %}
      <div class="card" style="overflow-x:auto">
        <table class="orders-table">
          <thead><tr><th>#</th><th>Item</th><th>Amount</th><th>Flag?</th></tr></thead>
          <tbody>
          {% for o in orders %}
          <tr>
            <td>#{{ o['id'] }}</td>
            <td>{{ o['item_name'] }}</td>
            <td style="color:var(--accent3);font-family:'JetBrains Mono',monospace">${{ "%.2f"|format(o['amount']) }}</td>
            <td>
              {% if '🚩' in o['item_name'] and user['balance'] < 0 %}
              <div class="flag-reveal" style="padding:.6rem 1rem;margin:0">
                <div class="flag-text" style="font-size:.95rem">flag{r4c3_c0nd1t10n_w1ns}</div>
              </div>
              {% else %}—{% endif %}
            </td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
      {% else %}
      <div class="card" style="text-align:center;padding:2.5rem">
        <p style="color:var(--muted)">No orders yet. Go buy something!</p>
        <a href="/shop" class="btn btn-primary" style="margin-top:1rem;display:inline-flex">Go to Shop</a>
      </div>
      {% endif %}
    </main>""", user=user, orders=rows)

# ── admin (show all users + balances for demo) ─────────────
@app.route("/admin")
def admin():
    db    = get_db()
    users = db.execute("SELECT id,username,balance FROM users").fetchall()
    return render_template_string(BASE_HTML + """
      <h1>🔧 Admin Panel</h1>
      <p class="sub">All users and balances (for demo purposes only)</p>
      <div class="card" style="overflow-x:auto">
        <table class="orders-table">
          <thead><tr><th>ID</th><th>Username</th><th>Balance</th><th>Status</th></tr></thead>
          <tbody>
          {% for u in users %}
          <tr>
            <td>#{{ u['id'] }}</td>
            <td>{{ u['username'] }}</td>
            <td style="font-family:'JetBrains Mono',monospace;color:{{ 'var(--red)' if u['balance'] < 0 else 'var(--accent)' }}">${{ "%.2f"|format(u['balance']) }}</td>
            <td>{{ '🔴 NEGATIVE (race won!)' if u['balance'] < 0 else ('🟡 Zero' if u['balance']==0 else '🟢 Normal') }}</td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </main>""", users=users, user=None)

if __name__ == "__main__":
    init_db()
    print("\n" + "="*55)
    print("  🏪  CyberShop CTF Demo — TOCTOU Vulnerable Server")
    print("="*55)
    print("  URL:      http://localhost:8080")
    print("  Admin:    http://localhost:8080/admin")
    print("  Reset:    http://localhost:8080/reset")
    print("="*55)
    print("  Exploit:  python3 exploit.py")
    print("="*55 + "\n")
    app.run(debug=True, threaded=True, port=8080)
