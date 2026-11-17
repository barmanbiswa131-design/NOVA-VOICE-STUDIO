# NOVA VOICE STUDIO

A lightweight personal narration studio for Bangla, Hindi, English and Nepali.

## Current features
- Responsive web interface
- Device voice preview using browser speech synthesis
- Male/female voice filtering when connected to the API
- MP3 generation through the Edge TTS API
- No login, script history, database or server-side audio storage

## Website
GitHub Pages deploys the static frontend. The first deployment runs through the GitHub Actions workflow in `.github/workflows/pages.yml`.

## TTS backend
The Python API is in `server.py`. It uses FastAPI and Edge TTS.

Install and run:
```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Enter the public HTTPS address of the running API in the website's TTS Server Address field. GitHub Pages only hosts the frontend; it does not run this Python server. Do not publish API keys or private credentials in this repository.

Generated audio is returned to the browser and is not saved by this application. Edge TTS requires an internet connection and availability of the upstream voice service.
