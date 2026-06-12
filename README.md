# 🖼️ Image Generating Automation using ChatGPT

> Automate AI image generation via ChatGPT — using **your own Chrome profile**. Just log in once and paste your prompts. No API key needed!

---

## ✨ Features

- 🔗 **Connects to your real Chrome** — no re-login, no new window (via CDP on port 9222)
- 🤖 **Fully automated** — types prompts, waits for generation, saves images
- 🖼️ **Batch generation** — queue multiple prompts at once
- 📁 **Auto-saves** images to a timestamped folder
- 🌐 **Web UI** — clean browser interface at `http://localhost:5050`
- 🔄 **Auto-retry** — retries failed scenes up to 3 times

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/himanshunuq/Image-Generating-Automation-using-ChatGpt.git
cd Image-Generating-Automation-using-ChatGpt
```

### 2. Set Up Virtual Environment & Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # On Windows: .venv\Scripts\activate
pip install flask flask-cors playwright
python -m playwright install chromium
```

### 3. Run the Server

```bash
source .venv/bin/activate
python server.py
```

### 4. Open the Web UI

Open your browser and go to:

```
http://localhost:5050
```

---

## 🔁 Running Again Next Time

```bash
cd Image-Generating-Automation-using-ChatGpt
source .venv/bin/activate
python server.py
```

Then open **http://localhost:5050** in your browser.

> To stop the server, press `Ctrl + C` in the terminal.

---

## 🛠️ How It Works

1. **Click "Connect My Chrome"** in the UI — this relaunches Chrome with a debug port (`9222`) while preserving your session.
2. **Enter your topic** and **paste your image prompts** (one per line).
3. **Click Generate** — the automation types each prompt into ChatGPT, waits for the image, and saves it.
4. Images are saved to a folder like `DyazoX_YourTopic_20260612_090500/`.

---

## 📋 Requirements

- Python 3.8+
- Google Chrome installed
- A ChatGPT account (free or Plus)

---

## 📄 License

MIT License — feel free to use and modify.
