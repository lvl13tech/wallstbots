#!/usr/bin/env python3
"""
upload_lvl13_full.py
====================
Upload ALL lvl13.tech frontend files (HTML, JS, CSS, assets/) to HostGator via FTP.

Unlike deploy_to_hostgator.py (which only uploads data/*.json), this script
pushes the full site for an initial deploy or a frontend refresh.

Reads creds from Project/config/secrets.json:
    hostgator_ftp.host, .username, .password
Discovers the right web-root automatically, with sensible fallbacks.
"""
import ftplib
import json
import sys
import time
from pathlib import Path

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

ROOT = Path(__file__).resolve().parents[2]
SECRETS_PATH = ROOT / "Project" / "config" / "secrets.json"
LOCAL_SITE  = ROOT / "Frontends" / "lvl13.tech"   # repo copy
ALT_SITE    = ROOT.parent / "1. lvl13.tech" / "Project" / "public_html"  # staging copy

# Files to upload. Tuples of (local_path_relative_to_site_root, remote_path).
FILES_TO_UPLOAD = [
    "index.html",
    "dashboard.html",
    "bot-detail.html",
    "admin.html",
    "login.html",
    "signup.html",
    "auth.js",
    "api.js",
    "assets/app.js",
    "assets/style.css",
    "assets/favicon.svg",
    "assets/logo.svg",
    "assets/robot.svg",
    "assets/og-image.svg",
    "assets/logo-bitbot13.png",
    "assets/logo-lvl13.png",
    "assets/logo-wallstbots.png",
]


def pick_source_dir() -> Path:
    """Prefer the staging folder (1. lvl13.tech) if it has the freshest files."""
    candidates = []
    for c in [ALT_SITE, LOCAL_SITE]:
        if c.exists():
            app_js = c / "assets" / "app.js"
            if app_js.exists():
                candidates.append((app_js.stat().st_mtime, c))
    if not candidates:
        print(f"ERROR: no source folder with assets/app.js found. Checked:\n  {LOCAL_SITE}\n  {ALT_SITE}")
        sys.exit(1)
    candidates.sort(reverse=True)  # newest first
    chosen = candidates[0][1]
    print(f"[source] using: {chosen}")
    return chosen


def connect_sftp(host: str, user: str, pwd: str):
    """Try SFTP on port 22 using paramiko. Returns (ssh, sftp) tuple."""
    if not HAS_PARAMIKO:
        raise ImportError("paramiko not installed")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=22, username=user, password=pwd, timeout=20)
    sftp = ssh.open_sftp()
    print(f"[sftp] connected to {host}:22")
    return ssh, sftp


def sftp_mkdir_p(sftp, remote_path: str):
    """mkdir -p via SFTP."""
    parts = [p for p in remote_path.replace("\\", "/").split("/") if p]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            try:
                sftp.mkdir(cur)
            except Exception as e:
                print(f"  [sftp mkdir] {cur}: {e}")


def sftp_discover_webroot(sftp) -> str:
    """Find the lvl13.tech webroot over SFTP."""
    candidates = [
        "lvl13.tech",
        "public_html/lvl13.tech",
        "public_html/lvl13",
        "lvl13",
        "public_html",
    ]
    for path in candidates:
        try:
            items = [f.filename for f in sftp.listdir_attr(path)]
            has_index  = "index.html" in items
            has_assets = "assets" in items
            print(f"[sftp probe] {path}/  items={len(items)}  index={has_index}  assets={has_assets}")
            if has_index or has_assets:
                return path
        except Exception as e:
            print(f"[sftp probe] {path}/  — {type(e).__name__}")
    print("[sftp probe] defaulting to public_html")
    return "public_html"


