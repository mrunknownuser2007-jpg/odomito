from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp
import os
import uuid
import shutil

app = FastAPI()

# Make sure folders exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

templates = Jinja2Templates(directory="templates")

# static folder mount - error na de isliye check
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

def clean_url(url: str):
    # ?si= wala tracker hata do
    return url.split("?si=")[0].split("&")[0].split("?")[0] + "?v=" + url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("?")[0].strip()
    # Simple clean
    # return url.strip()

def get_clean_url(url: str):
    url = url.strip()
    if "youtu.be/" in url:
        return url.split("?")[0]
    if "v=" in url:
        vid = url.split("v=")[1].split("&")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url.split("?")[0]

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # FIX for your error: TypeError: cannot use 'tuple' as a dict key
    # New Starlette needs (request, template_name)
    return templates.TemplateResponse(request, "index.html")

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    try:
        url = get_clean_url(url)
        file_id = str(uuid.uuid4())

        ydl_opts = {
            'outtmpl': f'downloads/{file_id}.%(ext)s',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_args': {
                'youtube': {
                    # web = bgutil ke saath PO Token banega, mweb/android = backup
                    'player_client': ['web', 'mweb', 'android', 'ios'],
                }
            },
            # Render pe JS runtime ke liye
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

        # Agar cookies.txt hai to use karo, nahi to bina uske chalega (bgutil ki wajah se)
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = 'cookies.txt'
            print("Using cookies.txt")

        if format == "mp3":
            ydl_opts['format'] = 'bestaudio/best'
            if shutil.which("ffmpeg"):
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
        else:
            # mp4 ke liye best quality
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

        print(f"Downloading: {url} as {format}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            print(f"Downloaded: {title}")

            # File dhundo
            for f in os.listdir("downloads"):
                if f.startswith(file_id):
                    full_path = os.path.join("downloads", f)
                    return {
                        "status": "success",
                        "file": full_path,
                        "title": title
                    }

        raise Exception("File not found after download")

    except Exception as e:
        print(f"ERROR: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download")
async def download_file(file: str):
    if os.path.exists(file):
        filename = os.path.basename(file)
        return FileResponse(file, filename=filename, media_type='application/octet-stream')
    return JSONResponse(status_code=404, content={"error": "File not found"})

@app.get("/health")
async def health():
    return {"status": "ok"}
