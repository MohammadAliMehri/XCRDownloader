"""XCRDownloader browser user-flow test (Playwright)."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
results = []

def log(step, ok, detail=""):
    results.append((step, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} | {step} | {detail}")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # 1. Load
    pg.goto(BASE, timeout=30000)
    pg.wait_for_timeout(1200)
    log("1. app loads", "XCRDownloader" in pg.title(), pg.title())

    # 2. Downloader: paste URL, auto-preview
    pg.fill("#url-input", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    pg.wait_for_timeout(6000)
    preview = pg.eval_on_selector_all("#preview-card, .preview-card, [id*=preview]",
                                      "els => els.map(e => ({display: getComputedStyle(e).display, text: (e.textContent||'').trim().slice(0,80)}))")
    visible = [p for p in preview if p["display"] != "none"]
    log("2. URL auto-preview", len(visible) > 0, str(visible)[:120])

    # 3. Player tab: music search
    pg.click("button:has-text('Player')")
    pg.wait_for_timeout(500)
    pg.fill("#music-search-input", "alan walker faded")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(16000)
    n_results = pg.eval_on_selector_all(".sr-row", "els => els.length")
    log("3. music search results", n_results > 0, f"{n_results} results")
    first = pg.eval_on_selector_all(".sr-row", "els => els.length ? els[0].textContent.trim().slice(0,60) : ''")
    log("3b. first result", bool(first), str(first)[:80])

    # 4. Click play on first result
    try:
        pg.eval_on_selector_all(".sr-row", "els => els[0] ? els[0].click() : null")
        pg.wait_for_timeout(12000)
        np = pg.eval_on_selector_all("#np-title", "els => els.map(e => e.textContent.trim().slice(0,60))")
        playing = pg.eval_on_selector_all("#np-audio", "els => els.map(e => ({tag: e.tagName, paused: e.paused, src: (e.currentSrc||'').slice(0,60)}))")
        log("4. play from results", bool(playing) and not playing[0]["paused"], f"np={np[:1]} media={playing[:1]}")
    except Exception as e:
        log("4. play from results", False, str(e)[:100])

    # 5. Anime tab: search
    pg.click("button:has-text('Anime')")
    pg.wait_for_timeout(500)
    pg.fill("#anime-search-input", "naruto")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(15000)
    cards = pg.eval_on_selector_all(".anime-card", "els => els.length")
    log("5. anime search", cards > 0, f"{cards} cards")
    first_title = pg.eval_on_selector_all(".anime-card .anime-card-title", "els => els.length ? els[0].textContent.trim().slice(0,50) : ''")
    log("5b. first anime card", bool(first_title), str(first_title)[:60])

    # 6. Open detail + episodes
    try:
        pg.eval_on_selector_all(".anime-card", "els => els[0] ? els[0].click() : null")
        pg.wait_for_timeout(12000)
        detail = pg.eval_on_selector_all("#anime-detail", "els => els.map(e => getComputedStyle(e).display)")
        ep_btns = pg.eval_on_selector_all(".anime-ep-btn", "els => els.length")
        log("6. episodes loaded", ep_btns > 0, f"detail={detail[:1]} {ep_btns} ep buttons")
    except Exception as e:
        log("6. episodes loaded", False, str(e)[:100])

    # 7. Click episode -> player card appears
    try:
        pg.eval_on_selector_all(".anime-ep-btn", "els => els.length ? els[0].click() : null")
        pg.wait_for_timeout(12000)
        player_disp = pg.eval_on_selector_all("#anime-player-card, .anime-player-card", "els => els.map(e => getComputedStyle(e).display)")
        embed_vis = pg.eval_on_selector_all("#anime-embed, .anime-embed", "els => els.map(e => getComputedStyle(e).display)")
        video_vis = pg.eval_on_selector_all("#anime-video, .anime-video", "els => els.map(e => getComputedStyle(e).display)")
        log("7. episode player", any(d != "none" for d in player_disp), f"card={player_disp[:1]} embed={embed_vis[:1]} video={video_vis[:1]}")
    except Exception as e:
        log("7. episode player", False, str(e)[:100])

    log("JS errors", not errors, "; ".join(errors[:3])[:150])
    b.close()

fails = [r for r in results if not r[1]]
print("\n==== SUMMARY ====")
print(f"{len(results)-len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILED:", [f[0] for f in fails])
