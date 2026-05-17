#!/usr/bin/env python3
"""
deploy_to_hostgator.py
Uploads public_html/data/*.json to HostGator via FTP.

For initial site upload (HTML/CSS/JS), use cPanel File Manager once.
This script is for the recurring data refresh — runs every few minutes
on a schedule (Windows Task Scheduler, cron, or GitHub Actions).
"""
import json
import sys
import ftplib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / "config" / "secrets.json"
LOCAL_DATA = ROOT / "public_html" / "data"

def load_secrets():
    if not SECRETS_PATH.exists():
        print(f"Missing {SECRETS_PATH}.")
        sys.exit(1)
    return json.loads(SECRETS_PATH.read_text())

def main():
    secrets = load_secrets()
    ftp_cfg = secrets.get("hostgator_ftp", {})
    if "FILL_IN" in (ftp_cfg.get("username") or "FILL_IN"):
        print("HostGator FTP credentials missing in config/secrets.json")
        sys.exit(1)

    files = list(LOCAL_DATA.glob("*.json"))
    if not files:
        print("No JSON files in public_html/data/ to upload.")
        sys.exit(1)

    print(f"[deploy] connecting to {ftp_cfg['host']}...")
    try:
        # Try FTPS first (more secure), fall back to plain FTP
        try:
            ftp = ftplib.FTP_TLS(ftp_cfg["host"], timeout=30)
            ftp.login(ftp_cfg["username"], ftp_cfg["password"])
            ftp.prot_p()
            print("[deploy] using FTPS (secure)")
        except Exception:
            ftp = ftplib.FTP(ftp_cfg["host"], timeout=30)
            ftp.login(ftp_cfg["username"], ftp_cfg["password"])
            print("[deploy] using plain FTP")

        ftp.cwd(ftp_cfg["remote_dir"])
        for f in files:
            print(f"  → {f.name} ({f.stat().st_size:,} bytes)")
            with open(f, "rb") as fh:
                ftp.storbinary(f"STOR {f.name}", fh)
        ftp.quit()
        print(f"[deploy] uploaded {len(files)} file(s) to {ftp_cfg['remote_dir']}")
    except Exception as e:
        print(f"[deploy] FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
