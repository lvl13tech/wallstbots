#!/usr/bin/env python3
"""
Update frontend API URLs to point to deployed Cloud Run service
Run this after getting the Cloud Run service URL
"""

import os
import sys
import re

# Get Cloud Run service URL from user or environment
cloud_run_url = os.environ.get('CLOUD_RUN_URL')

if not cloud_run_url:
    print("Cloud Run service URL not provided.")
    print("Please provide the Cloud Run service URL as an environment variable:")
    print("  export CLOUD_RUN_URL='https://wallstbots-backend-XXXXX.run.app'")
    print("")
    print("Or pass it as a command-line argument:")
    print("  python3 update-frontend-api-urls.py https://wallstbots-backend-XXXXX.run.app")

    if len(sys.argv) > 1:
        cloud_run_url = sys.argv[1]
    else:
        sys.exit(1)

# Ensure URL doesn't have trailing slash
cloud_run_url = cloud_run_url.rstrip('/')

print(f"Updating frontend API URLs to: {cloud_run_url}")
print("")

# Frontend directories
frontends = [
    'C:\\Users\\temps\\OneDrive\\Desktop\\Claude\\Websites\\1. Wall St Bots\\Frontends\\lvl13.tech',
    'C:\\Users\\temps\\OneDrive\\Desktop\\Claude\\Websites\\1. Wall St Bots\\Frontends\\bitbot13.tech',
    'C:\\Users\\temps\\OneDrive\\Desktop\\Claude\\Websites\\1. Wall St Bots\\Frontends\\wallstbots.tech',
]

files_to_update = [
    'login.html',
    'signup.html',
    'index.html',
]

updated_count = 0

for frontend_dir in frontends:
    frontend_name = os.path.basename(frontend_dir)
    print(f"Updating {frontend_name}...")

    for filename in files_to_update:
        filepath = os.path.join(frontend_dir, filename)

        if not os.path.exists(filepath):
            print(f"  ⊘ {filename} not found (skipping)")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Replace API_BASE_URL
            original_content = content
            content = re.sub(
                r'const API_BASE_URL = "[^"]*"',
                f'const API_BASE_URL = "{cloud_run_url}"',
                content
            )

            # Also replace http://localhost:8000 references
            content = content.replace(
                'http://localhost:8000',
                cloud_run_url
            )

            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✓ {filename} updated")
                updated_count += 1
            else:
                print(f"  = {filename} already updated or no matches found")

        except Exception as e:
            print(f"  ✗ {filename} ERROR: {str(e)}")

print("")
print(f"Updated {updated_count} files successfully")
print("")
print("Next steps:")
print("1. Commit changes to Git:")
print("   git add .")
print("   git commit -m 'Update frontend API URLs to Cloud Run service'")
print("")
print("2. Push to GitHub (triggers Cloudflare Pages deployment):")
print("   git push origin main")
print("")
print("3. Verify frontends are deployed (may take 1-2 minutes)")
print("   - lvl13.tech")
print("   - bitbot13.tech")
print("   - wallstbots.tech")
