from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp
import os
import uuid
import shutil

app = FastAPI()

# Folders create karo
os.makedirs("downloads", exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    try:
        file_id = str(uuid.uuid4())
        
        # FIX 1: YouTube bot block bypass
        ydl_opts = {
            'outtmpl': f'downloads/{file_id}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            # Ye 3 lines Render ke bot issue ko fix karengi
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'extractor_retries': 3,
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; SM-G998B) gzip',
            }
        }

        # Check karo cookies.txt hai kya
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = 'cookies.txt'

        if format == "mp3":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Downloaded file ka naam nikalo
            filename = ydl.prepare_filename(info)
            if format == "mp3":
                filename = os.path.splitext(filename)[0] + ".mp3"
            
            # Agar file mp4 me bhi .webm hai toh usko dhundo
            if not os.path.exists(filename):
                # fallback check
                for f in os.listdir("downloads"):
                    if f.startswith(file_id):
                        filename = os.path.join("downloads", f)
                        break

        return {"status": "success", "file": filename, "title": info.get('title', 'video')}

    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: {error_msg}")
        # User ko saaf error bhejo
        if "Sign in to confirm" in error_msg or "bot" in error_msg:
            return JSONResponse(status_code=500, content={"error": "YouTube is blocking server IP. Please try again after 2 mins or try different video."})
        return JSONResponse(status_code=500, content={"error": error_msg})

@app.get("/download")
async def download_file(file: str):
    if os.path.exists(file):
        return FileResponse(file, filename=os.path.basename(file), media_type='application/octet-stream')
    return JSONResponse(status_code=404, content={"error": "File not found"})
