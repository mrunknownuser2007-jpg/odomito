import os 
import re 
import unicodedata 
import urllib.parse 
from contextlib import asynccontextmanager 
from fastapi import FastAPI, Form, Request 
from fastapi.responses import FileResponse, JSONResponse 
from fastapi.staticfiles import StaticFiles 
from fastapi.templating import Jinja2Templates 
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask 
import yt_dlp 

DOWNLOAD_DIR = "downloads" 
_YT_URL_PATTERN = re.compile(r"^https?://(www\.)?(youtube\.com/watch\?.*v=[\w-]+|youtu\.be/[\w-]+).*") 

@asynccontextmanager 
async def lifespan(app: FastAPI): 
    os.makedirs(DOWNLOAD_DIR, exist_ok=True) 
    yield 

app = FastAPI(lifespan=lifespan) 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static") 

templates = Jinja2Templates(directory="templates") 

def safe_filename(name: str) -> str: 
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s.-]", "", name)
    return re.sub(r"\s+", "_", name).strip() or "download"

def delete_file(path: str):
    try: os.remove(path)
    except: pass

def _resolve_output_path(info: dict, fmt: str):
    video_id = info.get("id", "")
    ext = "mp3" if fmt == "mp3" else "mp4"
    if not os.path.exists(DOWNLOAD_DIR): return None
    files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.endswith(f".{ext}")]
    if not files: return None
    for f in files:
        if video_id and video_id in f: return f
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0]

@app.get("/") 
async def home(request: Request): 
    return templates.TemplateResponse("index.html", {"request": request}) 

@app.post("/convert") 
async def convert(youtube_url: str = Form(...), fmt: str = Form(...)): 
    if not _YT_URL_PATTERN.match(youtube_url): 
        return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL."}) 

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'ios']}},
    }
    
    if fmt == "mp3":
        ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]})
    else:
        ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            file_path = _resolve_output_path(info, fmt)
            if not file_path or not os.path.exists(file_path):
                return JSONResponse(status_code=500, content={"error": "File conversion failed."})
            
            display_name = f"{safe_filename(info.get('title', 'download'))}.{fmt}"
            headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(display_name)}"}
            return FileResponse(path=file_path, headers=headers, media_type="application/octet-stream", background=BackgroundTask(delete_file, file_path))
    except Exception as e:
        print(f"ERROR: {e}")
        return JSONResponse(status_code=500, content={"error": f"YouTube Error: {str(e)[:150]}"})