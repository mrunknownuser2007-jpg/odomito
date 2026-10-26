from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp
import os
import uuid
import re
import shutil

app = FastAPI()
os.makedirs("downloads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def clean_url(url: str) -> str:
    # si= parameter aur extra cheeze hatao, shorts ko normal banao
    url = url.strip()
    url = re.sub(r'\?si=.*', '', url)
    url = re.sub(r'&si=.*', '', url)
    # youtu.be/shorts/ ko handle karo
    if "/shorts/" in url:
        video_id = url.split("/shorts/")[1].split("?")[0].split("/")[0]
        url = f"https://www.youtube.com/watch?v={video_id}"
    return url

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    try:
        url = clean_url(url)
        file_id = str(uuid.uuid4())

        # SABSE STRONG YDL OPTIONS - Bot + Format dono fix
        ydl_opts = {
            'outtmpl': f'downloads/{file_id}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'ios'],
                    'player_skip': ['webpage'],
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12) gzip',
            }
        }

        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = 'cookies.txt'

        # FORMAT FIX - yehi tera error tha
        has_ffmpeg = shutil.which("ffmpeg") is not None
        
        if format == "mp3":
            if has_ffmpeg:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                # Agar ffmpeg nahi hai to m4a dega, jo phone me mp3 jaisa hi bajega
                ydl_opts.update({
                    'format': 'bestaudio[ext=m4a]/bestaudio/best',
                })
        else: # mp4
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # final file dhundo
            downloaded_file = None
            for f in os.listdir("downloads"):
                if f.startswith(file_id):
                    downloaded_file = os.path.join("downloads", f)
                    break
            
            if not downloaded_file:
                raise Exception("Download hua par file nahi mili")

        return {"status": "success", "file": downloaded_file, "title": info.get('title', 'video')}

    except Exception as e:
        print(f"ERROR FULL: {e}")
        msg = str(e)
        # User friendly error
        if "Sign in" in msg or "bot" in msg:
            msg = "YouTube ne server ko block kiya. 2 min baad try karo ya cookies.txt add karo."
        elif "format is not available" in msg:
            msg = "Ye format available nahi hai, MP4 try karo."
        return JSONResponse(status_code=500, content={"error": msg})

@app.get("/download")
async def download_file(file: str):
    # Security: sirf downloads folder ki file
    if not file.startswith("downloads/"):
        return JSONResponse(status_code=400, content={"error": "Invalid file"})
    if os.path.exists(file):
        return FileResponse(file, filename=os.path.basename(file), media_type='application/octet-stream')
    return JSONResponse(status_code=404, content={"error": "File not found"})
