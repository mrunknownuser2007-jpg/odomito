from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp, os, uuid, shutil, requests

app = FastAPI()
os.makedirs("downloads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

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
    return templates.TemplateResponse(request, "index.html")

def try_yt_dlp(url, format):
    file_id = str(uuid.uuid4())
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'retries': 2,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android', 'mweb', 'tv_embedded'],
                'player_skip': ['webpage', 'configs'],  # 429 ka main fix
            }
        },
    }
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = 'cookies.txt'
    if format == "mp3":
        ydl_opts['format'] = 'bestaudio/best'
        if shutil.which("ffmpeg"):
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
    else:
        ydl_opts['format'] = 'best[ext=mp4]/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        for f in os.listdir("downloads"):
            if f.startswith(file_id):
                return os.path.join("downloads", f), info.get('title','video')
    return None, None

def try_cobalt(url, format):
    # Cobalt API - Render IP bypass
    file_id = str(uuid.uuid4())
    ext = "mp3" if format=="mp3" else "mp4"
    try:
        r = requests.post("https://api.cobalt.tools/api/json", json={
            "url": url,
            "vCodec": "h264",
            "vQuality": "720",
            "aFormat": "mp3" if format=="mp3" else "best",
            "isAudioOnly": format=="mp3"
        }, headers={"Accept":"application/json"}, timeout=30)
        data = r.json()
        dl_url = data.get('url')
        if not dl_url:
            return None, None
        file_path = f"downloads/{file_id}.{ext}"
        with requests.get(dl_url, stream=True, timeout=60) as rr:
            with open(file_path, 'wb') as f:
                for chunk in rr.iter_content(1024*1024):
                    f.write(chunk)
        return file_path, "video"
    except Exception as e:
        print(f"Cobalt failed: {e}")
        return None, None

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    try:
        url = get_clean_url(url)
        print(f"Trying: {url}")
        # 1st try: yt-dlp + bgutil
        try:
            path, title = try_yt_dlp(url, format)
            if path:
                return {"status":"success","file": path,"title": title}
        except Exception as e:
            print(f"yt-dlp failed: {e}")

        # 2nd try: Cobalt fallback
        path, title = try_cobalt(url, format)
        if path:
            return {"status":"success","file": path,"title": title}

        raise Exception("Both methods failed - YouTube blocked this IP. Try again after 2 mins.")

    except Exception as e:
        print(f"ERROR: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download")
async def download_file(file: str):
    if os.path.exists(file):
        return FileResponse(file, filename=os.path.basename(file))
    return JSONResponse(status_code=404, content={"error":"File not found"})
