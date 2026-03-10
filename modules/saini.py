import os
import re
import time
import mmap
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from math import ceil
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from requests.exceptions import RequestException
from modules.topic_handler import send_video_with_fallback, send_document_with_fallback

def duration(filename):
    if not Path(filename).exists():
        print(f"❌ File not found for duration: {filename}")
        return 0.0

    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", filename
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        output = result.stdout.decode().strip()
        return float(output)
    except Exception as e:
        print(f"❌ Failed to get duration for {filename}: {e}")
        return 0.0

def get_mps_and_keys(api_url):
    response = requests.get(api_url)
    response_json = response.json()
    mpd = response_json.get('MPD')
    keys = response_json.get('KEYS')
    return mpd, keys

def get_mps_and_keys2(api_url):
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # Raises exception for 4xx/5xx status codes
        response_json = response.json()
        mpd = response_json.get('mpd_url')
        keys = response_json.get('keys')
        return mpd, keys
    except RequestException as e:
        print(f"Request failed: {e}")
        return None, None
    except ValueError as e:
        print(f"JSON decode error: {e}")
        return None, None

def get_mps_and_keys3(api_url):
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # Raises exception for 4xx/5xx status codes
        response_json = response.json()
        mpd = response_json.get('url')
        return mpd
    except RequestException as e:
        print(f"Request failed: {e}")
        return None
    except ValueError as e:
        print(f"JSON decode error: {e}")
        return None
   
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka

