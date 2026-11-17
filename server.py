import base64
import os
import requests
import wave
import io
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="NOVA Voice Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = "gemini-3.8-flash-tts"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

MALE_VOICE = "Charon"
FEMALE_VOICE = "Kore"

MALE_STYLE = (
    "Speak in natural Indian Hindi. Use a warm, deep, engaging science-documentary "
    "narrator delivery. Keep the same Charon voice identity every time. Sound human, "
    "not robotic. Read the script exactly as written. Follow inline audio tags and "
    "punctuation for emotion: begin curious and energetic, build suspense naturally, "
    "use clear dramatic pauses, explain science seriously, and finish confidently. "
    "Use clear pronunciation and natural pacing. Never shout."
)

FEMALE_STYLE = (
    "Speak in natural Indian Hindi with a warm, expressive, bright co-host delivery. "
    "Keep the same Kore voice identity every time. Sound genuinely curious, friendly, "
    "surprised and engaged, with natural conversational rhythm. Read the script exactly "
    "as written and follow inline audio tags and punctuation for emotion. Use clear "
    "pronunciation. Do not overact or sound robotic."
)

DUAL_STYLE = (
    "Create a natural Indian Hindi science-documentary conversation. MALE is the warm, "
    "deep Charon narrator: confident, engaging and suspenseful. FEMALE is the warm, "
    "bright Kore co-host: curious, expressive and conversational. Keep each speaker's "
    "voice identity consistent throughout. Follow the speaker labels and inline audio "
    "tags. Read only the spoken dialogue, never speak the labels. Use natural pauses "
    "and emotional variation without shouting or overacting."
)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    gender: str = "male"
    rate: str = "+0%"


class Segment(BaseModel):
    speaker: str
    text: str = Field(min_length=1, max_length=5000)


class DualTTSRequest(BaseModel):
    segments: list[Segment] = Field(min_length=1, max_length=60)
    rate: str = "+0%"


def get_api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is missing. Add it in Render Environment Variables."
        )
    return key


def speed_instruction(rate: str) -> str:
    speeds = {
        "-10%": "Speak slightly slower than normal, with clear pauses.",
        "+0%": "Use a natural medium speaking pace.",
        "+10%": "Speak slightly faster while keeping every word clear.",
        "+20%": "Speak briskly but clearly; do not rush pronunciation.",
    }
    if rate not in speeds:
        raise HTTPException(status_code=400, detail="Unsupported speaking speed.")
    return speeds[rate]


def gemini_audio(text: str, voice_config: dict, style: str) -> bytes:
    key = get_api_key()
    prompt = (
        "TTS the following transcript as natural spoken audio. Follow the director's "
        "notes for voice, emotion, accent and pacing. Do not read the director's notes "
        "or the words 'Transcript begins' aloud. Read only the transcript after that label.\n\n"
        "DIRECTOR'S NOTES:\n" + style + "\n\n"
        "TRANSCRIPT BEGINS:\n" + text
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": voice_config,
        },
    }
    try:
        response = requests.post(
            API_URL,
            headers={
                "x-goog-api-key": key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except Exception:
                detail = response.text
            raise HTTPException(
                status_code=502,
                detail=f"Gemini TTS error ({response.status_code}): {detail[:700]}"
            )
        body = response.json()
        parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                audio = base64.b64decode(inline["data"])
                if audio:
                    return audio
        raise RuntimeError("Gemini returned no audio data.")
    except HTTPException:
        raise
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Gemini TTS timed out. Please try again.")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Gemini TTS: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Audio generation failed: {exc}")


def audio_response(audio: bytes, filename: str):
    # Gemini TTS returns a complete WAV file for non-streaming generation.
    if not audio.startswith(b"RIFF"):
        # Some API responses may contain raw 24 kHz, 16-bit mono PCM.
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(audio)
        audio = wav_buffer.getvalue()
    return Response(
        audio,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/")
def home():
    return {
        "service": "NOVA Voice Studio",
        "status": "ok",
        "engine": MODEL,
        "voices": {"male": MALE_VOICE, "female": FEMALE_VOICE},
    }


@app.get("/voices")
def voices():
    # Keep both the structured fixed-voice fields and an array for older frontends
    # that expect data.voices.filter(...).
    return {
        "engine": MODEL,
        "male": {"id": MALE_VOICE, "name": "Charon", "gender": "male", "style": "Deep documentary narrator"},
        "female": {"id": FEMALE_VOICE, "name": "Kore", "gender": "female", "style": "Expressive co-host"},
        "voices": [
            {"id": MALE_VOICE, "name": "Charon", "gender": "male", "style": "Deep documentary narrator"},
            {"id": FEMALE_VOICE, "name": "Kore", "gender": "female", "style": "Expressive co-host"},
        ],
    }


@app.post("/tts")
def make_tts(data: TTSRequest):
    if data.gender not in {"male", "female"}:
        raise HTTPException(status_code=400, detail="Speaker must be male or female.")
    pace = speed_instruction(data.rate)
    if data.gender == "male":
        voice = MALE_VOICE
        style = MALE_STYLE + " " + pace
    else:
        voice = FEMALE_VOICE
        style = FEMALE_STYLE + " " + pace
    audio = gemini_audio(
        data.text,
        {
            "languageCode": "hi-IN",
            "voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": voice}
            },
        },
        style,
    )
    return audio_response(audio, f"nova-hindi-{data.gender}.wav")


@app.post("/tts/dual")
def make_dual_tts(data: DualTTSRequest):
    pace = speed_instruction(data.rate)
    if any(seg.speaker not in {"male", "female"} for seg in data.segments):
        raise HTTPException(status_code=400, detail="Each speaker must be male or female.")
    dialogue = []
    for seg in data.segments:
        alias = "MALE" if seg.speaker == "male" else "FEMALE"
        dialogue.append(f"{alias}: {seg.text.strip()}")
    audio = gemini_audio(
        "\n".join(dialogue),
        {
            "languageCode": "hi-IN",
            "multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": [
                    {
                        "speaker": "MALE",
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": MALE_VOICE}
                        },
                    },
                    {
                        "speaker": "FEMALE",
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": FEMALE_VOICE}
                        },
                    },
                ]
            },
        },
        DUAL_STYLE + " " + pace,
    )
    return audio_response(audio, "nova-hindi-dual.wav")
