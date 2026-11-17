# NOVA VOICE STUDIO

A lightweight Hindi narration studio powered by Gemini 3.8 Flash TTS.

## Fixed voices
- Male narrator: Charon — warm, deep, engaging documentary delivery.
- Female co-host: Kore — warm, bright, curious and expressive delivery.
- Permanent style prompts are stored in the backend.
- Single-speaker and two-speaker Hindi narration.
- Optional emotion tags such as [curiosity], [suspense], [excited] and [long pause].
- WAV audio generation; scripts and audio are not stored by this app.

## Website
GitHub Pages hosts the static frontend.

## Backend
The FastAPI backend is in `server.py` and calls the Gemini API from the server. Set the `GEMINI_API_KEY` secret in the Render service Environment Variables. Never put the key in this repository or the browser frontend.

Install and run:
```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

The server uses the `gemini-3.8-flash-tts` model. API availability, free-tier limits and pricing are controlled by Google and may change.
