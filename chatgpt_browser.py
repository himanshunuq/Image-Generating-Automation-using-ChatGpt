"""
chatgpt_browser.py — DyazoX Image Generator
============================================
Two connection modes, tried in order:

  1. CDP (preferred) — connects to YOUR already-running Chrome on port 9222.
     Click "Connect My Chrome" in the web UI once to enable this.
     After that, ChatGPT is always already logged in — no login screen ever.

  2. Playwright Chromium fallback — opens our own Chromium window.
     First use: log in once → session saved to chrome_profile/.
     Every use after: auto-logged in (no login screen).
"""

import os
import time
import base64
import socket

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CDP_URL     = "http://localhost:9222"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────
def run_generation(prompts, folder_name, log_fn):
    success = 0
    failed  = []

    with sync_playwright() as p:
        context, using_cdp = _connect(p, log_fn)
        page = _get_or_new_page(context)

        _ensure_chatgpt(page, log_fn)

        for idx, prompt in enumerate(prompts):
            scene = idx + 1
            log_fn(scene, "generating", f"Generating Scene {scene}...")

            saved = False
            for attempt in range(1, 4):
                try:
                    path = _generate_one(page, prompt, folder_name, scene, log_fn)
                    log_fn(scene, "success",
                           f"✅ Scene {scene} saved → {os.path.basename(path)}")
                    success += 1
                    saved = True
                    break
                except Exception as exc:
                    if attempt < 3:
                        log_fn(scene, "retrying",
                               f"⚠️ Scene {scene} attempt {attempt} failed, "
                               f"retrying in 5s… ({exc})")
                        time.sleep(5)
                    else:
                        log_fn(scene, "error", f"❌ Scene {scene} failed: {exc}")
                        failed.append(scene)

        # Only close if we opened our own browser (not the user's Chrome)
        if not using_cdp:
            context.close()

    return success, failed


# ─────────────────────────────────────────────────────────────
# Connection helpers
# ─────────────────────────────────────────────────────────────
def _port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=1):
            return True
    except OSError:
        return False


def _connect(p, log_fn):
    """
    Try CDP (your real Chrome) first.
    Fall back to Playwright's own Chromium with a saved profile.
    Returns (context, using_cdp).
    """
    if _port_open():
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL, timeout=5000)
            log_fn(0, "info",
                   "🔗 Connected to YOUR Chrome — no new window, no login needed!")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            return ctx, True
        except Exception as e:
            log_fn(0, "info", f"⚠️ CDP connection failed ({e}), using fallback...")

    log_fn(0, "info",
           "🚀 Opening Chromium window (your saved session)... "
           "Tip: click 'Connect My Chrome' in the UI to use your real Chrome instead.")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        channel="chromium",
        args=[
            "--start-maximized",
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications",
        ],
        no_viewport=True,
    )
    return ctx, False


def _get_or_new_page(context):
    pages = context.pages
    return pages[0] if pages else context.new_page()


# ─────────────────────────────────────────────────────────────
# ChatGPT helpers
# ─────────────────────────────────────────────────────────────
def _ensure_chatgpt(page, log_fn):
    log_fn(0, "info", "🌐 Navigating to ChatGPT...")
    page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Check for login wall
    try:
        page.wait_for_selector(
            'button:has-text("Log in"), a:has-text("Log in"), '
            'button:has-text("Sign in"), a:has-text("Sign in")',
            timeout=4000,
        )
        log_fn(0, "login_required",
               "⚠️ Please log in to ChatGPT in the browser window. "
               "Generation starts automatically after login.")
        _wait_for_login(page, log_fn)
    except PWTimeout:
        pass  # Already logged in ✅

    log_fn(0, "info", "✅ ChatGPT ready! Starting generation...")


def _wait_for_login(page, log_fn, timeout_secs=300):
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        try:
            page.wait_for_selector(
                'button:has-text("Log in"), a:has-text("Log in")',
                timeout=3000,
            )
            time.sleep(3)
        except PWTimeout:
            return
    raise RuntimeError("Login timed out (5 min).")


