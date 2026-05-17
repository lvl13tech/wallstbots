================================================================
LVL13.TECH — FRESH RE-UPLOAD BUNDLE
Generated: 2026-05-15
================================================================

WHAT'S IN THE ZIP
-----------------
lvl13_public_html_2026-05-15_0413.zip contains the public_html/
folder with EVERY file your site needs:

  public_html/
    index.html               (2.7 KB — SPA shell)
    assets/
      app.js                 (32 KB — router + data fetch + chatbot)
      style.css              (22 KB — full brand stylesheet)
      logo.svg               (2 KB — header logo)
      robot.svg              (1.5 KB — chatbot icon)
      favicon.svg            (0.5 KB — browser tab icon)
      og-image.svg           (2.5 KB — social share preview)
    data/
      state.json             (39 KB — fund values + leaderboards)
      news.json              (2 KB — news feed)
      signals.json           (24 KB — Buy/Sell/Hold per stock)
      reports.json           (19 B — empty until first Sunday report)

All files verified clean: 0 null bytes, healthy sizes.

================================================================
HOW TO RE-UPLOAD (HostGator File Manager — 5 min)
================================================================

STEP 1 — Open HostGator File Manager
  1. Log in to portal.hostgator.com
  2. cPanel → Files → File Manager
  3. Navigate to public_html/

STEP 2 — Wipe what's there
  1. Select ALL files inside public_html/ (Ctrl+A or Select All)
  2. Click Delete → Confirm
  3. public_html/ should now be empty
     (Do NOT delete public_html itself — just its contents)

STEP 3 — Upload the new bundle
  1. Click Upload (top toolbar)
  2. Drag lvl13_public_html_2026-05-15_0413.zip into the upload window
  3. Wait for upload to finish (30 KB — should take 2 seconds)
  4. Close the upload tab, go back to File Manager

STEP 4 — Extract
  1. Right-click the .zip file → Extract
  2. Extract to: /public_html/
  3. After extraction you'll see a public_html/ folder INSIDE public_html/
  4. Open the inner public_html/ folder
  5. Select all files inside it (index.html, assets, data)
  6. Click Move → destination /public_html/
  7. Delete the now-empty inner public_html/ folder
  8. Delete the .zip file

  ALTERNATIVE: extract directly into public_html/ if your File Manager
  has that option, then no moving needed.

STEP 5 — Verify
Open these THREE URLs in a new browser tab:

  https://lvl13.tech/
    → Should load the full site (not "Loading...")

  https://lvl13.tech/data/state.json
    → Should show a wall of JSON starting with { "starting_capital": 43000 ...

  https://lvl13.tech/assets/app.js
    → Should show JavaScript starting with /* ===... lvl13.tech ...

If all three load → you're done.
If state.json or app.js shows 404 → the file didn't make it to the right
folder. Re-do Step 4.

================================================================
IF SITE STILL SAYS "LOADING..."
================================================================

This means Cloudflare is caching the old broken version. Fix:

  1. Go to dash.cloudflare.com
  2. Click on lvl13.tech
  3. Caching → Configuration → Purge Everything
  4. Wait 30 seconds
  5. Hard refresh lvl13.tech (Ctrl+Shift+R or Cmd+Shift+R)

================================================================