async def pdf_download(url, file_name, chunk_size=1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name   
   

def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


import os
import subprocess
from pathlib import Path

async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        if not shutil.which("mp4decrypt"):
            print("❌ 'mp4decrypt' binary not found. This bot requires Bento4.")
            # raise FileNotFoundError("❌ 'mp4decrypt' binary not found.") 
            # Commented out raise to allow debugging if user wants to see what happens

        print(f"🔑 Decryption Keys: {keys_string}") # DEBUG PRINT

        # Step 1: Download with yt-dlp
        cmd1 = f'yt-dlp -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-formats --no-check-certificate --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 16 -k 1M -s 16" "{mpd_url}"'
        print(f"▶️ Downloading: {cmd1}")
        
        # Capture yt-dlp output
        dl_proc = subprocess.run(cmd1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if dl_proc.returncode != 0:
             print(f"❌ Download Failed: {dl_proc.stderr.decode()}")
             return None

        # Step 2: Detect downloaded files
        video_file = None
        audio_file = None
        for f in output_path.iterdir():
            if f.suffix in [".mp4", ".webm"] and not f.name.startswith("decrypted_") and not f.name == f"{output_name}.mp4":
                video_file = f
            elif f.suffix in [".m4a", ".webm"] and not f.name.startswith("decrypted_") and not f.name == f"{output_name}.mp4":
                audio_file = f

        if not video_file:
             print("❌ Decryption failed: video file not found after download.")
             return None
        
        print(f"📂 Found Video: {video_file} | Audio: {audio_file}")

        # Step 3: Decrypt
        decrypted_video = output_path / "decrypted_video.mp4"
        decrypted_audio = output_path / "decrypted_audio.m4a"

        # Check if keys are present
        if not keys_string or keys_string.strip() == "":
             print("⚠️ WARNING: keys_string is empty! mp4decrypt will likely fail to decrypt.")

        # Run mp4decrypt with capture
        cmd_v = f'mp4decrypt {keys_string} "{video_file}" "{decrypted_video}"'
        print(f"🔓 Decrypting Video: {cmd_v}")
        v_proc = subprocess.run(cmd_v, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"📝 mp4decrypt stdout: {v_proc.stdout.decode()}")
        print(f"📝 mp4decrypt stderr: {v_proc.stderr.decode()}")
        
        if v_proc.returncode != 0:
             print(f"❌ mp4decrypt (Video) Failed!")

        if audio_file:
            cmd_a = f'mp4decrypt {keys_string} "{audio_file}" "{decrypted_audio}"'
            print(f"🔓 Decrypting Audio: {cmd_a}")
            a_proc = subprocess.run(cmd_a, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # print(f"mp4decrypt audio stderr: {a_proc.stderr.decode()}")

        # Cleanup original encrypted files to save space
        if video_file: video_file.unlink(missing_ok=True)
        if audio_file: audio_file.unlink(missing_ok=True)

        # Step 4: Merge
        final_file = output_path / f"{output_name}.mp4"
        
        # Construct ffmpeg command
        if decrypted_audio and decrypted_audio.exists():
             cmd_merge = f'ffmpeg -y -i "{decrypted_video}" -i "{decrypted_audio}" -c copy "{final_file}"'
        else:
             cmd_merge = f'ffmpeg -y -i "{decrypted_video}" -c copy "{final_file}"'
             
        print(f"🔄 Merging: {cmd_merge}")
        m_proc = subprocess.run(cmd_merge, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if m_proc.returncode != 0:
             print(f"❌ FFmpeg Merge Failed: {m_proc.stderr.decode()}")
             # Don't return None yet, maybe video exists?
        
        # Cleanup decrypted intermediates
        if decrypted_video.exists(): decrypted_video.unlink(missing_ok=True)
        if decrypted_audio.exists(): decrypted_audio.unlink(missing_ok=True)

        if not final_file.exists():
            print("❌ Merged video file not found.")
            return None # raise FileNotFoundError("❌ Merged video file not found.")

        print(f"✅ Final video ready: {final_file}")
        return str(final_file)

    except Exception as e:
        print(f"🔥 Error in decrypt_and_merge_video: {e}")
        return None

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name

# appx zip ke liye 
# helper.py
import os
import requests
import zipfile
import subprocess
import tempfile
import shutil

FIXED_REFERER = "https://player.akamai.net.in/"

def process_zip_to_video(url, name):
    temp_dir = tempfile.mkdtemp(prefix="zip_")

    zip_path = os.path.join(temp_dir, "file.zip")
    extract_dir = os.path.join(temp_dir, "extract")
    output_path = os.path.join(temp_dir, f"{name}.mp4")

    headers = {
        "User-Agent": "Mozilla/5.0 (Android)",
        "Referer": FIXED_REFERER,
        "Range": "bytes=0-"
    }

    # 1️⃣ ZIP DOWNLOAD (FIXED REFERER)
    with requests.get(url, headers=headers, stream=True, timeout=20) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    # 2️⃣ EXTRACT ZIP
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    # 3️⃣ FIND m3u8
    m3u8_path = None
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.endswith(".m3u8"):
                m3u8_path = os.path.join(root, f)
                break

    if not m3u8_path:
        shutil.rmtree(temp_dir)
        raise Exception("❌ m3u8 file nahi mili")

    # 4️⃣ m3u8 → MP4 (same referer ffmpeg me bhi)
    cmd = [
        "ffmpeg",
        "-y",
        "-headers", f"Referer: {FIXED_REFERER}\r\n",
        "-allowed_extensions", "ALL",
        "-i", m3u8_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd)

    return output_path, temp_dir

import os, requests, zipfile, subprocess

import zipfile

def extract_zip(zip_path: str) -> str:
    extract_dir = zip_path.replace(".zip", "")
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    return extract_dir


import subprocess

def merge_ts_files(folder: str, output: str):
    ts_files = sorted(
        f for f in os.listdir(folder)
        if f.endswith((".ts", ".tse"))
    )

    list_file = os.path.join(folder, "list.txt")
    with open(list_file, "w") as f:
        for ts in ts_files:
            f.write(f"file '{os.path.join(folder, ts)}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output
    ], check=True)

    return output


def download_drago_mkv(url: str, filename: str, ext: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://akstechnicalclasses.classx.co.in/",
        "Origin": "https://akstechnicalclasses.classx.co.in",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{filename}.{ext}"

    session = create_session()
    downloaded = 0

    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)
        headers["Range"] = f"bytes={downloaded}-"

    try:
        with session.get(url, headers=headers, stream=True, timeout=(10, 180)) as r:
            if r.status_code not in (200, 206):
                print(f"❌ Bad status: {r.status_code}")
                return None

            total = int(r.headers.get("content-length", 0)) + downloaded
            chunk_size = 256 * 1024

            with open(file_path, "ab") as f, tqdm(
                total=total,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=filename,
                ncols=80
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        return file_path

    except Exception as e:
        print(f"⚠️ Download interrupted (resume enabled): {e}")
        return file_path if os.path.exists(file_path) else None

def download_drago_mkv(url: str, name: str) -> str | None:

    # 🔹 resolve redirect
    r = requests.get(url, allow_redirects=True, timeout=15)
    final_url = r.url

    # 🔹 ZIP case
    if final_url.endswith(".zip"):
        zip_path = download_raw_file(final_url, name, "zip")
        folder = extract_zip(zip_path)
        return merge_ts_files(folder, f"downloads/{name}.mp4")

    # 🔹 MKV (encrypted) case
    else:
        return download_raw_file(final_url, name, "mkv")
    
def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"

import os, re, asyncio, aiohttp
from urllib.parse import urljoin

async def fetch_segment(session, seg_url):
    try:
        async with session.get(seg_url, timeout=30) as resp:
            resp.raise_for_status()
            return await resp.read()
    except Exception as e:
        print(f"Error fetching segment {seg_url}: {e}")
        return None

async def download_m3u8_async(url: str, filename: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://player.akamai.net.in/",
        "Origin": "https://player.akamai.net.in",
        "Accept": "*/*"
    }
    os.makedirs("downloads", exist_ok=True)
    # Ensure filename ends with .mp4
    if not filename.endswith(".mp4"):
        final_file = f"downloads/{filename}.mp4"
    else:
        final_file = f"downloads/{filename}"

    print(f"🔗 Resolving URL: {url}")

    # Check if it is a direct video file (MP4/MKV/WEBM)
    if url.lower().endswith((".mp4", ".mkv", ".webm")):
        print(f"⚡ Direct video file link detected. Starting stream download...")
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=None) as resp:
                    resp.raise_for_status()
                    total_size = int(resp.headers.get('Content-Length', 0))
                    
                    with open(final_file, 'wb') as f:
                        downloaded = 0
                        async for chunk in resp.content.iter_chunked(1024 * 1024): # 1MB chunks
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # Optional: minimal logging to avoid flooding logs
                                if total_size > 0 and downloaded % (10 * 1024 * 1024) == 0: # Log every 10MB
                                   pass 
            
            print(f"✅ Full video downloaded: {final_file}")
            return final_file
        except Exception as e:
             print(f"🔥 Error in direct download: {e}")
             return None

    # If not a direct file, assume M3U8/Playlist
    print(f"📂 parsing potential M3U8 playlist...")
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            r = await session.get(url, timeout=30)
            text = await r.text()
            playlist_lines = text.splitlines()
            # Extract segment URLs, handling relative paths
            segments = [
                urljoin(url, line.strip()) 
                for line in playlist_lines 
                if line.strip() and not line.strip().startswith("#")
            ]

            if not segments:
                print("❌ No segments found in playlist!")
                return None

            total_segments = len(segments)
            print(f"🚀 Downloading {total_segments} segments for {filename} (Batch Mode)...")

            # Batch size to control memory usage
            BATCH_SIZE = 20 

            with open(final_file, "wb") as f:
                for i in range(0, total_segments, BATCH_SIZE):
                    batch = segments[i : i + BATCH_SIZE]
                    # Simple progress log
                    if i % 100 == 0:
                        print(f"⬇️ Processing segments {i} to {min(i + BATCH_SIZE, total_segments)}...")
                    
                    # Download batch concurrently
                    tasks = [fetch_segment(session, seg_url) for seg_url in batch]
                    results = await asyncio.gather(*tasks)

                    # Write to file in order (results matches order of tasks)
                    for data in results:
                        if data:
                            f.write(data)
                        else:
                            print("⚠️ Skipping failed segment, video may glitch.")

            print(f"\n✅ Full video downloaded: {final_file}")
            return final_file
            
        except Exception as e:
            print(f"🔥 Error in download_m3u8_async: {e}")
            return None

# Run
# asyncio.run(download_m3u8_async("your_m3u8_url", "video_name"))
import os
import asyncio
import subprocess
import logging

async def download_video(url, cmd, name, check_duration=True):
    if "transcoded" in url.lower():
        print(f"⚡ Transcoded URL detected → using download_m3u8_async for {name}")
        return await download_m3u8_async(url, name)
    
    # Use --concurrent-fragments for HLS (faster native parallel download)
    # and aria2c for non-HLS single-file downloads
    if any(ext in url for ext in [".m3u8", "master.m3u8", "playlist.m3u8"]):
        download_cmd = f'{cmd} -R 10 --fragment-retries 15 --concurrent-fragments 16 --no-check-certificates'
    else:
        download_cmd = f'{cmd} -R 10 --fragment-retries 15 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 16 -k 1M -s 16" --no-check-certificates'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)

    k = subprocess.run(download_cmd, shell=True)

    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name, check_duration)

    failed_counter = 0

    base = name.split(".")[0]
    possible_names = [
        name, 
        f"{name}.webm", 
        f"{base}.mkv", 
        f"{base}.mp4", 
        f"{base}.mp4.webm",
        os.path.splitext(name)[0] + ".mp4"
    ]

    final_file = None
    for f in possible_names:
        if os.path.isfile(f):
            final_file = f
            break

    if not final_file:
         raise Exception("Download failed: File not found")

    if os.path.getsize(final_file) == 0:
        os.remove(final_file)
        raise Exception("Download failed: File is 0 bytes")
    
    if check_duration:
        if duration(final_file) <= 0:
            os.remove(final_file)
            raise Exception("Download failed: Invalid video file check duration (moov atom not found)")

    return final_file
import os
import os
import time
import mmap
import asyncio
import requests
import subprocess

from tqdm import tqdm
from pyrogram import Client
from pyrogram.types import Message
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import os
from tqdm import tqdm
import os
import requests
from tqdm import tqdm  # progress bar
def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=10,
        pool_maxsize=10
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
import os
import mmap
import requests
from tqdm import tqdm
from base64 import b64decode

# ==============================
# FILE DECRYPT FUNCTION
# ==============================
def decrypt_file(file_path: str, key: str) -> bool:
    if not file_path or not os.path.exists(file_path):
        return False

    if not key:
        return True

    key_bytes = key.encode()
    size = min(28, os.path.getsize(file_path))

    with open(file_path, "r+b") as f:
        with mmap.mmap(f.fileno(), length=size, access=mmap.ACCESS_WRITE) as mm:
            for i in range(size):
                mm[i] ^= key_bytes[i] if i < len(key_bytes) else i

    return True
# ==============================
# RAW FILE DOWNLOAD
# ==============================
def download_raw_file(url: str, filename: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Referer": "https://akstechnicalclasses.classx.co.in/",
        "Origin": "https://akstechnicalclasses.classx.co.in",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{filename}.mkv"

    session = create_session()
    downloaded = 0

    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)
        headers["Range"] = f"bytes={downloaded}-"

    try:
        with session.get(url, headers=headers, stream=True, timeout=(10, 180)) as r:
            if r.status_code not in (200, 206):
                print(f"❌ Bad status: {r.status_code}")
                return None

            total = int(r.headers.get("content-length", 0)) + downloaded
            chunk_size = 256 * 1024

            with open(file_path, "ab") as f, tqdm(
                total=total,
                initial=downloaded,
                unit="B",
                unit_scale=True,
                desc=filename,
                ncols=80
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        return file_path

    except Exception as e:
        print(f"⚠️ Download interrupted (resume enabled): {e}")
        return file_path if os.path.exists(file_path) else None
# ==============================
# DOWNLOAD + DECRYPT WRAPPER
# ==============================

def download_and_decrypt_video(url: str, name: str, key: str = None) -> str | None:
    video_path = None

    for _ in range(5):  # resume attempts
        video_path = download_raw_file(url, name)
        if video_path and os.path.getsize(video_path) > 10 * 1024 * 1024:
            break

    if not video_path:
        return None

    if decrypt_file(video_path, key):
        return video_path

    return None

# ==============================
# EXAMPLE USAGE
# ==============================


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name, channel_id):
    reply = await bot.send_message(channel_id, f"Downloading pdf:\n<pre><code>{name}</code></pre>")
    time.sleep(1)
    start_time = time.time()
    await bot.send_document(ka, caption=cc1)
    count+=1
    await reply.delete (True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3) 



import asyncio

import asyncio

import asyncio

import os




    
import os
import time
import asyncio
import math

# 🔹 Async ffmpeg runner (NO BLOCKING)
async def run_cmd(cmd: str):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()


# ==========================
# FILE SPLITTING FUNCTION
# ==========================
async def split_file(filename, max_size=2 * 1024 * 1024 * 1024):  # 2 GB
    """
    Split a video file into parts smaller than max_size
    Returns list of split file paths
    """
    file_size = os.path.getsize(filename)
    
    if file_size <= max_size:
        return [filename]  # No splitting needed
    
    # Calculate number of parts needed
    num_parts = math.ceil(file_size / max_size)
    
    # Get video duration
    dur = duration(filename)
    if dur <= 0:
        dur = 3600  # Default to 1 hour if duration detection fails
    
    part_duration = int(dur / num_parts)
    
    split_files = []
    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1]
    
    for i in range(num_parts):
        start_time = i * part_duration
        output_file = f"{base_name}_part{i+1}{ext}"
        
        # Use FFmpeg to split without re-encoding (copy codec)
        if i == num_parts - 1:
            # Last part - no duration limit, just go to the end
            cmd = f'ffmpeg -y -i "{filename}" -ss {start_time} -c copy "{output_file}"'
        else:
            # Other parts - limit duration
            cmd = f'ffmpeg -y -i "{filename}" -ss {start_time} -t {part_duration} -c copy "{output_file}"'
        
        print(f"🔪 Splitting part {i+1}/{num_parts}: {output_file}")
        await run_cmd(cmd)
        
        if os.path.exists(output_file):
            split_files.append(output_file)
        else:
            print(f"⚠️ Failed to create part {i+1}")
    
    return split_files


