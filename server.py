from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
import edge_tts
import io

app = FastAPI(title="NOVA Voice Studio API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str
    gender: str = "female"
    rate: str = "+0%"

class Segment(BaseModel):
    speaker: str
    text: str = Field(min_length=1, max_length=5000)

class DualTTSRequest(BaseModel):
    segments: list[Segment] = Field(min_length=1, max_length=100)
    male_voice: str
    female_voice: str
    rate: str = "+0%"

@app.get("/")
def home():
    return {"service": "NOVA Voice Studio API", "status": "ok"}

@app.get("/voices")
async def voices():
    try:
        all_voices = await edge_tts.list_voices()
        hindi = [v for v in all_voices if v.get("Locale", "").lower().startswith("hi-in") and v.get("ShortName", "").endswith("Neural")]
        return sorted(hindi, key=lambda v: (v.get("Gender", "").lower() != "male", v.get("ShortName", "")))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.post("/tts")
async def make_tts(data: TTSRequest):
    if data.rate not in {"-10%", "+0%", "+10%", "+20%"}:
        raise HTTPException(status_code=400, detail="Unsupported speaking rate")
    if data.gender not in {"male", "female"}:
        raise HTTPException(status_code=400, detail="Speaker must be male or female")
    if not data.voice.startswith("hi-IN-"):
        raise HTTPException(status_code=400, detail="Only Indian Hindi voices are supported")
    try:
        catalog = await edge_tts.list_voices()
        selected = next((v for v in catalog if v.get("ShortName") == data.voice), None)
        if not selected or selected.get("Gender", "").lower() != data.gender:
            raise HTTPException(status_code=400, detail="Selected voice does not match the chosen speaker gender. Reconnect and select again.")
        output = io.BytesIO()
        pitch = "-8Hz" if data.gender == "male" else "+0Hz"
        communicate = edge_tts.Communicate(data.text, data.voice, rate=data.rate, pitch=pitch)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
        audio = output.getvalue()
        if not audio:
            raise RuntimeError("No audio was returned")
        return Response(audio, media_type="audio/mpeg", headers={"Content-Disposition": 'attachment; filename="nova-voice.mp3"', "Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/tts/dual")
async def make_dual_tts(data: DualTTSRequest):
    if data.rate not in {"-10%", "+0%", "+10%", "+20%"}:
        raise HTTPException(status_code=400, detail="Unsupported speaking rate")
    if any(seg.speaker not in {"male", "female"} for seg in data.segments):
        raise HTTPException(status_code=400, detail="Speaker must be male or female")
    if not data.male_voice.startswith("hi-IN-") or not data.female_voice.startswith("hi-IN-"):
        raise HTTPException(status_code=400, detail="Only Indian Hindi voices are supported")
    try:
        catalog = await edge_tts.list_voices()
        by_name = {v.get("ShortName"): v for v in catalog}
        male_info, female_info = by_name.get(data.male_voice), by_name.get(data.female_voice)
        if not male_info or male_info.get("Gender", "").lower() != "male":
            raise HTTPException(status_code=400, detail="The selected MALE voice is not a verified male Hindi voice. Reconnect and choose a male voice.")
        if not female_info or female_info.get("Gender", "").lower() != "female":
            raise HTTPException(status_code=400, detail="The selected FEMALE voice is not a verified female Hindi voice. Reconnect and choose a female voice.")
        output = io.BytesIO()
        for seg in data.segments:
            voice = data.male_voice if seg.speaker == "male" else data.female_voice
            pitch = "-8Hz" if seg.speaker == "male" else "+0Hz"
            communicate = edge_tts.Communicate(seg.text, voice, rate=data.rate, pitch=pitch)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    output.write(chunk["data"])
        audio = output.getvalue()
        if not audio:
            raise RuntimeError("No audio was returned")
        return Response(audio, media_type="audio/mpeg", headers={"Content-Disposition": 'attachment; filename="nova-dual-voice.mp3"', "Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
