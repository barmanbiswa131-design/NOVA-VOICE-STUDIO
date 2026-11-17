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
    rate: str = "+0%"

@app.get("/")
def home():
    return {"service": "NOVA Voice Studio API", "status": "ok"}

@app.get("/voices")
async def voices():
    try:
        all_voices = await edge_tts.list_voices()
        return [v for v in all_voices if v.get("Locale", "").split("-")[0] in {"bn", "hi", "en", "ne"}]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.post("/tts")
async def make_tts(data: TTSRequest):
    if data.rate not in {"-10%", "+0%", "+10%", "+20%"}:
        raise HTTPException(status_code=400, detail="Unsupported speaking rate")
    try:
        output = io.BytesIO()
        communicate = edge_tts.Communicate(data.text, data.voice, rate=data.rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
        audio = output.getvalue()
        if not audio:
            raise RuntimeError("No audio was returned")
        return Response(audio, media_type="audio/mpeg", headers={"Content-Disposition": 'attachment; filename="nova-voice.mp3"', "Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
