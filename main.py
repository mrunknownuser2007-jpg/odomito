from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp, os, uuid, re, shutil
app = FastAPI()
os.makedirs("downloads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def clean_url(url: str):
    url = url.split("?si=")[0].split("&si=")[0]
    if "/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0].split("/")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url.strip()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/convert")
async def convert(url: str = Form(...), format: str = Form(...)):
    try:
        url = clean_url(url)
        file_id = str(uuid.uuid4())
        ydl_opts = {
            'outtmpl': f'downloads/{file_id}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'retries': 10,
            'extractor_args': {'youtube': {'player_client': ['android','web']}},
        }
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = 'cookies.txt'

        # SABSE SIMPLE FORMAT - kabhi fail nahi hoga
        if format == "mp3":
            ydl_opts['format'] = 'bestaudio/best'
            if shutil.which("ffmpeg"):
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]
        else:
            ydl_opts['format'] = 'best' # best matlab jo bhi mile mp4/webm sab chalega
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            for f in os.listdir("downloads"):
                if f.startswith(file_id):
                    return {"status":"success","file": os.path.join("downloads",f),"title": info.get('title','video')}
        raise Exception("File not found after download")
    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download")
async def download_file(file: str):
    if os.path.exists(file):
        return FileResponse(file, filename=os.path.basename(file))
    return JSONResponse(status_code=404, content={"error":"File not found"})