async def send_vid(
    bot: Client,
    m: Message,
    cc,
    filename,
    vidwatermark,
    thumb,
    name,
    prog,
    channel_id,
    message_thread_id=None
):
    # ==========================
    # THUMBNAIL GENERATION
    # ==========================
    thumb_path = f"{filename}.jpg"
    await run_cmd(
        f'ffmpeg -y -i "{filename}" -ss 00:00:10 -vframes 1 "{thumb_path}"'
    )

    await prog.delete(True)

    reply1 = await bot.send_message(
        channel_id,
        f"**📩 Uploading Video 📩:-**\n<blockquote>**{name}**</blockquote>"
    )

    reply = await m.reply_text(
        f"**Generate Thumbnail:**\n<blockquote>**{name}**</blockquote>"
    )

    try:
        # ==========================
        # THUMB SELECTION
        # ==========================
        thumbnail = thumb_path if thumb == "/d" else thumb

        # ==========================
        # WATERMARK PROCESS
        # ==========================
        if vidwatermark == "/d":
            w_filename = filename
        else:
            w_filename = f"w_{os.path.basename(filename)}"
            font_path = "vidwater.ttf"
            
            # Update user about watermark process
            await reply.edit(f"**🎨 Applying Watermark...**\n<blockquote>**{name}**</blockquote>")
            
            try:
                # Check if font file exists
                if not os.path.exists(font_path):
                    print(f"⚠️ Font file not found: {font_path}, using default font")
                    watermark_cmd = (
                        f'ffmpeg -y -i "{filename}" -vf '
                        f'"drawtext=text=\'{vidwatermark}\':'
                        f'fontcolor=white@0.3:fontsize=h/6:'
                        f'x=(w-text_w)/2:y=(h-text_h)/2" '
                        f'-codec:a copy "{w_filename}"'
                    )
                else:
                    watermark_cmd = (
                        f'ffmpeg -y -i "{filename}" -vf '
                        f'"drawtext=fontfile={font_path}:text=\'{vidwatermark}\':'
                        f'fontcolor=white@0.3:fontsize=h/6:'
                        f'x=(w-text_w)/2:y=(h-text_h)/2" '
                        f'-codec:a copy "{w_filename}"'
                    )
                
                print(f"🎨 Applying watermark: {vidwatermark}")
                await run_cmd(watermark_cmd)
                
                # Check if watermarked file was created successfully
                if not os.path.exists(w_filename) or os.path.getsize(w_filename) == 0:
                    print(f"⚠️ Watermark failed, using original file")
                    w_filename = filename
                    await reply.edit(f"**⚠️ Watermark failed, uploading without watermark**\n<blockquote>**{name}**</blockquote>")
                else:
                    print(f"✅ Watermark applied successfully")
                    await reply.edit(f"**✅ Watermark Applied**\n<blockquote>**{name}**</blockquote>")
                    
            except Exception as e:
                print(f"❌ Watermark error: {e}")
                w_filename = filename
                await reply.edit(f"**⚠️ Watermark error, uploading without watermark**\n<blockquote>**{name}**</blockquote>")

        # ==========================
        # FILE SIZE CHECK & SPLITTING
        # ==========================
        file_size = os.path.getsize(w_filename)
        max_size = 2 * 1024 * 1024 * 1024  # 2 GB
        
        if file_size > max_size:
            # File is larger than 2 GB, split it
            await reply.edit(f"**File size: {file_size / (1024**3):.2f} GB**\n**Splitting into parts...**\n<blockquote>**{name}**</blockquote>")
            split_files = await split_file(w_filename, max_size)
            
            # Remove original large file after splitting
            if len(split_files) > 1 and w_filename != filename:
                try:
                    os.remove(w_filename)
                except:
                    pass
            
            # Upload each part
            for idx, part_file in enumerate(split_files, 1):
                dur = int(duration(part_file))
                start_time = time.time()
                
                part_caption = f"{cc}\n\n**Part {idx}/{len(split_files)}**"
                
                await reply.edit(f"**📩 Uploading Part {idx}/{len(split_files)} 📩**\n<blockquote>**{name}**</blockquote>")
                
                try:
                    if message_thread_id:
                        await send_video_with_fallback(bot,
                            chat_id=channel_id,
                            video=part_file,
                            caption=part_caption,
                            message_thread_id=message_thread_id,
                            supports_streaming=True,
                            height=720,
                            width=1280,
                            thumb=thumbnail,
                            duration=dur,
                            progress=progress_bar,
                            progress_args=(reply, start_time)
                        )
                    else:
                        await bot.send_video(
                            chat_id=channel_id,
                            video=part_file,
                            caption=part_caption,
                            supports_streaming=True,
                            height=720,
                            width=1280,
                            thumb=thumbnail,
                            duration=dur,
                            progress=progress_bar,
                            progress_args=(reply, start_time)
                        )
                except Exception:
                    if message_thread_id:
                        await send_document_with_fallback(bot,
                            chat_id=channel_id,
                            document=part_file,
                            caption=part_caption,
                            message_thread_id=message_thread_id,
                            progress=progress_bar,
                            progress_args=(reply, start_time)
                        )
                    else:
                        await bot.send_document(
                            chat_id=channel_id,
                            document=part_file,
                            caption=part_caption,
                            progress=progress_bar,
                            progress_args=(reply, start_time)
                        )
                
                # Clean up part file after upload
                try:
                    os.remove(part_file)
                except:
                    pass
        else:
            # File is smaller than 2 GB, upload normally
            dur = int(duration(w_filename))
            start_time = time.time()

            # ==========================
            # UPLOAD (VIDEO → DOC FALLBACK)
            # ==========================
            try:
                if message_thread_id:
                    await send_video_with_fallback(bot,
                        chat_id=channel_id,
                        video=w_filename,
                        caption=cc,
                        message_thread_id=message_thread_id,
                        supports_streaming=True,
                        height=720,
                        width=1280,
                        thumb=thumbnail,
                        duration=dur,
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
                else:
                    await bot.send_video(
                        chat_id=channel_id,
                        video=w_filename,
                        caption=cc,
                        supports_streaming=True,
                        height=720,
                        width=1280,
                        thumb=thumbnail,
                        duration=dur,
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
            except Exception:
                if message_thread_id:
                    await send_document_with_fallback(bot,
                        chat_id=channel_id,
                        document=w_filename,
                        caption=cc,
                        message_thread_id=message_thread_id,
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
                else:
                    await bot.send_document(
                        chat_id=channel_id,
                        document=w_filename,
                        caption=cc,
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
            
            # ==========================
            # CLEANUP
            # ==========================
            os.remove(w_filename)
    
    finally:
        try:
            await reply.delete(True)
        except:
            pass
        try:
            await reply1.delete(True)
        except:
            pass
        try:
            os.remove(f"{filename}.jpg")
        except:
            pass

import zipfile
import shutil

async def download_and_extract_pdf(url, name):
    try:
        print(f"🔄 Processing Classplus ZIP: {url}")
        temp_dir = f"temp_zip_{int(time.time())}_{name}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Determine paths
        zip_path = os.path.join(temp_dir, f"{name}.zip")
        
        # Download ZIP
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(zip_path, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                else:
                    return None

        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # Find PDF
        pdf_path = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_path = os.path.join(root, file)
                    break
            if pdf_path:
                break
        
        if pdf_path:
            # Move to a safe location (current dir) with correct name
            final_path = f"{name}.pdf"
            if os.path.exists(final_path):
               os.remove(final_path)
            shutil.move(pdf_path, final_path)
            shutil.rmtree(temp_dir)
            return final_path
        else:
            shutil.rmtree(temp_dir)
            return None
            
    except Exception as e:
        print(f"❌ Error in download_and_extract_pdf: {e}")
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        return None
