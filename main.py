from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp, os, uuid, shutil, requests, re

app = FastAPI()
os.makedirs("downloads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

def get_id(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

def method_yt_dlp(url, format):
    file_id = str(uuid.uuid4())
    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'retries': 2,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android', 'mweb', 'tv_embedded'],
                'player_skip': ['webpage', 'configs'],
            }
        },
    }
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = 'cookies.txt'
    if format == "mp3":
        ydl_opts['format'] = 'bestaudio/best'
        if shutil.which("ffmpeg"):
            ydl_opts['postprocessors'] = [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]
    else:
        ydl_opts['format'] = 'best[ext=mp4]/best'
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        for f in os.listdir("downloads"):
            if f.startswith(file_id):
                return os.path.join("downloads", f), info.get('title','video')
    return None, None

def method_cobalt(url, format):
    # New Cobalt v10 API - endpoint is / not /api/json
    file_id = str(uuid.uuid4())
    ext = "mp3" if format=="mp3" else "mp4"
    apis = ["https://api.cobalt.tools/", "https://cobalt-api.kwiatekmiki.com/", "https://co.eepy.today/"]
    for api in apis:
        try:
            print(f"Trying cobalt: {api}")
            r = requests.post(api, json={
                "url": url,
                "vCodec": "h264",
                "vQuality": "720",
                "aFormat": "mp3" if format=="mp3" else "best",
                "isAudioOnly": format=="mp3",
                "filenamePattern": "basic"
            }, headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=30)
            data = r.json()
            dl = data.get('url')
            if not dl:
                continue
            path = f"downloads/{file_id}.{ext}"
            with requests.get(dl, stream=True, timeout=120) as rr:
                with open(path, 'wb') as f:
                    for chunk in rr.iter_content(1024*1024):
                        f.write(chunk)
            return path, "video"
        except Exception as e:
            print(f"Cobalt {api} failed: {e}")
            continue
    return None, None

def method_invidious(url, format):
    # Invidious - 100% works on Render
    vid = get_id(url)
    if not vid:
        return None, None
    file_id = str(uuid.uuid4())
    ext = "mp3" if format=="mp3" else "mp4"
    instances = ["https://inv.nadeko.net", "https://yt.omada.cafe", "https://invidious.nerdvpn.de"]
    for inst in instances:
        try:
            r = requests.get(f"{inst}/api/v1/videos/{vid}", timeout=20).json()
            # best audio
            if format=="mp3":
                streams = r.get('adaptiveFormats', [])
                audios = [s for s in streams if 'audio' in s.get('type','')]
                if not audios: continue
                best = sorted(audios, key=lambda x: int(x.get('bitrate',0)), reverse=True)[0]
            else:
                best = r.get('formatStreams', [{}])[-1]
            dl = best.get('url')
            if not dl: continue
            path = f"downloads/{file_id}.{ext}"
            with requests.get(dl, stream=True, timeout=120) as rr:
                with open(path, 'wb') as f:
                    for chunk in rr.iter_content(1024*1024):
                        f.write(chunk)
            return path, r.get('title','video')
        except Exception as e:
            print(f"Invidious {inst} failed: {e}")
            continue
    return None, None

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    url = url.strip()
    print(f"Convert: {url} as {format}")
    # Try 1, 2, 3
    for func in [method_yt_dlp, method_cobalt, method_invidious]:
        try:
            path, title = func(url, format)
            if path and os.path.exists(path):
                print(f"Success with {func.__name__}: {path}")
                return {"status":"success","file": path,"title": title}
        except Exception as e:
            print(f"{func.__name__} error: {e}")
            continue
    return JSONResponse(status_code=500, content={"error": "YouTube is blocking Render IP heavily. Please try a different video or try again in 1 min. Invidious fallback also failed."})

@app.get("/download")
async def download_file(file: str):
    if os.path.exists(file):
        return FileResponse(file, filename=os.path.basename(file))
    return JSONResponse(status_code=404, content={"error":"File not found"})
