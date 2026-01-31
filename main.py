"""SARA OMEGA v2.5.2 PASS 7 - Railway Production"""
import os, re, time, hashlib, logging, json
from typing import Optional, Dict, List
from datetime import datetime
from collections import defaultdict
from fastapi import FastAPI, UploadFile, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import speech, texttospeech, vision, translate_v2 as translate
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
logger = logging.getLogger(__name__)

OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "")
TEST_TOKEN = os.environ.get("TEST_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
KILL_SWITCH = os.environ.get("KILL_SWITCH", "false").lower() == "true"
FEATURE_VISION = os.environ.get("FEATURE_VISION", "true").lower() == "true"
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Two-tier access system
RATE_LIMITS = {
    "owner": {
        "requests_per_day": None,      # Unlimited
        "voice_per_day": None,         # Unlimited voice calls
        "vision_per_day": None,        # Unlimited OCR
        "max_context": None            # Unlimited conversation length
    },
    "tester": {
        "requests_per_day": 200,       # 200 requests per day (generous)
        "voice_per_day": 30,           # 30 voice calls per day
        "vision_per_day": 50,          # 50 OCR per day
        "max_context": 50              # 50 messages per conversation (long!)
    }
}

app = FastAPI(title="SARA OMEGA", version="2.5.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

stt_client = tts_client = vision_client = translate_client = llm_client = None
try:
    stt_client = speech.SpeechClient()
    tts_client = texttospeech.TextToSpeechClient()
    vision_client = vision.ImageAnnotatorClient()
    translate_client = translate.Client()
    if OPENAI_API_KEY: llm_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("Clients initialized")
except Exception as e:
    logger.error(f"Init error: {e}")

SESSION, AUDIT, RATE_LIMIT, startup_time = {}, [], defaultdict(list), time.time()

def sha512_hash(data: str) -> str:
    return hashlib.sha512(data.encode()).hexdigest()

def clean_text(text: str, max_length: int = 500) -> str:
    return re.sub(r'[<>{}[\]\\`]', '', text)[:max_length].strip()

def authorize(req: Request) -> Optional[str]:
    if KILL_SWITCH: return None
    auth = req.headers.get("Authorization", "")
    if auth == f"Bearer {OWNER_TOKEN}": return "owner"
    if auth == f"Bearer {TEST_TOKEN}": return "tester"
    return None

def audit(event: str, details: Optional[Dict] = None):
    entry = {"timestamp": int(time.time()), "iso_time": datetime.utcnow().isoformat(), "event": event, "details": details or {}, "hash": sha512_hash(f"{event}:{int(time.time())}")}
    AUDIT.append(entry)
    if len(AUDIT) > 1000: AUDIT.pop(0)

def check_rate_limit(identifier: str, role: str, limit_type: str = "requests") -> bool:
    limits = RATE_LIMITS.get(role, RATE_LIMITS["tester"])
    
    # Owner has no limits
    if role == "owner":
        return True
    
    # Get the appropriate limit
    if limit_type == "voice":
        daily_limit = limits["voice_per_day"]
    elif limit_type == "vision":
        daily_limit = limits["vision_per_day"]
    else:
        daily_limit = limits["requests_per_day"]
    
    # Check daily limit
    now = time.time()
    today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    
    # Get requests for today
    key = f"{identifier}:{limit_type}"
    requests = [t for t in RATE_LIMIT[key] if t > today_start]
    
    if daily_limit and len(requests) >= daily_limit:
        return False
    
    RATE_LIMIT[key].append(now)
    return True

def get_max_context(role: str) -> int:
    limits = RATE_LIMITS.get(role, RATE_LIMITS["tester"])
    max_ctx = limits["max_context"]
    return max_ctx if max_ctx else 1000  # 1000 = effectively unlimited

def think(session_id: str, text: str, role: str = "tester") -> str:
    if not llm_client: return "AI not configured. Set OPENAI_API_KEY."
    try:
        ctx = SESSION.get(session_id, [])
        ctx.append({"role": "user", "content": clean_text(text, 1000)})
        
        # Apply role-based context limit
        max_context = get_max_context(role)
        ctx = ctx[-max_context:] if max_context else ctx
        
        response = llm_client.chat.completions.create(model="gpt-4o-mini", messages=ctx, temperature=0.6, max_tokens=500)
        answer = response.choices[0].message.content
        ctx.append({"role": "assistant", "content": answer})
        SESSION[session_id] = ctx
        audit("llm_completion", {"session_id": session_id, "tokens": response.usage.total_tokens, "role": role})
        return answer
    except Exception as e:
        logger.error(f"Think error: {e}")
        return "Error processing request."

@app.get("/")
def root():
    return {"name": "SARA OMEGA", "version": "2.5.2", "status": "online" if not KILL_SWITCH else "disabled", "platform": "Railway"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "2.5.2", "platform": "Railway", "timestamp": datetime.utcnow().isoformat(), "uptime": int(time.time() - startup_time), "dependencies": {"google_cloud": stt_client is not None, "openai": llm_client is not None}, "features": {"voice": True, "vision": FEATURE_VISION}, "kill_switch": KILL_SWITCH}

@app.get("/health/ready")
def readiness():
    if KILL_SWITCH: raise HTTPException(503, "Service disabled")
    return {"ready": True}

@app.get("/health/live")
def liveness():
    return {"alive": True}

@app.get("/metrics")
def metrics():
    return Response(f"sara_active_sessions {len(SESSION)}\nsara_audit_entries {len(AUDIT)}\n", media_type="text/plain")

@app.post("/voice")
async def voice(req: Request, file: UploadFile, session_id: str, location: str = ""):
    if not (role := authorize(req)): raise HTTPException(401, "Unauthorized")
    if not check_rate_limit(f"voice:{session_id}", role, "voice"): raise HTTPException(429, f"Daily voice limit reached ({RATE_LIMITS[role]['voice_per_day']} per day)")
    if not stt_client or not tts_client: raise HTTPException(503, "Voice unavailable")
    try:
        audio = await file.read()
        if len(audio) > MAX_AUDIO_BYTES: raise HTTPException(413, "Audio too large")
        rec = speech.RecognitionAudio(content=audio)
        cfg = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=16000, language_code="en-US", enable_automatic_punctuation=True)
        stt_response = stt_client.recognize(config=cfg, audio=rec)
        if not stt_response.results: return JSONResponse(400, {"error": "No speech"})
        transcript = " ".join([r.alternatives[0].transcript for r in stt_response.results])
        reply = think(session_id, transcript, role)
        synthesis = texttospeech.SynthesisInput(text=reply)
        voice_params = texttospeech.VoiceSelectionParams(language_code="en-GB", name="en-GB-Wavenet-C")
        audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        tts_response = tts_client.synthesize_speech(input=synthesis, voice=voice_params, audio_config=audio_cfg)
        audit("voice_interaction", {"session_id": session_id, "role": role})
        return Response(tts_response.audio_content, media_type="audio/mpeg")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/vision")
async def vision_read(req: Request, file: UploadFile, target_lang: str = "en"):
    if not (role := authorize(req)): raise HTTPException(401, "Unauthorized")
    if not FEATURE_VISION: raise HTTPException(403, "Vision disabled")
    if not check_rate_limit(f"vision:{req.client.host if req.client else 'unknown'}", role, "vision"): raise HTTPException(429, f"Daily vision limit reached ({RATE_LIMITS[role]['vision_per_day']} per day)")
    if not vision_client: raise HTTPException(503, "Vision unavailable")
    try:
        content = await file.read()
        if len(content) > MAX_IMAGE_BYTES: raise HTTPException(413, "Image too large")
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        if not response.text_annotations: return {"original_text": "", "message": "No text"}
        text = response.text_annotations[0].description
        translated = translate_client.translate(text, target_language=target_lang)["translatedText"] if target_lang != "en" and translate_client else text
        audit("vision_ocr", {"role": role, "target_lang": target_lang})
        return {"original_text": text, "translated_text": translated, "target_language": target_lang}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/admin/stats")
def admin_stats(req: Request):
    if authorize(req) != "owner": raise HTTPException(403, "Owner only")
    return {
        "version": "2.5.2", 
        "platform": "Railway", 
        "uptime": int(time.time() - startup_time), 
        "sessions": len(SESSION), 
        "audit": len(AUDIT), 
        "rate_limits": RATE_LIMITS,
        "features": {"voice": stt_client is not None, "vision": vision_client is not None}, 
        "kill_switch": KILL_SWITCH
    }
