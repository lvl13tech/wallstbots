import psycopg
import sys

passwords = {
    "Botty525874bYTFD47": "Botty525874bYTFD47",
    "h7W,B#hcDrVcPrT": "h7W,B#hcDrVcPrT"
}

host = "aws-0-us-east-1.pooler.supabase.com"
port = "6543"
user = "postgres"
database = "postgres"

print("Testing database credentials...\n")

for name, password in passwords.items():
    try:
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        conn = psycopg.connect(conn_string, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"✓ SUCCESS with password: {name}")
        print(f"  Database version: {version}\n")
        sys.exit(0)
    except Exception as e:
        print(f"✗ FAILED with password: {name}")
        print(f"  Error: {str(e)[:100]}\n")

print("Neither password worked. Credentials are incorrect.")
sys.exit(1)