# ─────────────────────────────────────────────────────────────
# Image generation — one scene
# ─────────────────────────────────────────────────────────────
def _generate_one(page, prompt, folder_name, scene_num, log_fn) -> str:
    # ── Record existing images to differentiate from the new one ─
    time.sleep(1)
    try:
        existing_srcs = set()
        for el in page.query_selector_all('img'):
            box = el.bounding_box()
            if box and box.get("width", 0) >= 150:
                src = el.get_attribute("src")
                if src:
                    existing_srcs.add(src)
    except Exception:
        existing_srcs = set()

    # ── Find the input box ──────────────────────────────────
    input_el = None
    for sel in [
        "#prompt-textarea",
        "div[contenteditable='true'][data-lexical-editor]",
        "div[contenteditable='true']",
        "textarea",
    ]:
        try:
            el = page.wait_for_selector(sel, state="visible", timeout=10000)
            if el:
                input_el = el
                break
        except PWTimeout:
            continue

    if input_el is None:
        raise RuntimeError("Could not find the ChatGPT input box.")

    # ── Type the prompt ─────────────────────────────────────
    full_prompt = (
        f"Generate a image "
        f"vertical 9:16 composition. :"
        f"{prompt}"
    )
    input_el.click()
    time.sleep(0.4)
    page.keyboard.press("Meta+a")
    page.keyboard.press("Backspace")
    time.sleep(0.2)
    page.keyboard.type(full_prompt, delay=15)
    time.sleep(0.8)

    # ── Send message ────────────────────────────────────────
    sent = False
    for sel in [
        'button[data-testid="send-button"]:not([disabled])',
        'button[aria-label="Send message"]:not([disabled])',
        'button[aria-label="Send prompt"]:not([disabled])',
    ]:
        try:
            page.wait_for_selector(sel, timeout=5000).click()
            sent = True
            break
        except PWTimeout:
            continue
    if not sent:
        page.keyboard.press("Enter")

    log_fn(scene_num, "generating",
           f"⏳ Scene {scene_num}: Waiting for ChatGPT to generate image (up to 2 min)...")

    # ── Wait for the NEW image to fully load ───────────────────
    img_el = _wait_for_image(page, existing_srcs, timeout_secs=120)
    if img_el is None:
        raise RuntimeError("Image did not appear within 2 minutes.")

    # Scroll into view and give it 2 seconds to fully render
    try:
        img_el.scroll_into_view_if_needed()
    except Exception:
        pass
    time.sleep(2)

    # ── Save the image (3 strategies, most-reliable first) ─
    file_path = os.path.join(folder_name, f"Scene_{str(scene_num).zfill(2)}.png")

    # ── Strategy 1: Element screenshot — always works ───────
    try:
        img_el.screenshot(path=file_path)
        size = os.path.getsize(file_path)
        if size > 5000:   # real PNG is at least 5 KB
            log_fn(scene_num, "generating",
                   f"📸 Scene {scene_num}: saved via screenshot ({size//1024} KB)")
            return file_path
    except Exception as e:
        log_fn(scene_num, "retrying", f"Screenshot failed: {e}")

    # ── Strategy 2: JS fetch (full original quality) ────────
    try:
        _fetch_via_js(page, img_el, file_path)
        size = os.path.getsize(file_path)
        if size > 5000:
            log_fn(scene_num, "generating",
                   f"🌐 Scene {scene_num}: saved via JS fetch ({size//1024} KB)")
            return file_path
    except Exception as e:
        log_fn(scene_num, "retrying", f"JS fetch failed: {e}")

    # ── Strategy 3: Click ChatGPT download button ───────────
    try:
        _click_download(page, file_path)
        return file_path
    except Exception as e:
        raise RuntimeError(f"All save strategies failed. Last error: {e}")


# ─────────────────────────────────────────────────────────────
# Image detection
# ─────────────────────────────────────────────────────────────
def _wait_for_image(page, existing_srcs, timeout_secs=120):
    """
    Poll until a NEW large fully-rendered image appears on the page.
    """
    deadline = time.time() + timeout_secs

    while time.time() < deadline:
        try:
            # Check all images on the page, starting from most recently added
            for el in reversed(page.query_selector_all('img')):
                box = el.bounding_box()
                src = el.get_attribute("src") or ""
                
                # If it's a large image and wasn't there before we sent the prompt
                if box and box.get("width", 0) >= 150 and src and src not in existing_srcs:
                    # Confirm image is actually loaded
                    natural_w = page.evaluate("el => el.naturalWidth", el)
                    if natural_w and natural_w > 50:
                        return el
        except Exception:
            pass
        time.sleep(2)

    return None


# ─────────────────────────────────────────────────────────────
# Save helpers
# ─────────────────────────────────────────────────────────────
def _click_download(page, file_path):
    """Click ChatGPT's native download icon — hover over image first to reveal it."""
    try:
        page.locator('img[src*="oaiusercontent"]').last.hover()
        time.sleep(0.5)
    except Exception:
        pass

    btn = page.locator(
        'button[aria-label*="Download" i], '
        '[data-testid*="download" i], '
        'button:has-text("Download")'
    ).last
    with page.expect_download(timeout=20000) as dl_info:
        btn.click(timeout=5000)
    dl_info.value.save_as(file_path)


def _fetch_via_js(page, img_el, file_path):
    """Fetch full-resolution image bytes from inside the browser page context."""
    src = img_el.get_attribute("src") or ""

    if src.startswith("data:image"):
        _, b64 = src.split(",", 1)
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(b64))
        return

    if src.startswith("blob:") or src.startswith("https:"):
        b64_data = page.evaluate(
            """async (url) => {
                const r = await fetch(url, {cache: 'force-cache'});
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const buf = await r.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let result = '';
                const chunk = 8192;
                for (let i = 0; i < bytes.length; i += chunk) {
                    result += String.fromCharCode(...bytes.subarray(i, i + chunk));
                }
                return btoa(result);
            }""",
            src,
        )
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        return

    raise RuntimeError(f"Unknown img src scheme: {src[:50]}")
