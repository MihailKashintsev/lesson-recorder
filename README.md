# LessonRecorder

> 🎙️ Record lessons → get transcript → generate structured notes. Fully automatic.

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What it does

1. **Records** audio from your microphone and/or system sound (captures online lessons too)
2. **Transcribes** speech offline using Whisper AI — no internet needed
3. **Generates** structured markdown notes via free cloud AI (Groq, Gemini, OpenRouter)
4. **Saves** everything to a local history with search and export
5. **Auto-updates** — notifies you when a new version is available

---

## Installation

1. Go to [Releases](../../releases) and download the latest `LessonRecorder_X.X.X_setup.exe`
2. Run it — no admin rights required
3. Launch **LessonRecorder** from the Start menu or desktop shortcut

---

## First-time setup

### Transcription (works offline)

Open **Settings → Transcription** and choose a Whisper model:

| Model | Speed | Quality | Use when |
|-------|-------|---------|----------|
| `tiny` | ⚡ Very fast | Good | Quick notes, clear audio |
| `base` | Fast | Better | Default recommendation |
| `small` | Medium | Great | Important lectures |
| `medium` | Slow | Excellent | Professional quality |

The model downloads automatically on first use and is cached locally.

### AI Notes (free, requires internet)

Open **Settings → AI Provider** and choose one:

| Provider | Free limit | Sign up |
|----------|-----------|---------|
| **Groq** | 14,400 requests/day | [console.groq.com](https://console.groq.com) |
| **Google Gemini** | 250 requests/day | [aistudio.google.com](https://aistudio.google.com) |
| **OpenRouter** | 50 req/day (free models) | [openrouter.ai](https://openrouter.ai) |
| **Custom URL** | Any OpenAI-compatible API | — |

No credit card required for any of them. Paste your key → click **Test connection** → Save.

---

## How to use

1. Open the **Record** tab
2. Select audio source: Microphone / System audio / Both
3. Click **Start Recording**
4. When done, click **Stop** — transcription starts automatically
5. After transcription, click **Generate Notes** to get an AI summary
6. Find all sessions in the **History** tab

---

## Auto-updates

When a new version is released, the app shows a notification on startup:

> **"Update available: v1.X.X"**  
> Download and install?

Click **Download** — the installer runs silently and restarts the app. No manual steps needed.

---

## System requirements

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 64-bit | Windows 11 |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB | 4 GB |
| Internet | Not needed for transcription | Needed for AI notes |

---

## Tips

- Use **"Both sources"** to capture both your voice and the teacher's audio in online lessons
- First transcription takes ~30 sec (model loading) — all subsequent ones are instant
- Single words and short phrases work fine — the silence filter is disabled
- If Groq is unavailable in your region, switch to Google Gemini — it works everywhere

---

## License

MIT — free to use, modify and distribute.