def upload_via_sftp(sftp, source_dir: Path) -> tuple:
    """Upload all FILES_TO_UPLOAD via SFTP. Returns (ok, fail)."""
    webroot = sftp_discover_webroot(sftp)
    print(f"[sftp] uploading into: {webroot}/")
    ok = fail = 0
    for rel in FILES_TO_UPLOAD:
        local = source_dir / rel
        if not local.exists():
            print(f"  [skip] missing local: {local}")
            fail += 1
            continue
        remote = f"{webroot}/{rel}"
        # ensure parent dir exists
        parts = rel.split("/")
        if len(parts) > 1:
            sftp_mkdir_p(sftp, f"{webroot}/{'/'.join(parts[:-1])}")
        try:
            sftp.put(str(local), remote)
            print(f"  [up] {rel}  ({local.stat().st_size} bytes)")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {rel}: {type(e).__name__}: {e}")
            fail += 1
    return ok, fail


def connect(host: str, user: str, pwd: str) -> ftplib.FTP:
    """Try FTPS, fall back to plain FTP. Try multiple host candidates."""
    # HostGator sometimes blocks ftp.<domain>; the domain itself or the
    # cPanel server hostname (e.g. sh00167.hostgator.com) usually works.
    candidates = [host]
    base = host.replace("ftp.", "", 1)
    if base != host:
        candidates.append(base)              # e.g. "lvl13.tech"
        candidates.append(f"www.{base}")     # e.g. "www.lvl13.tech"
    # If host already looks like a cPanel server, also try its FTP subdomain form
    if "hostgator.com" in host:
        candidates.insert(0, host)           # cPanel server first
    seen = set()
    last_err = None
    for h in candidates:
        if h in seen:
            continue
        seen.add(h)
        # Try FTPS
        try:
            ftp = ftplib.FTP_TLS(h, timeout=20)
            ftp.login(user, pwd)
            ftp.prot_p()
            print(f"[ftp] FTPS connected ({h})")
            return ftp
        except Exception as e:
            print(f"[ftp] FTPS to {h} failed: {type(e).__name__}: {str(e)[:80]}")
            last_err = e
        # Try plain FTP
        try:
            ftp = ftplib.FTP(h, timeout=20)
            ftp.login(user, pwd)
            print(f"[ftp] plain FTP connected ({h})")
            return ftp
        except Exception as e:
            print(f"[ftp] plain FTP to {h} failed: {type(e).__name__}: {str(e)[:80]}")
            last_err = e
    print(f"\n[ftp] ALL hostnames failed. Last error: {last_err}")
    print(f"[ftp] Tried: {list(seen)}")
    print(f"[ftp] Likely causes:")
    print(f"      - DNS for ftp.<domain> not pointing to FTP server")
    print(f"      - HostGator disabled plain FTP/FTPS (now requires SFTP)")
    print(f"      - Local firewall / VPN (NordVPN) blocking outbound port 21")
    print(f"      - cPanel server hostname needed (e.g. gatorXXXX.hostgator.com)")
    raise last_err


def discover_webroot(ftp: ftplib.FTP) -> str:
    """
    Figure out where to put the lvl13 files. Common HostGator layouts:
      A) FTP user lands at /  with /public_html/ being the primary site
         → upload to /public_html/lvl13.tech/ if it exists, else /public_html/
      B) FTP user lands directly at the site webroot (subdomain-specific FTP)
         → upload to .
      C) FTP user lands at /public_html/lvl13.tech/ already
         → upload to .
    """
    pwd = ftp.pwd()
    print(f"[ftp] landing pwd: {pwd}")

    # Probe candidates in priority order. Your cPanel URL shows dir=lvl13.tech,
    # so that's the most likely webroot for this addon domain.
    candidates = [
        "lvl13.tech",
        "public_html/lvl13.tech",
        "public_html/lvl13",
        "lvl13",
        "public_html",
        ".",
    ]
    for path in candidates:
        try:
            ftp.cwd("/")
            ftp.cwd(path)
            items = ftp.nlst()
            # Heuristic: a webroot has index.html OR assets/
            has_index  = any(i == "index.html" or i.endswith("/index.html") for i in items)
            has_assets = any(i == "assets" or i.endswith("/assets") for i in items)
            print(f"[probe] /{path}/  items={len(items)}  index={has_index}  assets={has_assets}")
            if has_index or has_assets:
                ftp.cwd("/")
                return path.lstrip("/")
        except Exception as e:
            print(f"[probe] /{path}/  — {type(e).__name__}")
    # No clear match — default to public_html
    print(f"[probe] no clear lvl13 webroot found; defaulting to public_html")
    ftp.cwd("/")
    return "public_html"


