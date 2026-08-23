# 🎙 LessonRecorder

> Record a lesson — get a ready-made summary. Automatically.

---

## What it does

- **Records** sound from your microphone or system audio (captures online lessons, webinars, lectures)
- **Transcribes** speech offline — Whisper AI runs directly on your computer, no internet needed
- **Creates a summary** using free AI — structured notes with headings and key takeaways
- **Saves history** of all lessons with search and file export
- **Self-updates** — notifies you when a new version is available, one click to install

---

## For engineers / reviewers

**Pipeline:** `recorder` (mic + WASAPI loopback capture) → `transcriber` → optional `photo_ocr` → `summarizer`, wired together in a PyQt6 desktop shell (`ui/`).

Transcription (`core/transcriber.py`, `core/transcribe_worker.py`) runs Whisper in a **separate subprocess**, not in-process. Reason: `faster-whisper`'s ctranslate2 backend can hard-crash the process on certain CPUs (AVX2/native issues) with no catchable Python exception — see `NATIVE_CRASH_CODES` in `core/transcriber.py`. Isolating it in a worker process means the crash just becomes a bad exit code, and the app can catch it and transparently retry with plain `openai-whisper` instead of taking the whole GUI down with it.

The summarizer (`core/summarizer.py`) doesn't hardcode a single LLM vendor — it's a small `PROVIDERS` dict describing each backend (base URL, models, auth) behind one OpenAI-compatible HTTP client. That's deliberate: it lets a user in any region pick a provider that's actually reachable and affordable for them, instead of the app being useless the moment one API is blocked, rate-limited, or too expensive.

**GigaChat (Sber) is a first-class provider here**, not an afterthought — it authenticates through Sber's own OAuth flow (`client_id`/`secret` → bearer token, `https://gigachat.devices.sberbank.ru/api/v1`), has a free tier of 150k tokens/month, and was included specifically so the app doesn't only support international LLMs — it supports Sber's own model on equal footing.

Tech stack:
- **PyQt6** — desktop UI
- **openai-whisper** / **faster-whisper** — offline speech-to-text, with subprocess isolation + automatic fallback between the two
- **sounddevice** + **scipy** — cross-platform audio I/O, plus WASAPI loopback capture on Windows for recording system audio
- **pytesseract** + **OpenCV** — OCR on whiteboard/slide photos
- **requests**-based OpenAI-compatible client — talks to DeepSeek, GigaChat, Groq, Gemini, OpenRouter, or any custom endpoint through one code path

Tests: `pip install -r requirements-dev.txt && pytest`

---

## Installation

### Windows

1. Go to [Releases](../../releases)
2. Download `LessonRecorder_vX.X.X_Windows_setup.exe`
3. Run it — the installer will automatically download Python and all components
4. Launch from the Start menu

> No need to install Python separately — everything happens automatically

### macOS

1. Download `LessonRecorder_vX.X.X_macOS.dmg`
2. Open the DMG and drag the icon to Applications
3. First launch: **right-click → Open → Open**

> If needed: `brew install python3`

### Linux

1. Download `LessonRecorder_vX.X.X_Linux.AppImage`
2. Make it executable and run:

```
chmod +x LessonRecorder_*.AppImage
./LessonRecorder_*.AppImage
```

---

## First-time setup

### Transcription (works offline)

Open **Settings → Transcription** and choose a model:

| Model | Speed | Quality | Best for |
|-------|-------|---------|----------|
| `tiny` | ⚡ Very fast | Good | Quick notes, clear audio |
| `base` | Fast | Better | **Recommended** |
| `small` | Medium | Great | Important lectures |
| `medium` | Slow | Excellent | Maximum quality |

The model downloads once on first use and is cached locally.

### AI Summary (internet required, free)

Open **Settings → AI Provider** and choose one:

| Provider | Free limit | Sign up |
|----------|-----------|---------|
| **Groq** | 14,400 requests/day | [console.groq.com](https://console.groq.com) |
| **Google Gemini** | 250 requests/day | [aistudio.google.com](https://aistudio.google.com) |
| **OpenRouter** | 50 req/day (free models) | [openrouter.ai](https://openrouter.ai) |
| **DeepSeek** | Very cheap (~$1 for months) | [platform.deepseek.com](https://platform.deepseek.com) |

No credit card required. Paste your key → **Test connection** → Save.

---

## How to use

1. Open the **Record** tab
2. Choose audio source: Microphone / System audio / Both
3. Click **Start Recording**
4. When done — click **Stop**. Transcription starts automatically
5. After transcription, click **Generate Summary**
6. All lessons are saved in the **History** tab

---

## Tips

- Use **"Both sources"** for online lessons — captures both your voice and the teacher's audio
- First transcription takes ~30 seconds (model loading), all subsequent ones are instant
- Add **photos of the whiteboard or slides** via the 📷 button — text from them will be included in the summary
- If a provider is unavailable in your region — try another one from the list

---

## System requirements

| | Minimum |
|---|---|
| Windows | 10 or 11, 64-bit |
| macOS | 10.15 or newer |
| Linux | Ubuntu 20.04 or newer |
| RAM | 4 GB (8 GB recommended) |
| Disk space | 2 GB |
| Internet | Not needed for recording and transcription |

---

## Support

- Telegram: [@rendergm](https://t.me/rendergm)
- Website: [rendergames.tilda.ws](https://rendergames.tilda.ws)
- Support the project: [Boosty](https://boosty.to/rendergamesru)
