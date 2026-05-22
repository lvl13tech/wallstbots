import urllib.request, urllib.error, json, sys

SUPABASE_URL     = "https://rfsssoeyctobxbhpjyom.supabase.co"
SERVICE_ROLE_KEY = "sb_secret_VtpfIRxxlkQ9NB2ZBXQ84Q_m-0w6iey"
TARGET_EMAIL     = "lvl13cs@gmail.com"
NEW_PASSWORD     = "$Amonre$10mil^"

headers = {
    "apikey":        SERVICE_ROLE_KEY,
    "Authorization": "Bearer " + SERVICE_ROLE_KEY,
    "Content-Type":  "application/json",
}

def api(method, path, body=None):
    url  = SUPABASE_URL + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# Step 1: find user by email
print(f"[1] looking up {TARGET_EMAIL}...")
status, data = api("GET", "/auth/v1/admin/users?per_page=1000")
print(f"    status: {status}")
users = [u for u in data.get("users", []) if u.get("email") == TARGET_EMAIL]

if not users:
    print(f"ERROR: {TARGET_EMAIL} not found in Supabase")
    sys.exit(1)

user    = users[0]
user_id = user["id"]
confirmed = str(user.get("email_confirmed_at", "not confirmed"))[:10]
print(f"    found user_id: {user_id}")
print(f"    email_confirmed: {confirmed}")

# Step 2: update password
print("[2] updating password...")
status, result = api("PUT", f"/auth/v1/admin/users/{user_id}", {"password": NEW_PASSWORD})
print(f"    status: {status}")
if status in (200, 201):
    print("    SUCCESS - password updated")
else:
    print(f"    ERROR: {result}")
    sys.exit(1)

# Step 3: ensure admin role in DB
try:
    import psycopg2
    DB_URL = "postgresql://postgres.rfsssoeyctobxbhpjyom:WsbProd2024!Zx9k@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    print("[3] ensuring admin role in DB...")
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    cur.execute("UPDATE users SET role='admin' WHERE id=%s RETURNING email, role", (user_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    print(f"    DB: email={row[0]}  role={row[1]}")
except ImportError:
    print("[3] psycopg2 not installed - skipping DB role check (password still reset OK)")
except Exception as e:
    print(f"[3] DB non-fatal: {e}")

print()
print("=== DONE ===")
print(f"  Login: https://wallstbots.tech/#/login")
print(f"  Email: {TARGET_EMAIL}")
print(f"  Password: set successfully")
