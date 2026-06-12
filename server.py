import os
import json
import time
import socket
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

# Global state for progress tracking
generation_state = {
    "running": False,
    "total": 0,
    "current": 0,
    "topic": "",
    "folder": "",
    "log": [],
    "failed": [],
    "done": False,
}


def reset_state():
    generation_state.update({
        "running": False,
        "total": 0,
        "current": 0,
        "topic": "",
        "folder": "",
        "log": [],
        "failed": [],
        "done": False,
    })


def add_log(scene, status, message):
    generation_state["log"].append({
        "scene": scene,
        "status": status,
        "message": message,
    })


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chrome-status")
def chrome_status():
    """Check whether Chrome's debug port is open."""
    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=1):
            return jsonify({"connected": True})
    except OSError:
        return jsonify({"connected": False})


@app.route("/setup-chrome", methods=["POST"])
def setup_chrome():
    """
    Kill Chrome completely and relaunch it with --remote-debugging-port=9222
    so Playwright can connect directly to YOUR existing browser session.
    All logins (ChatGPT etc.) are preserved because we use your real profile.
    """
    script = r"""
    # Gracefully quit Chrome to avoid the "Restore pages?" crash prompt
    osascript -e 'tell application "Google Chrome" to quit' 2>/dev/null
    
    # Wait up to 6 seconds for graceful shutdown
    for i in {1..6}; do
        if ! pgrep -f "Google Chrome" > /dev/null; then break; fi
        sleep 1
    done

    # Force kill any stubborn leftover processes
    pkill -9 -f "Google Chrome" 2>/dev/null
    sleep 2

    # Remove lock files so Chrome accepts the debug flag
    PROFILE="$HOME/Library/Application Support/Google/Chrome"
    rm -f "$PROFILE/SingletonLock"
    rm -f "$PROFILE/SingletonSocket"
    rm -f "$PROFILE/SingletonCookie"
    rm -f "$PROFILE/Default/SingletonLock"

    # Relaunch Chrome with debug port + your real profile
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --remote-debugging-port=9222 \
      --user-data-dir="$PROFILE" \
      --profile-directory=Default \
      --no-first-run \
      --restore-last-session > /dev/null 2>&1 &

    # Give Chrome time to start
    sleep 7
    """
    try:
        subprocess.run(["bash", "-c", script], timeout=25)
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Check if port is open
    for _ in range(5):
        try:
            with socket.create_connection(("127.0.0.1", 9222), timeout=1):
                return jsonify({"status": "ok",
                                "message": "✅ Chrome connected! Port 9222 is open."})
        except OSError:
            time.sleep(2)

    return jsonify({"status": "ok",
                    "message": "⏳ Chrome is starting — wait 10 sec then Generate."})


@app.route("/generate", methods=["POST"])
def generate():
    """Start browser automation in a background thread."""
    import threading
    from chatgpt_browser import run_generation

    data = request.json
    topic = data.get("topic", "DyazoX_Short").strip()
    prompts = data.get("prompts", [])

    if not prompts:
        return jsonify({"error": "No prompts provided"}), 400

    reset_state()
    generation_state["running"] = True
    generation_state["total"] = len(prompts)
    generation_state["topic"] = topic

    folder_name = f"DyazoX_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(folder_name, exist_ok=True)
    generation_state["folder"] = folder_name

    def run():
        try:
            success, failed = run_generation(
                prompts=prompts,
                folder_name=folder_name,
                log_fn=add_log,
            )
            generation_state["failed"] = failed
            add_log(-1, "done",
                    f"🎉 Done! {success}/{len(prompts)} images saved to '{folder_name}'")
        except Exception as exc:
            add_log(-1, "error", f"❌ Fatal error: {exc}")
        finally:
            generation_state["running"] = False
            generation_state["done"] = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started", "folder": folder_name})


@app.route("/progress")
def progress():
    """Server-Sent Events — streams live log entries to the browser UI."""
    def event_stream():
        sent = 0
        while True:
            logs = generation_state["log"]
            while sent < len(logs):
                yield f"data: {json.dumps(logs[sent])}\n\n"
                sent += 1
            if generation_state["done"]:
                yield f"data: {json.dumps({'scene': -99, 'status': 'finished', 'message': 'STREAM_END'})}\n\n"
                break
            time.sleep(0.3)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/status")
def status():
    return jsonify(generation_state)


if __name__ == "__main__":
    print("\n🎬 DyazoX Image Generator  (ChatGPT Browser Automation)")
    print("=" * 55)
    print("✅ Open your browser at: http://localhost:5050")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