def ensure_dir(ftp: ftplib.FTP, path: str):
    """mkdir -p equivalent on remote."""
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p
        try:
            ftp.cwd(cur)
        except ftplib.error_perm:
            try:
                ftp.mkd(cur)
                ftp.cwd(cur)
            except ftplib.error_perm as e:
                print(f"  [mkdir] failed for {cur}: {e}")
                return False
    return True


def upload_file(ftp: ftplib.FTP, webroot: str, local: Path, rel_remote: str) -> bool:
    if not local.exists():
        print(f"  [skip] missing local: {local}")
        return False
    # Ensure remote directory exists
    parts = rel_remote.split("/")
    if len(parts) > 1:
        ftp.cwd("/")
        ensure_dir(ftp, f"{webroot}/{'/'.join(parts[:-1])}")
    # Upload
    ftp.cwd("/")
    ftp.cwd(webroot)
    if len(parts) > 1:
        ftp.cwd("/".join(parts[:-1]))
    size = local.stat().st_size
    with open(local, "rb") as fh:
        ftp.storbinary(f"STOR {parts[-1]}", fh)
    print(f"  [up] {rel_remote}  ({size} bytes)")
    return True


def main():
    if not SECRETS_PATH.exists():
        print(f"ERROR: {SECRETS_PATH} not found")
        sys.exit(1)
    secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    ftp_cfg = secrets.get("hostgator_ftp", {})
    user = ftp_cfg.get("username", "")
    pwd  = ftp_cfg.get("password", "")
    host = ftp_cfg.get("host", "")
    if not host or not user or not pwd or "FILL" in str(user) or "FILL" in str(pwd):
        print(f"ERROR: hostgator_ftp creds incomplete in secrets.json (host={host!r}, user_set={bool(user)}, pwd_set={bool(pwd)})")
        sys.exit(1)

    source_dir = pick_source_dir()

    # ── Try SFTP first (HostGator now requires SFTP on most accounts) ────────
    ssh = sftp = None
    ok = fail = 0
    used_sftp = False

    if HAS_PARAMIKO:
        try:
            ssh, sftp = connect_sftp(host, user, pwd)
            print()
            ok, fail = upload_via_sftp(sftp, source_dir)
            used_sftp = True
        except Exception as e:
            print(f"[sftp] failed: {type(e).__name__}: {e}")
            print("[sftp] falling back to FTP/FTPS...")
        finally:
            if sftp:
                try: sftp.close()
                except Exception: pass
            if ssh:
                try: ssh.close()
                except Exception: pass
    else:
        print("[sftp] paramiko not installed — install with: pip install paramiko")
        print("[sftp] falling back to FTP/FTPS...")

    # ── Fall back to FTP/FTPS if SFTP didn't work ────────────────────────────
    if not used_sftp:
        ftp = connect(host, user, pwd)
        try:
            webroot = discover_webroot(ftp)
            print(f"[ftp] uploading into: /{webroot}/")
            print()
            for rel in FILES_TO_UPLOAD:
                local = source_dir / rel
                try:
                    if upload_file(ftp, webroot, local, rel):
                        ok += 1
                    else:
                        fail += 1
                except Exception as e:
                    print(f"  [FAIL] {rel}: {type(e).__name__}: {e}")
                    fail += 1
        finally:
            try: ftp.quit()
            except Exception: ftp.close()

    print()
    print(f"[result] uploaded {ok}, failed/skipped {fail}, total {len(FILES_TO_UPLOAD)}")
    print(f"[next] open https://lvl13.tech in a fresh tab (hard refresh: Ctrl+F5) to verify")


if __name__ == "__main__":
    main()
__main__":
    main()
