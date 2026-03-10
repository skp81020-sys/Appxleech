import os
import re
import sys
# Ensure root is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import m3u8
import json
import time
import pytz
import asyncio
import requests
import subprocess
import urllib
import urllib.parse
import yt_dlp
import tgcrypto
import cloudscraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64encode, b64decode

from modules.topic_handler import get_or_create_forum_topic, extract_autotopic_name, send_document_with_fallback, send_video_with_fallback, send_photo_with_fallback
from bs4 import BeautifulSoup
import saini as helper
import cw_helper
import html_handler
import globals
from db import db
from broadcast import broadcast_handler, broadusers_handler
from text_handler import text_to_txt
from youtube_handler import ytm_handler, y2t_handler, getcookies_handler, cookies_handler
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, CREDIT, CREDIT_LINK, cookies_file_path
from vars import api_url, api_token, token_cp, adda_token, photologo, photoyt, photocp, photozip
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
from aiohttp import web
import random
from pyromod import listen
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from pyrogram.errors import FloodWait, PeerIdInvalid, UserIsBlocked, InputUserDeactivated
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp
import aiofiles
import zipfile
import shutil
import ffmpeg
from urllib.parse import urlparse, parse_qs
import base64
from custom_cipher import B64Cipher, Secret
from cp_encn import decrypt_cp_encn_video
from appx_al import (
    decrypt_aes_link,
    is_node_link,
    resolve_isp_link,
    resolve_node_link,
    decrypt_xor,
    download_xor_pdf,
    download_encrypted_pdf,
    download_cloudflare_pdf,
    zip_to_video,
    classify_appx_link,
    get_ytdlp_appx_header_args,
    get_appx_headers,
    deobfuscate_ts,
    AppxLinkInfo,
)

# Classplus Headers for API calls
cp_headers = {
    "User-Agent": "Mobile-Android",
    "App-Version": "1.12.1.1",
    "Api-Version": "56",
    "Device-Id": "9d8ce7affa2f5032",
    "Device-Details": "motorola_Moto G4_SDK-32",
    "region": "IN",
    "accept-language": "en",
    "x-chrome-version": "143.0.7499.52",
    "Content-Type": "application/json",
    "Build-Number": "56",
    "isReviewerOn": "0",
    "is-apk": "0",
    "Connection": "Keep-Alive",
}

# AES Keys for aes:// handling
AES_KEY = "d62acaa3a9aaab68667cabdb850d4620"
AES_IV = "f12aa767375c0e58fa0b73c9bb9cb06f"


# ---------------------------------------------------------
# YOUTUBE FORMAT SELECTOR
# ---------------------------------------------------------
def youtube_format(raw_text2):
    return (
        f"bv*[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/"
        f"b[height<={raw_text2}]"
    )

# ---------------------------------------------------------
# YOUTUBE DOWNLOAD HANDLER (NO COOKIES)
# ---------------------------------------------------------
async def download_youtube(url, ytf, name):
    output_file = f"{name}.mp4"
    cmd = f'yt-dlp --concurrent-fragments 5 -f "{ytf}" "{url}" -o "{output_file}"'

    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            if os.path.exists(output_file):
                print(f"YouTube download complete: {output_file}")
                return output_file
            else:
                print("Download finished but file missing.")
                return None
        else:
            print("YouTube download failed:")
            print(stderr.decode(errors="ignore"))
            return None

    except Exception as e:
        print(f"Error during YouTube download: {e}")
        return None
async def drm_handler(bot: Client, m: Message):
    globals.processing_request = True
    globals.cancel_requested = False
    caption = globals.caption
    endfilename = globals.endfilename
    thumb = globals.thumb
    CR = globals.CR
    cwtoken = globals.cwtoken
    cptoken = globals.cptoken
    pwtoken = globals.pwtoken
    vidwatermark = globals.vidwatermark
    raw_text2 = globals.raw_text2
    quality = globals.quality
    res = globals.res
    topic = globals.topic

    # Retry wrapper function for downloads
    async def retry_download(download_func, count_val, name1_val, url_val):
        """
        Retry download up to 3 times with error message cleanup
        Returns: (success: bool, count_increment: int, failed_increment: int)
        """
        error_messages = []
        
        for attempt in range(1, 4):  # 3 attempts
            try:
                # Show retry message if not first attempt
                if attempt > 1:
                    retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count_val).zfill(3)} {name1_val}`')
                    error_messages.append(retry_msg)
                    await asyncio.sleep(2)
                
                # Execute the download function
                await download_func()
                
                # Success! Delete all error messages
                for msg in error_messages:
                    try:
                        await msg.delete(True)
                    except:
                        pass
                
                return (True, 1, 0)  # success, count+1, failed+0
                
            except Exception as e:
                error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count_val).zfill(3)} {name1_val}`\n**Url** =>> {url_val}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                error_messages.append(error_msg)
                
                if attempt == 3:  # Last attempt failed
                    # Delete old error messages, keep only the last one
                    for msg in error_messages[:-1]:
                        try:
                            await msg.delete(True)
                        except:
                            pass
                    return (False, 1, 1)  # failed, count+1, failed+1
                else:
                    await asyncio.sleep(3)  # Wait before retry
        
        return (False, 1, 1)  # Should never reach here

    user_id = m.from_user.id
    if m.document and m.document.file_name.endswith('.txt'):
        x = await m.download()
        await bot.send_document(OWNER, x)
        await m.delete(True)
        file_name, ext = os.path.splitext(os.path.basename(x))  # Extract filename & extension
        path = f"./downloads/{m.chat.id}"
        with open(x, "r") as f:
            content = f.read()
        lines = content.split("\n")
        os.remove(x)
    elif m.text and "://" in m.text:
        lines = [m.text]
    else:
        return

    if m.document:
        bot_username = (await bot.get_me()).username
        if not db.is_user_authorized(m.chat.id, bot_username):
            print(f"User ID not authorized", m.chat.id)
            await bot.send_message(m.chat.id, f"<blockquote>__**Oopss! You are not a Premium member\nPLEASE /upgrade YOUR PLAN\nSend me your user id for authorization\nYour User id**__ - `{m.chat.id}`</blockquote>\n")
            return

    autotopic_mode = False
    pdf_count = 0
    img_count = 0
    v2_count = 0
    mpd_count = 0
    m3u8_count = 0
    yt_count = 0
    drm_count = 0
    zip_count = 0
    other_count = 0
    
    links = []
    for i in lines:
        if "://" in i:
            url = i.split("://", 1)[1]
            links.append(i.split("://", 1))
            if ".pdf" in url:
                pdf_count += 1
            elif url.endswith((".png", ".jpeg", ".jpg")):
                img_count += 1
            elif "v2" in url:
                v2_count += 1
            elif "mpd" in url:
                mpd_count += 1
            elif "m3u8" in url:
                m3u8_count += 1
            elif "drm" in url:
                drm_count += 1
            elif "youtu" in url:
                yt_count += 1
            elif "zip" in url:
                zip_count += 1
            else:
                other_count += 1
                    
    if not links:
        await m.reply_text("<b>🔹Invalid Input.</b>")
        return

    if m.document:
        editable = await m.reply_text(f"** Total 🔗 Links Found are {len(links)}\n"
               f"<blockquote>\n"
               f"📁 PDF : {pdf_count}  🖼️ IMG : {img_count}  🛡️ V2 : {v2_count} \n"
               f"🧩 ZIP : {zip_count}  🔏 DRM : {drm_count}  🎧 M3U8 : {m3u8_count}\n"
               f"📦 MPD : {mpd_count}  📺 YT : {yt_count}\n"
               f"🌟 OTHER : {other_count}\n"
               f"</blockquote>\n"
               f"Send From Where You Want to download Initial Is <b>1</b>")
        try:
            input0: Message = await bot.listen(editable.chat.id, timeout=20)
            raw_text = input0.text
            await input0.delete(True)
        except asyncio.TimeoutError:
            raw_text = '1'
    
        if int(raw_text) > len(links) :
            await editable.edit(f"**🔹Enter number in range of Index (01-{len(links)})**")
            processing_request = False  # Reset the processing flag
            await m.reply_text("**🔹Exiting Task......  **")
            return

        await editable.edit(f"**Enter Batch Name or send /d**")
        try:
            input1: Message = await bot.listen(editable.chat.id, timeout=20)
            raw_text0 = input1.text
            await input1.delete(True)
        except asyncio.TimeoutError:
            raw_text0 = '/d'
      
        if raw_text0 == '/d':
            b_name = file_name.replace('_', ' ')
        else:
            b_name = raw_text0
        await editable.edit("**🔹Enter __PW/CP/CW__ Working Token For 𝐌𝐏𝐃 𝐔𝐑𝐋 or send /d**")
        try:
            input4: Message = await bot.listen(editable.chat.id, timeout=30)
            raw_text4 = input4.text
            await input4.delete(True)
        except asyncio.TimeoutError:
            raw_text4 = '/d'

        # --- AUTOTOPIC FEATURE ---
        await editable.edit("**Do you want to upload Topic Wise?\nSend /yes or /d**\n\n<blockquote><i>⚠️ Warning:- You must make the bot admin and give manage topics permission in the Group/Channel.</i></blockquote>")
        try:
            input_topic: Message = await bot.listen(editable.chat.id, timeout=30)
            raw_topic = input_topic.text
            await input_topic.delete(True)
        except asyncio.TimeoutError:
            raw_topic = '/d'
        
        autotopic_mode = True if "/yes" in raw_topic.lower() else False
        # -------------------------

        # --- TOPIC PINNING FEATURE ---
        await editable.edit("**Do you want to pin topics if yes send /y or /d**\n\n<blockquote><i>If enabled, the bot will send the topic name as text and pin it before uploading its files.</i></blockquote>")
        try:
            input_pin: Message = await bot.listen(editable.chat.id, timeout=30)
            raw_pin = input_pin.text
            await input_pin.delete(True)
        except asyncio.TimeoutError:
            raw_pin = '/d'
        
        pin_topic_mode = True if "/y" in raw_pin.lower() else False
        # -----------------------------

        await editable.edit("__**⚠️Provide the Channel ID or send /d__\n\n<blockquote><i>🔹 Make me an admin to upload.\n🔸Send /id in your channel to get the Channel ID.\n\nExample: Channel ID = -100XXXXXXXXXXX</i></blockquote>\n**")
        try:
            input7: Message = await bot.listen(editable.chat.id, timeout=20)
            raw_text7 = input7.text
            await input7.delete(True)
        except asyncio.TimeoutError:
            raw_text7 = '/d'

        if "/d" in raw_text7:
            channel_id = m.chat.id
        else:
            channel_id = raw_text7    
        await editable.delete()

    elif m.text:
        raw_text4 = '/d'
        path = f"./downloads/{m.chat.id}"
        if any(ext in links[i][1] for ext in [".pdf", ".jpeg", ".jpg", ".png"] for i in range(len(links))):
            raw_text = '1'
            raw_text7 = '/d'
            channel_id = m.chat.id
            b_name = '**Link Input**'
            await m.delete()
        else:
            editable = await m.reply_text(f"╭━━━━❰ᴇɴᴛᴇʀ ʀᴇꜱᴏʟᴜᴛɪᴏɴ❱━━➣ \n┣━━⪼ send `144`  for 144p\n┣━━⪼ send `240`  for 240p\n┣━━⪼ send `360`  for 360p\n┣━━⪼ send `480`  for 480p\n┣━━⪼ send `720`  for 720p\n┣━━⪼ send `1080` for 1080p\n╰━━⌈⚡[🦋`{CREDIT}`🦋]⚡⌋━━➣ ")
            input2: Message = await bot.listen(chat_id=editable.chat.id, filters=filters.text & filters.user(m.from_user.id))
            raw_text2 = input2.text
            quality = f"{raw_text2}p"
            await m.delete()
            await input2.delete(True)
            try:
                if raw_text2 == "144":
                    res = "256x144"
                elif raw_text2 == "240":
                    res = "426x240"
                elif raw_text2 == "360":
                    res = "640x360"
                elif raw_text2 == "480":
                    res = "854x480"
                elif raw_text2 == "720":
                    res = "1280x720"
                elif raw_text2 == "1080":
                    res = "1920x1080"
                else:
                    res = "UN"
            except Exception:
                    res = "UN"
            raw_text = '1'
            raw_text7 = '/d'
            channel_id = m.chat.id
            b_name = '**Link Input**'
            await editable.delete()
        
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = thumb

    try:
        if m.document and raw_text == "1":
            batch_message = await bot.send_message(chat_id=channel_id, text=f"<blockquote><b>🎯Target Batch : {b_name}</b></blockquote>")
            if "/d" not in raw_text7:
                await bot.send_message(chat_id=m.chat.id, text=f"<blockquote><b><i>🎯Target Batch : {b_name}</i></b></blockquote>\n\n🔄 Your Task is under processing, please check your Set Channel📱. Once your task is complete, I will inform you 📩")
                await bot.pin_chat_message(channel_id, batch_message.id)
                message_id = batch_message.id
                pinning_message_id = message_id + 1
                await bot.delete_messages(channel_id, pinning_message_id)
        else:
             if "/d" not in raw_text7:
                await bot.send_message(chat_id=m.chat.id, text=f"<blockquote><b><i>🎯Target Batch : {b_name}</i></b></blockquote>\n\n🔄 Your Task is under processing, please check your Set Channel📱. Once your task is complete, I will inform you 📩")
    except Exception as e:
        await m.reply_text(f"**Fail Reason »**\n<blockquote><i>{e}</i></blockquote>\n\n✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}🌟`")

        
    failed_count = 0
    count =int(raw_text)    
    arg = int(raw_text)
    try:
        last_pinned_topic = None
        last_msg_time = 0
        for i in range(arg-1, len(links)):
            ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"
            keys_string = ""
            mpd = None
            if globals.cancel_requested:
                await m.reply_text("🚦**STOPPED**🚦")
                globals.processing_request = False
                globals.cancel_requested = False
                return
  
            # -- CLASSPLUS / AES / ENCRYPTION LOGIC --
            cp_encn_video = False
            cp_already_signed = False # Flag to skip Golden Eagle / old CP handlers after contentHashId signing
            skip_url_cleanup = False # Flag to skip destructive URL cleanup
            protocol = links[i][0]
            link0 = links[i][1]  # The content after ://
            url = link0 # Initialize url with raw link content
            
            print(f"🔄 Processing Link: {protocol}://{link0}")

            if "rickcoder007" in protocol.lower() or "aes" in protocol.lower() or "rick_johnson" in protocol.lower():
                try:
                    encrypted_data = link0 # content is already stripped of :// by detection logic? 
                    # WAIT: 'link0' comes from 'links[i][1]' which is the content AFTER '://'
                    # So if the link is 'rickcoder007://XYZ', then 'protocol' is 'rickcoder007' and 'link0' is 'XYZ'.
                    # So NO stripping is needed here if logic at line 214 does the splitting correctly.
                    
                    # BUT line 214 says: url = i.split("://", 1)[1] ... links.append(i.split("://", 1))
                    # So links[i][0] is protocol, links[i][1] is payload.
                    # Correct.
                    
                    encrypted_data = link0 
                    secret = Secret(bytes.fromhex(AES_KEY), bytes.fromhex(AES_IV))
                    cipher = B64Cipher(secret)
                    decrypted_link = cipher.decrypt(encrypted_data)
                    link0 = decrypted_link
                    url = decrypted_link
                    skip_url_cleanup = True # Skip cleanup for decrypted links
                    print(f"🔓 Decrypted AES Link: {url}")

                    # Check if decrypted link is a node:// frozen directory
                    if is_node_link(url):
                        url = "node://" + url
                        link0 = url
                        print(f"🔗 Detected node:// directory in AES link")

                except Exception as e:
                    await m.reply_text(f"❌ Failed to decrypt AES link: {e}")
                    failed_count += 1
                    continue

            # -- NODE:// FROZEN DIRECTORY RESOLUTION (from appx_al) --
            if url.startswith("node://"):
                try:
                    node_jstr = url.replace("node://", "")
                    node_resolution = int(raw_text2) if raw_text2 and raw_text2.isdigit() else 480
                    url = await resolve_node_link(node_jstr, resolution=node_resolution)
                    link0 = url
                    skip_url_cleanup = True
                    print(f"🔗 Node resolved: {url[:100]}...")
                except Exception as e:
                    await m.reply_text(f"❌ Failed to resolve node:// link: {e}")
                    failed_count += 1
                    count += 1
                    continue

            # -- ISP:// INSECURE PLAYER RESOLUTION (from appx_al) --
            if url.startswith("isp://"):
                try:
                    isp_payload = url.replace("isp://", "")
                    url = resolve_isp_link(isp_payload)
                    link0 = url
                    skip_url_cleanup = True
                    print(f"🔗 ISP resolved: {url}")
                except Exception as e:
                    await m.reply_text(f"❌ Failed to resolve isp:// link: {e}")
                    failed_count += 1
                    count += 1
                    continue

            # -- APPX LINK CLASSIFICATION (from appx_al) --
            # Classify and extract metadata for appx-specific link patterns
            appx_info = classify_appx_link(url)
            is_appx_xor_video = (appx_info.link_type == "xor_video")
            is_appx_xor_pdf = (appx_info.link_type == "xor_pdf")
            is_appx_enc_pdf = (appx_info.link_type == "enc_pdf")
            is_appx_zip_video = (appx_info.link_type == "zip_video")
            is_appx_hls_live = (appx_info.link_type == "hls_live")
            is_appx_cloudflare_pdf = (appx_info.link_type == "cloudflare_pdf")

            # Update URL if appx_al extracted a clean URL
            if appx_info.url and appx_info.url != url:
                url = appx_info.url
                link0 = url

            # Add Appx referer headers for appx/classx/securevideo links
            appx_referer_needed = appx_info.needs_referer
            
            # Check for Classplus Encrypted Dummy URL (contentHashId or legacy url with previewToken)
            if "stream.m3u8?contentHashId=" in url or ("stream.m3u8?url=" in url and "previewToken=" in url):
                try:
                    query_params = parse_qs(urlparse(url).query)
                    content_hash_id = query_params.get("contentHashId", [None])[0]
                    preview_token = query_params.get("previewToken", [None])[0]
                    legacy_url = query_params.get("url", [None])[0]
                    param_name = query_params.get("param_name", ["contentId"])[0]
                    org_code = query_params.get("orgCode", [None])[0]

                    skip_url_cleanup = True # Skip cleanup for signed links

                    # === Legacy URL + previewToken: sign via Golden Eagle with org-specific token ===
                    if legacy_url and preview_token:
                        if "_encn/master.m3u8" in legacy_url:
                            cp_encn_video = True
                            print("🔒 Classplus Encrypted Video Detected (.encn)")
                        
                        # Build Golden Eagle API call with orgCode for org-specific token
                        ge_params = f"url={requests.utils.quote(legacy_url, safe='')}"
                        if org_code:
                            ge_params += f"&orgCode={requests.utils.quote(org_code, safe='')}"
                        if raw_text4 and raw_text4 != '/d':
                            ge_params += f"&token={requests.utils.quote(raw_text4, safe='')}"
                        ge_api_url = f"https://cp-api-liart.vercel.app/Golden_Eagle?{ge_params}"
                        
                        ge_success = False
                        for ge_attempt in range(1, 4):
                            try:
                                print(f"🔄 Golden Eagle (legacy+org) attempt {ge_attempt}/3... org={org_code or 'none'}")
                                ge_resp = requests.get(ge_api_url, timeout=30)
                                ge_data = ge_resp.json()
                                
                                if isinstance(ge_data, dict) and ge_data.get("success") and ge_data.get("url"):
                                    url = ge_data["url"]
                                    cp_already_signed = True
                                    ge_success = True
                                    print(f"✅ Legacy Signed URL: {url[:80]}...")
                                    break
                                elif isinstance(ge_data, dict) and "KEYS" in ge_data and "MPD" in ge_data:
                                    url = ge_data.get("MPD", "")
                                    cp_already_signed = True
                                    ge_success = True
                                    keys_string = " ".join([f"--key {k}" for k in ge_data.get("KEYS", [])])
                                    print(f"✅ Legacy DRM Content - Got {len(ge_data.get('KEYS', []))} keys")
                                    break
                                elif isinstance(ge_data, dict) and ge_data.get("url"):
                                    url = ge_data["url"]
                                    cp_already_signed = True
                                    ge_success = True
                                    print(f"✅ Legacy Signed URL: {url[:80]}...")
                                    break
                                else:
                                    print(f"⚠️ GE attempt {ge_attempt}/3: {str(ge_data)[:200]}")
                                    if ge_attempt < 3:
                                        await asyncio.sleep(15)
                            except Exception as ge_err:
                                print(f"❌ GE attempt {ge_attempt}/3: {ge_err}")
                                if ge_attempt < 3:
                                    await asyncio.sleep(15)
                        
                        if not ge_success:
                            raise Exception("Golden Eagle failed to sign legacy URL after 3 attempts")

                    # === v2 / fallback: need API signing ===
                    else:
                        if content_hash_id and preview_token:
                            sign_params = {"contentId": content_hash_id}
                            sign_headers = cp_headers.copy()
                            sign_headers["x-access-token"] = preview_token
                            print(f"🔑 v2 Signing: contentId={content_hash_id[:30]}... previewToken={preview_token[:30]}...")
                        elif content_hash_id:
                            sign_params = {
                                param_name: content_hash_id,
                                "offlineDownload": "false"
                            }
                            sign_headers = cp_headers.copy()
                            sign_headers["x-access-token"] = raw_text4
                            print(f"🔑 Legacy Signing: {param_name}={content_hash_id[:30]}...")
                        else:
                            raise Exception("No contentHashId or legacy URL found in stream URL")

                        sign_resp = requests.get(
                            "https://api.classplusapp.com/cams/uploader/video/jw-signed-url",
                            params=sign_params,
                            headers=sign_headers,
                            timeout=30
                        )
                        sign_resp.raise_for_status()
                        sign_data = sign_resp.json()

                        signed_url = sign_data.get("url") or (sign_data.get("data", {}) or {}).get("url")
                        drm_urls = sign_data.get("drmUrls") or (sign_data.get("data", {}) or {}).get("drmUrls")

                        if signed_url:
                            url = signed_url
                            cp_already_signed = True
                            print(f"✅ Signed URL: {url[:80]}...")
                        elif drm_urls:
                            url = drm_urls.get("manifestUrl", "")
                            cp_already_signed = True
                            print(f"✅ DRM Signed URL: {url[:80]}...")
                        else:
                            raise Exception(f"No URL in response: {str(sign_data)[:200]}")

                except Exception as e:
                    print(f"❌ Failed to sign Classplus link: {e}")
                    await m.reply_text(f"❌ Failed to sign Classplus link: {e}")
                    failed_count += 1
                    continue
            
            # Check if resolved URL is 'encn' type (needs post-process decryption)
            if "_encn/master.m3u8" in url:
                cp_encn_video = True
                print("🔒 Classplus Encrypted Video Detected (.encn)")

            if not skip_url_cleanup:
                Vxy = url.replace("https://", "").replace("http://", "").replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed/", "youtu.be/").replace("www.youtube.com/embed/", "youtu.be/").replace("youtube.com/embed/", "youtu.be/").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
                if not url.startswith("http"):
                     url = "https://" + Vxy
            link0 = url

            # CW Helper Integration
            if "#keysV1=" in url:
                url_clean, keys_str = cw_helper.get_download_info(url)
                if keys_str:
                     url = url_clean
                     mpd = url_clean
                     keys_string = keys_str
            
            # --- FAKE LINK CHECK ---
            if url == "https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/media-cdn.classplusapp.com/master.m3u8":
                await m.reply_text(f"<b>{str(count).zfill(3)}.</b> ⚠️ **Fake Link Error :>** {url}")
                count += 1
                failed_count += 1
                continue

            name1 = links[i][0].replace("(", "[").replace(")", "]").replace("_", "").replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").replace("rickcoder007", "").replace("Rick_Johnson", "").strip()
            # FIX: If name1 matches the protocol (like 'https') or is empty after stripping, assign a default
            if not name1 or name1.lower() in ["https", "http", ""]:
                name1 = f"Untitled_{int(time.time())}_{str(count).zfill(3)}"
            
            # Encapsulate filename truncation
            # Linux filename limit is 255 bytes. Hindi chars can be 3 bytes.
            # 60 chars * 3 bytes = 180 bytes, leaving room for extensions.
            if len(name1) > 60:
                name1 = name1[:60]

            name = name1
            # GLOBAL FIX — now namef is always defined
            namef = name1
            appxkey = None
            
            # --- AUTOTOPIC LOGIC ---
            upload_thread_id = None
            if autotopic_mode:
                try:
                    # Extract topic from filename
                    topic_name = extract_autotopic_name(name1)
                    if topic_name:
                        # Get or create topic thread ID
                        bot_username = (await bot.get_me()).username
                        upload_thread_id = await get_or_create_forum_topic(db, bot_username, channel_id, topic_name)
                        if upload_thread_id:
                            print(f"✅ Autotopic: Uploading to topic '{topic_name}' (Thread ID: {upload_thread_id})")
                        else:
                            print(f"⚠️ Autotopic: Failed to get thread ID for '{topic_name}', uploading to General.")
                except Exception as e_topic:
                     print(f"❌ Autotopic Error: {e_topic}")
            # -----------------------

            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            if "acecwply" in url:
                cmd = f'yt-dlp --concurrent-fragments 5 -o "{name}.%(ext)s" -f "bestvideo[height<={raw_text2}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'
         
            elif "https://cpmc/" in url:
               url = url.replace("https://cpmc/", "")  # Extract contentId
               url = url.replace(".m3u8", "")
               r = requests.get("https://api-seven-omega-33.vercel.app/extract", params={
               "content_id": url,
               "token": raw_text4
               })
               data = r.json()
               signed = r.json().get("signed_url")
               # Output variables
               url = None
               mpd= None
               keys_string = ""
               if signed and isinstance(signed, str) and "drm" in signed.lower():
    # DRM case: extract directly from response
                 mpd = data.get("mpd")
                 keys = data.get("keys", [])
                 if not mpd:
                   raise ValueError("❌ MPD URL missing in DRM response.")
                 if not keys:
                    raise ValueError("❌ Decryption keys missing in DRM response.")
                 url = mpd
                 keys_string = " ".join([f"--key {key}" for key in keys])
               else:
                   url = signed
                                        # --- Unified Classplus/Testbook handler using ITSGOLU API (with 3x retry) ---
            if any(x in url for x in ["https://cpvod.testbook.com/", "classplusapp.com/drm/", "media-cdn.classplusapp.com", "media-cdn-alisg.classplusapp.com", "media-cdn-a.classplusapp.com", "tencdn.classplusapp", "videos.classplusapp", "webvideos.classplusapp.com"]) and not cp_already_signed:
                # normalize cpvod -> media-cdn path used by API
                url_norm = url.replace("https://cpvod.testbook.com/", "https://media-cdn.classplusapp.com/drm/")
                # Pass user's CP token to API if available
                if raw_text4 and raw_text4 != '/d':
                    api_url_call = f"https://cp-api-liart.vercel.app/Golden_Eagle?url={url}&token={raw_text4}"
                else:
                    api_url_call = f"https://cp-api-liart.vercel.app/Golden_Eagle?url={url}"
                keys_string = ""
                mpd = None
                api_success = False

                for retry_attempt in range(1, 4):  # Retry up to 3 times
                    try:
                        print(f"🔄 Golden Eagle API attempt {retry_attempt}/3...")
                        resp = requests.get(api_url_call, timeout=30)
                        data = resp.json()

                        # DRM response (MPD + KEYS)
                        if isinstance(data, dict) and "KEYS" in data and "MPD" in data:
                            mpd = data.get("MPD")
                            keys = data.get("KEYS", [])
                            url = mpd
                            keys_string = " ".join([f"--key {k}" for k in keys])
                            print(f"✅ DRM Content - Got {len(keys)} keys (attempt {retry_attempt})")
                            api_success = True
                            break

                        # Non-DRM response (direct url)
                        elif isinstance(data, dict) and "url" in data:
                            url = data.get("url")
                            keys_string = ""
                            print(f"✅ Non-DRM Content - Got direct URL (attempt {retry_attempt})")
                            api_success = True
                            break

                        else:
                            # Unexpected response format — count as failure, retry
                            print(f"⚠️ Attempt {retry_attempt}/3: Golden Eagle returned unexpected response: {data}")
                            if retry_attempt < 3:
                                await asyncio.sleep(15)

                    except Exception as e_api:
                        print(f"❌ Attempt {retry_attempt}/3: Golden Eagle API error: {e_api}")
                        if retry_attempt < 3:
                            await asyncio.sleep(15)

                # If all 3 retries failed, skip this link
                if not api_success:
                    # Determine if it's a video or pdf for the skip message
                    link_type = "Pdf" if ".pdf" in link0.lower() else "Video"
                    await m.reply_text(f"<b>{str(count).zfill(3)}.</b> ❌ {link_type} id {str(count).zfill(3)} skipped due to API failure (3 retries failed)")
                    count += 1
                    failed_count += 1
                    continue

            elif ('classplusapp' in url or "testbook.com" in url or "classplusapp.com/drm" in url or "media-cdn.classplusapp.com/drm" in url) and not cp_already_signed:
                headers = {
                    'host': 'api.classplusapp.com',
                    'x-access-token': f'{raw_text4}',    
                    'accept-language': 'en',
                    'api-version': '56',
                    'app-version': '1.12.1.1',
                    'build-number': '56',
                    'connection': 'Keep-Alive',
                    'content-type': 'application/json',
                    'device-details': 'motorola_Moto G4_SDK-32',
                    'device-id': 'c28d3cb16bbdac01',
                    'region': 'IN',
                    'user-agent': 'Mobile-Android',
                    'x-chrome-version': '143.0.7499.52',
                    'isReviewerOn': '0',
                    'is-apk': '0',
                    'accept-encoding': 'gzip'
                }
                
                url = url.replace('https://tencdn.classplusapp.com/', 'https://media-cdn.classplusapp.com/tencent/')

                params = {
                    "url": f"{url}"
                }

                try:
                    res = requests.get("https://api.classplusapp.com/cams/uploader/video/jw-signed-url", params=params, headers=headers).json()
                    if "url" in res:
                        url = res["url"]
                        print(f"✅ Classplus Signed URL: {url}")
                    else:
                        print(f"⚠️ Classplus Signing Failed: {res}")
                except Exception as e:
                    print(f"❌ Classplus Signing Error: {e}")
                
                
            if "edge.api.brightcove.com" in url:
                bcov = f'bcov_auth={cwtoken}'
                url = url.split("bcov_auth")[0]+bcov

            #elif "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
            elif "dragoapi.vercel.app" in url and "*" in url :
    # Split into base URL and key
             parts = url.split("*", 1)
             if len(parts) == 2:
              base_url = parts[0].strip()
              appxkey = parts[1].strip()   # e.g. 8822682
              response = requests.get(base_url, timeout=10, allow_redirects=True)
              final_url = response.url.strip()  # resolved CDN link

        # Step 2: Overwrite url with the resolved link
              url = final_url
              print(f"⚡ DragoAPI link detected → base_url={base_url}, appxkey={appxkey}")
            elif "dragoapi.vercel.app" in url and ".mkv" in url:
              r = requests.get(url, timeout=10, allow_redirects=True)

    # Step 2: Final resolved URL
              final_url = r.url

    # Step 3: Store directly in url for downloading
              url = final_url.strip()
            
            elif "childId" in url and "parentId" in url:
                url = f"https://anonymouspwplayerrr-3dba7e3fb6a8.herokuapp.com/pw?url={url}&token={raw_text4}"
                           
            elif 'encrypted.m' in url and '*' in url and not is_appx_xor_video:
                 appxkey = url.split('*')[1]
                 url = url.split('*')[0]
            

            
            
            elif ".m3u8" in url and "appx" in url:
             r = requests.get(url, timeout=10)
             data_json = r.json()

             enc_url = data_json.get("video_url")

             if "*" in enc_url:
        # URL = * se pehle wala
               before, after = enc_url.split("*", 1)

    # URL = * se pehle wala
               url = before.strip()

    # APPX KEY = * ke baad wala decoded (final digit)
               appxkey = base64.b64decode(after.strip()).decode().strip()

             else:
        # Direct URL case
              url = enc_url.strip()
              appxkey = data_json.get("encryption_key")


  
                
            elif "dragoapi.vercel.app" in url or url.endswith(".m3u8"):
    # Step 1: Hit the URL (it auto-redirects to real HLS)
             r = requests.get(url, timeout=10, allow_redirects=True)

    # Step 2: Final resolved URL
             final_url = r.url

    # Step 3: Store directly in url for downloading
             url = final_url.strip()

    # Step 4: No referer needed for this pattern
             

            # ==========================
            # YOUTUBE LINK DETECTION
            # ==========================
            if "youtube.com" in url or "youtu.be" in url:
                try:
                    # Extract video ID from all YouTube URL patterns
                    video_id = None
                    
                    if "youtu.be/" in url:
                        video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0].split("/")[0]
                    elif "/embed/" in url:
                        video_id = url.split("/embed/")[1].split("?")[0].split("&")[0].split("/")[0]
                    elif "/live/" in url:
                        video_id = url.split("/live/")[1].split("?")[0].split("&")[0].split("/")[0]
                    elif "/shorts/" in url:
                        video_id = url.split("/shorts/")[1].split("?")[0].split("&")[0].split("/")[0]
                    elif "v=" in url:
                        video_id = url.split("v=")[1].split("&")[0].split("/")[0]
                    
                    # Clean video ID (remove any remaining slashes or invalid chars)
                    if video_id:
                        video_id = video_id.strip().strip("/")
                    
                    if video_id and len(video_id) > 5:
                        # Try multiple thumbnail qualities (maxresdefault might not exist for all videos)
                        thumbnail_urls = [
                            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                            f"https://img.youtube.com/vi/{video_id}/0.jpg"
                        ]
                        
                        # Generate caption in same format as downloaded videos
                        if m.text:
                            yt_caption = f'{name1} [{res}p] .mkv'
                        else:
                            if topic == "/yes":
                                raw_title = links[i][0]
                                clean_yt = raw_title.strip()
                                if clean_yt.startswith("(") or clean_yt.startswith("["):
                                    t_match = re.search(r"[\(\[]([^\)\]]+)[\)\]]", raw_title)
                                    if t_match:
                                        t_name = t_match.group(1).strip()
                                        v_name = re.sub(r"^[\(\[][^\)\]]+[\)\]]\s*", "", raw_title)
                                        v_name = re.sub(r"[\(\[][^\)\]]+[\)\]]", "", v_name)
                                        v_name = re.sub(r"^[\s:]+", "", v_name).strip()
                                        # Strip trailing URL remnant (links split on "://" leaves ":https" at end)
                                        for marker in [":https", ":http", "https", "http"]:
                                            if v_name.rstrip().endswith(marker):
                                                v_name = v_name.rstrip()[:-(len(marker))].strip()
                                                break
                                    else:
                                        t_name = "Untitled"
                                        v_name = name1
                                else:
                                    t_name = "Untitled"
                                    v_name = name1
                            
                                if caption == "/cc1":
                                    credit_link = f'<a href="{globals.CR_LINK}">{CR}</a>'
                                    yt_caption = f"""╭━━━━━━━━━━━╮
🎥 VIDEO ID: {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""
                                elif caption == "/cc2":
                                    yt_caption = f"——— ✦ {str(count).zfill(3)} ✦ ———\n\n<blockquote><b>⋅ ─  {t_name}  ─ ⋅</b></blockquote>\n\n<b>🎞️ Title :</b> {v_name}\n<b>├── Extention :  {CR} .mkv</b>\n<b>├── Resolution : [{res}]</b>\n<blockquote><b>📚 Course : {b_name}</b></blockquote>\n\n**🌟 Extracted By : {CR}**"
                                else:
                                    yt_caption = f'<blockquote><b>⋅ ─ {t_name} ─ ⋅</b></blockquote>\n<b>{str(count).zfill(3)}.</b> {v_name} [{res}p] .mkv'
                            else:
                                t_name = "Untitled"
                                v_name = name1
                                if caption == "/cc1":
                                    credit_link = f'<a href="{globals.CR_LINK}">{CR}</a>'
                                    yt_caption = f"""╭━━━━━━━━━━━╮
🎥 VIDEO ID: {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""
                                elif caption == "/cc2":
                                    yt_caption = f"——— ✦ {str(count).zfill(3)} ✦ ———\n\n<b>🎞️ Title :</b> {name1}\n<b>├── Extention :  {CR} .mkv</b>\n<b>├── Resolution : [{res}]</b>\n<blockquote><b>📚 Course : {b_name}</b></blockquote>\n\n**🌟 Extracted By : {CR}**"
                                else:
                                    yt_caption = f'<b>{str(count).zfill(3)}.</b> {name1} [{res}p] .mkv'
                        
                        # Create inline button
                        from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("▶️ Play Video", url=url)]
                        ])
                        
                        # Try sending with different thumbnail qualities
                        thumbnail_sent = False
                        for thumb_url in thumbnail_urls:
                            try:
                                if upload_thread_id:
                                    await send_photo_with_fallback(bot,
                                        chat_id=channel_id,
                                        photo=thumb_url,
                                        caption=yt_caption,
                                        message_thread_id=upload_thread_id,
                                        reply_markup=keyboard
                                    )
                                else:
                                    await bot.send_photo(
                                        chat_id=channel_id,
                                        photo=thumb_url,
                                        caption=yt_caption,
                                        reply_markup=keyboard
                                    )
                                thumbnail_sent = True
                                break
                            except Exception as thumb_error:
                                print(f"Thumbnail quality failed: {thumb_url}, trying next...")
                                continue
                        
                        if thumbnail_sent:
                            count += 1
                            continue
                        else:
                            print(f"All thumbnail qualities failed for video: {video_id}")
                    
                except Exception as e:
                    print(f"YouTube thumbnail generation failed: {e}")
                    pass

            if "youtu" in url:
             ytf = youtube_format(raw_text2)
             video_path = await download_youtube(url, ytf, name)
           
            if "jw-prod" in url:
                cmd = f'yt-dlp --concurrent-fragments 5 -o "{name}.mp4" "{url}"'
            elif "webvideos.classplusapp." in url:
               cmd = f'yt-dlp --concurrent-fragments 5 --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" -f "{ytf}" "{url}" -o "{name}.mp4"'
            elif "youtube.com" in url or "youtu.be" in url:
                cmd = f'yt-dlp --concurrent-fragments 5 --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}".mp4'
            else:
                cmd = f'yt-dlp --concurrent-fragments 5 -f "{ytf}" "{url}" -o "{name}.mp4"'

            # Inject Appx referer headers into cmd if classified as appx link
            if appx_referer_needed and "--add-header" not in cmd:
                appx_hdr_args = get_ytdlp_appx_header_args()
                cmd = cmd.replace("yt-dlp ", f"yt-dlp {appx_hdr_args} ", 1)

            try:
                if m.text:
                    cc = f'{name1} [{res}p] .mkv'
                    cc1 = f'{name1} .pdf'
                    cczip = f'{name1} .zip'
                    ccimg = f'{name1} .jpg'
                    ccm = f'{name1} .mp3'
                    cchtml = f'{name1} .html'
                else:
                        if topic == "/yes":
                                raw_title = links[i][0]
                                t_name = "Untitled"
                                v_name = name1

                                clean_title = raw_title.strip()

                                # Helper: strip URL from v_name 
                                # links are split on "://" so links[i][0] ends with ":https" or ":http" (without "://")
                                def strip_url(text):
                                    for marker in [":https", ":http", "https", "http"]:
                                        if text.rstrip().endswith(marker):
                                            text = text.rstrip()[:-(len(marker))]
                                            break
                                    return text.strip()

                                # Rule: Only extract topic if filename starts with ( or [
                                if clean_title.startswith("(") or clean_title.startswith("["):
                                    # Check for ">>" separator first
                                    if ">>" in raw_title:
                                        parts = raw_title.split(">>", 1)
                                        pre_part = parts[0].strip()
                                        
                                        # Find first bracket group in pre_part
                                        p_stack = []
                                        p_start = -1
                                        p_end = -1
                                        for idx, char in enumerate(pre_part):
                                            if char in "([":
                                                if not p_stack: p_start = idx
                                                p_stack.append(char)
                                            elif char in ")]":
                                                if p_stack:
                                                    last_open = p_stack[-1]
                                                    if (last_open == "(" and char == ")") or (last_open == "[" and char == "]"):
                                                        p_stack.pop()
                                                        if not p_stack:
                                                            p_end = idx
                                                            break
                                        
                                        if p_start == 0 and p_end != -1:
                                            t_name = pre_part[p_end+1:].strip()
                                            if not t_name:
                                                t_name = pre_part[1:p_end].strip()
                                        else:
                                            t_name = pre_part
                                        
                                        v_name = strip_url(parts[1].strip())

                                    else:
                                        # No ">>" — extract bracket groups
                                        groups = []
                                        curr_stack = []
                                        curr_start = -1
                                        
                                        for idx, char in enumerate(raw_title):
                                            if char in "([":
                                                if not curr_stack: curr_start = idx
                                                curr_stack.append(char)
                                            elif char in ")]":
                                                if curr_stack:
                                                    last_open = curr_stack[-1]
                                                    if (last_open == "(" and char == ")") or (last_open == "[" and char == "]"):
                                                        curr_stack.pop()
                                                        if not curr_stack:
                                                            groups.append((curr_start, idx, raw_title[curr_start+1:idx]))
                                                            curr_start = -1
                                        
                                        if len(groups) >= 2:
                                            # 2nd bracket group is topic name
                                            g1_end = groups[0][1]
                                            g2_start = groups[1][0]
                                            between_text = raw_title[g1_end+1:g2_start].strip()
                                            
                                            if not between_text:
                                                t_name = groups[1][2]
                                                v_name = raw_title[groups[1][1]+1:].strip()
                                                v_name = re.sub(r"^[\s:]+", "", v_name).strip()
                                            else:
                                                t_name = groups[0][2]
                                                v_name = raw_title[groups[0][1]+1:].strip()
                                                v_name = re.sub(r"^[\s:]+", "", v_name).strip()
                                        elif len(groups) == 1:
                                            t_name = groups[0][2]
                                            v_name = raw_title[groups[0][1]+1:].strip()
                                            v_name = re.sub(r"^[\s:]+", "", v_name).strip()
                                        
                                        # Strip URL from v_name
                                        v_name = strip_url(v_name)
                                        
                                        if not v_name:
                                            v_name = name1

                                else:
                                    # Filename doesn't start with bracket → topic = Untitled, full name = title
                                    t_name = "Untitled"
                                    v_name = name1

                        else:
                            t_name = "Untitled"
                            v_name = name1

                        # --- TOPIC PINNING IMPLEMENTATION ---
                        if pin_topic_mode and t_name and t_name != "Untitled":
                            if last_pinned_topic != t_name:
                                try:
                                    if upload_thread_id:
                                        pin_msg = await bot.send_message(channel_id, f"**{t_name}**", reply_to_message_id=upload_thread_id)
                                    else:
                                        pin_msg = await bot.send_message(channel_id, f"**{t_name}**")
                                    await pin_msg.pin(disable_notification=True)
                                    # Attempt to delete the system "pinned a message" notification
                                    try:
                                        sys_msg = await bot.get_messages(channel_id, pin_msg.id + 1)
                                        if sys_msg and sys_msg.service and sys_msg.pinned_message:
                                            await sys_msg.delete()
                                    except:
                                        pass
                                    last_pinned_topic = t_name
                                except Exception as e:
                                    print(f"Failed to pin topic {t_name}: {e}")
                        # ------------------------------------

                        # Unified New Caption Style
                        # Enforce HTML link for CREDIT with configurable URL (uses per-user settings from globals)
                        credit_link = f'<a href="{globals.CR_LINK}">{CR}</a>'
                        
                        cc = f"""╭━━━━━━━━━━━╮
🎥 VIDEO ID: {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""

                        cc1 = f"""╭━━━━━━━━━━━╮
📕 Pdf Id : {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""

                        cczip = f"""╭━━━━━━━━━━━╮
📁 Zip Id : {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""

                        ccimg = f"""╭━━━━━━━━━━━╮
📷 PHOTO ID: {str(count).zfill(3)}
╰━━━━━━━━━━━╯
📄 Title:  {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""

                        ccm = f"""╭━━━━━━━━━━━╮
🎵 Mp3 Id : {str(count).zfill(3)}
╰━━━━━━━━━━━╯

📄 Title: {v_name}

🪄 Topic Name : {t_name}

🔖 Batch: {b_name}

📥 Downloaded by: {credit_link}"""

                        cchtml = cczip # Fallback for html

                if "drive" in url:
                    ka = await helper.download(url, name)
                    if upload_thread_id:
                        copy = await send_document_with_fallback(bot, chat_id=channel_id, document=ka, caption=cc1, message_thread_id=upload_thread_id)
                    else:
                        copy = await bot.send_document(chat_id=channel_id, document=ka, caption=cc1)
                    count+=1
                    os.remove(ka)

                # ══════════════════════════════════════════════════════════
                # APPX_AL: XOR Encrypted PDF
                # ══════════════════════════════════════════════════════════
                elif is_appx_xor_pdf:
                    try:
                        namef = name1
                        pdf_file = f"{namef}.pdf"
                        prog = await bot.send_message(channel_id, f"<i><b>📄 Downloading Appx Encrypted PDF...</b></i>\n<blockquote><b>{str(count).zfill(3)}) {namef}</b></blockquote>", disable_web_page_preview=True)
                        await download_xor_pdf(pdf_file, url, appx_info.pdf_enc_key)
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        if upload_thread_id:
                            copy = await send_document_with_fallback(bot, chat_id=channel_id, document=pdf_file, caption=cc1, message_thread_id=upload_thread_id)
                        else:
                            copy = await bot.send_document(chat_id=channel_id, document=pdf_file, caption=cc1)
                        count += 1
                        os.remove(pdf_file)
                    except Exception as e:
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        await bot.send_message(channel_id, f'⚠️**PDF Download Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                        count += 1
                        failed_count += 1
                        continue

                # ══════════════════════════════════════════════════════════
                # APPX_AL: API-Encrypted PDF (curl + XOR, same as xor_pdf)
                # ══════════════════════════════════════════════════════════
                elif is_appx_enc_pdf:
                    try:
                        namef = name1
                        pdf_file = f"{namef}.pdf"
                        prog = await bot.send_message(channel_id, f"<i><b>📄 Downloading Appx Encrypted PDF...</b></i>\n<blockquote><b>{str(count).zfill(3)}) {namef}</b></blockquote>", disable_web_page_preview=True)
                        await download_xor_pdf(pdf_file, url, appx_info.pdf_enc_key)
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        if upload_thread_id:
                            copy = await send_document_with_fallback(bot, chat_id=channel_id, document=pdf_file, caption=cc1, message_thread_id=upload_thread_id)
                        else:
                            copy = await bot.send_document(chat_id=channel_id, document=pdf_file, caption=cc1)
                        count += 1
                        os.remove(pdf_file)
                    except Exception as e:
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        await bot.send_message(channel_id, f'⚠️**PDF Download Failed (Enc)**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                        count += 1
                        failed_count += 1
                        continue

                # ══════════════════════════════════════════════════════════
                # APPX_AL: Cloudflare Protected PDF
                # ══════════════════════════════════════════════════════════
                elif is_appx_cloudflare_pdf:
                    try:
                        namef = name1
                        pdf_file = f"{namef}.pdf"
                        prog = await bot.send_message(channel_id, f"<i><b>📄 Downloading Cloudflare PDF...</b></i>\n<blockquote><b>{str(count).zfill(3)}) {namef}</b></blockquote>", disable_web_page_preview=True)
                        await download_cloudflare_pdf(url, pdf_file)
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        if upload_thread_id:
                            copy = await send_document_with_fallback(bot, chat_id=channel_id, document=pdf_file, caption=cc1, message_thread_id=upload_thread_id)
                        else:
                            copy = await bot.send_document(chat_id=channel_id, document=pdf_file, caption=cc1)
                        count += 1
                        os.remove(pdf_file)
                    except Exception as e:
                        if prog:
                            try: await prog.delete(True)
                            except: pass
                        await bot.send_message(channel_id, f'⚠️**PDF Download Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                        count += 1
                        failed_count += 1
                        continue

                # ══════════════════════════════════════════════════════════
                # APPX_AL: XOR Encrypted Video (download + XOR decrypt)
                # ══════════════════════════════════════════════════════════
                elif is_appx_xor_video:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False

                    for attempt in range(1, 4):
                        try:
                            if attempt > 1:
                                for _msg in [current_error_msg, retry_msg, prog, prog1]:
                                    if _msg:
                                        try: await _msg.delete(True)
                                        except: pass
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show = f"<i><b>🔐 XOR Encrypted Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"

                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()

                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)

                            # Download with Appx headers
                            appx_hdr_args = get_ytdlp_appx_header_args()
                            cmd = f'yt-dlp --concurrent-fragments 5 {appx_hdr_args} -o "{name}.mkv" "{url}" -R 25 --fragment-retries 25'
                            os.system(cmd)

                            # XOR decrypt the downloaded file
                            vid_file = f"{name}.mkv"
                            if os.path.exists(vid_file) and appx_info.xor_key:
                                decrypt_xor(vid_file, appx_info.xor_key)
                                print(f"✅ XOR decrypted: {vid_file}")

                            filename = vid_file
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)

                            if retry_msg:
                                try: await retry_msg.delete(True)
                                except: pass
                            success = True
                            count += 1
                            await asyncio.sleep(1)
                            break

                        except Exception as e:
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            if attempt == 3:
                                if retry_msg:
                                    try: await retry_msg.delete(True)
                                    except: pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)

                    if success:
                        continue

                # ══════════════════════════════════════════════════════════
                # APPX_AL: ZIP-to-Video (UHS 1-5 offline content)
                # ══════════════════════════════════════════════════════════
                elif is_appx_zip_video:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False

                    for attempt in range(1, 4):
                        try:
                            if attempt > 1:
                                for _msg in [current_error_msg, retry_msg, prog, prog1]:
                                    if _msg:
                                        try: await _msg.delete(True)
                                        except: pass
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            Show = f"<i><b>📦 ZIP→Video Processing (UHS {appx_info.uhs_version})</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"

                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()

                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)

                            # Run ZIP-to-video pipeline
                            out_dir = f"appx_zip_{count}"
                            os.makedirs(out_dir, exist_ok=True)
                            filename = zip_to_video(
                                zip_url=url,
                                out_dir=out_dir,
                                uhs_version=appx_info.uhs_version,
                            )

                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)

                            # Cleanup temp directory
                            import shutil
                            shutil.rmtree(out_dir, ignore_errors=True)

                            if retry_msg:
                                try: await retry_msg.delete(True)
                                except: pass
                            success = True
                            count += 1
                            await asyncio.sleep(1)
                            break

                        except Exception as e:
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            # Cleanup temp directory on failure too
                            try:
                                import shutil
                                shutil.rmtree(f"appx_zip_{count}", ignore_errors=True)
                            except: pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**ZIP Processing Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            if attempt == 3:
                                if retry_msg:
                                    try: await retry_msg.delete(True)
                                    except: pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)

                    if success:
                        continue

                # ══════════════════════════════════════════════════════════
                # APPX_AL: HLS Live Stream
                # ══════════════════════════════════════════════════════════
                elif is_appx_hls_live:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    success = False

                    for attempt in range(1, 4):
                        try:
                            if attempt > 1:
                                for _msg in [current_error_msg, retry_msg, prog]:
                                    if _msg:
                                        try: await _msg.delete(True)
                                        except: pass
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            Show = f"<i><b>📡 HLS Live Stream Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"

                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()

                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)

                            # Download HLS live with yt-dlp (treat as non-live to get full recording)
                            appx_hdr_args = get_ytdlp_appx_header_args()
                            hls_key_arg = ""
                            if appx_info.hls_key:
                                hls_key_arg = f' --hls-key "{appx_info.hls_key}"'
                            cmd = f'yt-dlp --concurrent-fragments 5 {appx_hdr_args} --extractor-args "generic:is_live=false" --no-keep-fragments{hls_key_arg} -o "{name}.mkv" "{url}" -R 25 --fragment-retries 25'
                            os.system(cmd)

                            filename = f"{name}.mkv"
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)

                            if retry_msg:
                                try: await retry_msg.delete(True)
                                except: pass
                            success = True
                            count += 1
                            await asyncio.sleep(1)
                            break

                        except Exception as e:
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**HLS Download Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            if attempt == 3:
                                if retry_msg:
                                    try: await retry_msg.delete(True)
                                    except: pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)

                    if success:
                        continue

                elif ".pdf" in url:
                    final_url = url
                    need_referer = False
                    namef = name1
                    if "appxsignurl.vercel.app/appx/" in url:
                        try:
                            # Step 1: Directly use the original URL
                            response = requests.get(url.strip(), timeout=10)
                            data = response.json()

                            # Step 2: Extract actual PDF URL
                            pdf_url = data.get("pdf_url")
                            if pdf_url:
                                url = pdf_url.strip()   # overwrite with real downloadable link
                            else:
                                print("No pdf_url found in response JSON.")
                                # fallback: keep original URL
                                # url remains unchanged

                            # Step 3: Extract title if available
                            namef = data.get("title", name1)

                            # Step 4: Mark referer requirement
                            need_referer = True
                        except Exception as e:
                            print(f"Error fetching AppxSignURL JSON: {e}")
                            need_referer = True
                            namef = name1
                    

                    elif "static-db.appx.co.in" in url:
                           
                           need_referer = True
                           namef = name1
                    elif "static-db-v2.appx.co.in" in url:
                           
                           need_referer = True
                           namef = name1

                    elif "static-db-v2.appx.co.in" in url:
                        filename = urlparse(url).path.split("/")[-1]
                        url = f"https://appx-content-v2.classx.co.in/paid_course4/{filename}"
                        need_referer = True
                        namef = name1
                    else:
                        if topic == "/yes":
                            namef = f'{v_name}'
                        else:
                            try:
                                response = requests.get(url)
                                if response.status_code == 200:
                                    try:
                                        data = response.json()
                                        namef = data.get("title", name1).replace("nn", "")
                                    except:
                                        namef = name1
                                else:
                                    namef = name1
                            except:
                                namef = name1
                        need_referer = True
                    if "cwmediabkt99" in url:
                        namef = name1
                        max_retries = 15  # Define the maximum number of retries
                        retry_delay = 4  # Delay between retries in seconds
                        success = False  # To track whether the download was successful
                        failure_msgs = []  # To keep track of failure messages
                        
                        for attempt in range(max_retries):
                            try:
                                await asyncio.sleep(retry_delay)
                                url = url.replace(" ", "%20")
                                scraper = cloudscraper.create_scraper()
                                response = scraper.get(url)

                                if response.status_code == 200:
                                    with open(f'{namef}.pdf', 'wb') as file:
                                        file.write(response.content)
                                    await asyncio.sleep(retry_delay)  # Optional, to prevent spamming
                                    if upload_thread_id:
                                        copy = await send_document_with_fallback(bot, chat_id=channel_id, document=f'{namef}.pdf', caption=cc1, message_thread_id=upload_thread_id)
                                    else:
                                        copy = await bot.send_document(chat_id=channel_id, document=f'{namef}.pdf', caption=cc1)
                                    count += 1
                                    os.remove(f'{namef}.pdf')
                                    success = True
                                    break  # Exit the retry loop if successful
                                else:
                                    failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {response.status_code} {response.reason}")
                                    failure_msgs.append(failure_msg)
                                    
                            except Exception as e:
                                failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                                failure_msgs.append(failure_msg)
                                await asyncio.sleep(retry_delay)
                                continue 
                    else:
                        namef = name1
                        try:
                            # -----------------------------------------
                            if need_referer:
                                referer = "https://player.akamai.net.in/"
                                ua = "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 4a Build/QD4A.200805.003)"
                                cmd = f'yt-dlp --add-header "Referer: {referer}" --add-header "User-Agent: {ua}" -o "{namef}.pdf" "{url}"'
                            else:
                                cmd = f'yt-dlp -o "{namef}.pdf" "{url}"'

                            download_cmd = f"{cmd} -R 25 --fragment-retries 25"

                            # -----------------------------------------
                            # DOWNLOAD PDF
                            # -----------------------------------------
                            os.system(download_cmd)

                            # -----------------------------------------
                            # SEND PDF
                            # -----------------------------------------
                            copy = await send_document_with_fallback(bot,
                                chat_id=channel_id,
                                document=f"{namef}.pdf",
                                caption=cc1,
                                message_thread_id=upload_thread_id
                            )

                            count += 1
                            os.remove(f"{namef}.pdf")

                        except FloodWait as e:
                            await m.reply_text(str(e))
                            time.sleep(e.x)
                            continue

                elif ".ws" in url and  url.endswith(".ws"):
                    try:
                        await helper.pdf_download(f"{api_url}utkash-ws?url={url}&authorization={api_token}",f"{name}.html")
                        time.sleep(1)
                        await send_document_with_fallback(bot, chat_id=channel_id, document=f"{name}.html", caption=cchtml, message_thread_id=upload_thread_id)
                        os.remove(f'{name}.html')
                        count += 1
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue    
                            
                elif "cdn-wl-assets.classplus.co" in url and url.endswith(".zip"):
                    try:
                        namef = name1
                        # Use helper to download ZIP and extract PDF
                        pdf_path = await helper.download_and_extract_pdf(url, namef)
                        
                        if pdf_path:
                            # Send the extracted PDF
                            await send_document_with_fallback(bot,
                                chat_id=channel_id,
                                document=pdf_path,
                                caption=cc1,
                                message_thread_id=upload_thread_id
                            )
                            count += 1
                            os.remove(pdf_path)
                        else:
                            await m.reply_text(f"❌ Failed to extract PDF from ZIP: {url}")
                            failed_count += 1
                            
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue
                    except Exception as e:
                        await m.reply_text(f"❌ Error processing ZIP: {str(e)}")
                        failed_count += 1
                        continue

                elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                    try:
                        namef = name1
                        ext = url.split('.')[-1]
                        cmd = f'yt-dlp -o "{namef}.{ext}" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await send_photo_with_fallback(bot, chat_id=channel_id, photo=f'{namef}.{ext}', caption=ccimg, message_thread_id=upload_thread_id)
                        count += 1
                        os.remove(f'{namef}.{ext}')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue    

                elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
                    try:
                        namef = name1
                        ext = url.split('.')[-1]
                        cmd = f'yt-dlp -o "{namef}.{ext}" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await send_document_with_fallback(bot, chat_id=channel_id, document=f'{namef}.{ext}', caption=ccm, message_thread_id=upload_thread_id)
                        count += 1
                        os.remove(f'{namef}.{ext}')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue    
                elif "dragoapi.vercel.app" in url:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False
                    
                    for attempt in range(1, 4):  # 3 attempts
                        try:
                            # Cleanup before retrying (if not first attempt)
                            if attempt > 1:
                                if current_error_msg:
                                    try:
                                        await current_error_msg.delete(True)
                                    except:
                                        pass
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                if prog:
                                    try:
                                        await prog.delete(True)
                                    except:
                                        pass
                                if prog1:
                                    try:
                                        await prog1.delete(True)
                                    except:
                                        pass
                                
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n┃\n" \
                                   f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {count}/{len(links)}\n┃\n" \
                                   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧 » {remaining_links}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote><b>⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Eɴᴄʀʏᴘᴛᴇᴅ Sᴛᴀʀᴛᴇᴅ...⏳</b></blockquote>\n┃\n" \
                                   f'┣💃𝐂𝐫𝐞𝐝𝐢𝐭 » {CR}\n┃\n' \
                                   f"╰━📚𝐁𝐚𝐭𝐜𝐡 » {b_name}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote>📚𝐓𝐢𝐭𝐥𝐞 » {namef}</blockquote>\n┃\n" \
                                   f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {quality}\n┃\n" \
                                   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">**Original Link**</a>\n┃\n' \
                                   f'╰━━🖇️𝐔𝐫𝐥 » <a href="{url}">**Api Link**</a>\n' \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"🛑**Send** /stop **to stop process**\n┃\n" \
                                   f"╰━✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>" 
                            
                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()
                            
                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                            prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                            res_file = await helper.download_asia_video(url,  name)  
                            filename = res_file  
                            if prog1:
                                try: await prog1.delete(True)
                                except: pass
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)
                            
                            # Success! Cleanup messages
                            if retry_msg:
                                try:
                                    await retry_msg.delete(True)
                                except:
                                    pass
                            
                            success = True
                            count += 1  
                            await asyncio.sleep(1)  
                            break  # Exit retry loop on success
                            
                        except Exception as e:
                            if prog:
                                try:
                                    await prog.delete(True)
                                except:
                                    pass
                            if prog1:
                                try:
                                    await prog1.delete(True)
                                except:
                                    pass

                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            
                            if attempt == 3:  # Last attempt failed
                                # Clean up retry msg, keep only success/fail
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)  # Wait before retry
                    
                    if success:
                        continue  
                elif "dragoapi.vercel.app" in url and ".mkv" in url:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False
                    
                    for attempt in range(1, 4):  # 3 attempts
                        try:
                            # Cleanup before retrying (if not first attempt)
                            if attempt > 1:
                                if current_error_msg:
                                    try:
                                        await current_error_msg.delete(True)
                                    except:
                                        pass
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                if prog:
                                    try:
                                        await prog.delete(True)
                                    except:
                                        pass
                                if prog1:
                                    try:
                                        await prog1.delete(True)
                                    except:
                                        pass
                                
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n┃\n" \
                                   f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {count}/{len(links)}\n┃\n" \
                                   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧 » {remaining_links}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote><b>⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Eɴᴄʀʏᴘᴛᴇᴅ Sᴛᴀʀᴛᴇᴅ...⏳</b></blockquote>\n┃\n" \
                                   f'┣💃𝐂𝐫𝐞𝐝𝐢𝐭 » {CR}\n┃\n' \
                                   f"╰━📚𝐁𝐚𝐭𝐜𝐡 » {b_name}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote>📚𝐓𝐢𝐭𝐥𝐞 » {namef}</blockquote>\n┃\n" \
                                   f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {quality}\n┃\n" \
                                   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">**Original Link**</a>\n┃\n' \
                                   f'╰━━🖇️𝐔𝐫𝐥 » <a href="{url}">**Api Link**</a>\n' \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"🛑**Send** /stop **to stop process**\n┃\n" \
                                   f"╰━✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>" 
                            
                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()
                            
                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                            prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                            res_file = await helper.process_zip_to_video(url,  name)  
                            filename = res_file  
                            if prog1:
                                try: await prog1.delete(True)
                                except: pass
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)
                            
                            # Success! Cleanup messages
                            if retry_msg:
                                try:
                                    await retry_msg.delete(True)
                                except:
                                    pass
                            
                            success = True
                            count += 1  
                            await asyncio.sleep(1)  
                            break  # Exit retry loop on success
                            
                        except Exception as e:
                            if prog:
                                try:
                                    await prog.delete(True)
                                except:
                                    pass
                            if prog1:
                                try:
                                    await prog1.delete(True)
                                except:
                                    pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            
                            if attempt == 3:  # Last attempt failed
                                # Clean up retry msg, keep only success/fail
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)  # Wait before retry
                    
                    if success:
                        continue   
                elif (".m3u8" in url and "appx" in url) \
                    or "encrypted.m" in url \
                    or "appxsignurl.vercel.app/appx/" in url \
                    or ("dragoapi.vercel.app" in url and "*" in url):
    # handle appx/encrypted/appxsignurl/dragoapi with *key
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False
                    
                    for attempt in range(1, 4):  # 3 attempts
                        try:
                            # Cleanup before retrying (if not first attempt)
                            if attempt > 1:
                                if current_error_msg:
                                    try:
                                        await current_error_msg.delete(True)
                                    except:
                                        pass
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                if prog:
                                    try:
                                        await prog.delete(True)
                                    except:
                                        pass
                                if prog1:
                                    try:
                                        await prog1.delete(True)
                                    except:
                                        pass
                                
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n┃\n" \
                                   f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {count}/{len(links)}\n┃\n" \
                                   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧 » {remaining_links}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote><b>⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Eɴᴄʀʏᴘᴛᴇᴅ Sᴛᴀʀᴛᴇᴅ...⏳</b></blockquote>\n┃\n" \
                                   f'┣💃𝐂𝐫𝐞𝐝𝐢𝐭 » {CR}\n┃\n' \
                                   f"╰━📚𝐁𝐚𝐭𝐜𝐡 » {b_name}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote>📚𝐓𝐢𝐭𝐥𝐞 » {namef}</blockquote>\n┃\n" \
                                   f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {quality}\n┃\n" \
                                   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">**Original Link**</a>\n┃\n' \
                                   f'╰━━🖇️𝐔𝐫𝐥 » <a href="{url}">**Api Link**</a>\n' \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"🛑**Send** /stop **to stop process**\n┃\n" \
                                   f"╰━✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>" 
                            
                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()
                            
                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                            prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                            if ".m3u8" in url:
                                print(f"⚡ Detected Appx M3U8, switching to batch downloader for {namef}")
                                res_file = await helper.download_m3u8_async(url, namef)
                            else:
                                res_file = helper.download_and_decrypt_video(url, namef, appxkey)  
                            filename = res_file  
                            if prog1:
                                try: await prog1.delete(True)
                                except: pass
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)
                            
                            # Success! Cleanup messages
                            if retry_msg:
                                try:
                                    await retry_msg.delete(True)
                                except:
                                    pass
                            
                            success = True
                            count += 1  
                            await asyncio.sleep(1)  
                            break  # Exit retry loop on success
                            
                        except Exception as e:
                            if prog:
                                try:
                                    await prog.delete(True)
                                except:
                                    pass
                            if prog1:
                                try:
                                    await prog1.delete(True)
                                except:
                                    pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            
                            if attempt == 3:  # Last attempt failed
                                # Clean up retry msg, keep only success/fail
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)  # Wait before retry
                    
                    if success:
                        continue  

                elif ('drmcdni' in url or 'drm/wv' in url or 'drm/common' in url) or (mpd is not None and keys_string):
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False
                    
                    for attempt in range(1, 4):  # 3 attempts
                        try:
                            # Cleanup before retrying (if not first attempt)
                            if attempt > 1:
                                if current_error_msg:
                                    try:
                                        await current_error_msg.delete(True)
                                    except:
                                        pass
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                if prog:
                                    try:
                                        await prog.delete(True)
                                    except:
                                        pass
                                if prog1:
                                    try:
                                        await prog1.delete(True)
                                    except:
                                        pass
                                
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n┃\n" \
                                   f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {count}/{len(links)}\n┃\n" \
                                   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧 » {remaining_links}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote><b>⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Sᴛᴀʀᴛᴇᴅ...⏳</b></blockquote>\n┃\n" \
                                   f'┣💃𝐂𝐫𝐞𝐝𝐢𝐭 » {CR}\n┃\n' \
                                   f"╰━📚𝐁𝐚𝐭𝐜𝐡 » {b_name}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote>📚𝐓𝐢𝐭𝐥𝐞 » {namef}</blockquote>\n┃\n" \
                                   f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {quality}\n┃\n" \
                                   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">**Original Link**</a>\n┃\n' \
                                   f'╰━━🖇️𝐔𝐫𝐥 » <a href="{url}">**Api Link**</a>\n' \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"🛑**Send** /stop **to stop process**\n┃\n" \
                                   f"╰━✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                            prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                            res_file = await helper.decrypt_and_merge_video(mpd, keys_string, path, name, raw_text2)
                            filename = res_file
                            await prog1.delete(True)
                            await prog.delete(True)
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)
                            
                            # Success! Cleanup messages
                            if retry_msg:
                                try:
                                    await retry_msg.delete(True)
                                except:
                                    pass
                            
                            success = True
                            count += 1
                            await asyncio.sleep(1)
                            break  # Exit retry loop on success
                            
                        except Exception as e:
                            if prog:
                                try:
                                    await prog.delete(True)
                                except:
                                    pass
                            if prog1:
                                try:
                                    await prog1.delete(True)
                                except:
                                    pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            
                            if attempt == 3:  # Last attempt failed
                                # Clean up retry msg, keep only success/fail
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)  # Wait before retry
                    
                    if success:
                        continue
     
                else:
                    current_error_msg = None
                    retry_msg = None
                    prog = None
                    prog1 = None
                    success = False
                    
                    for attempt in range(1, 4):  # 3 attempts
                        try:
                            # Cleanup before retrying (if not first attempt)
                            if attempt > 1:
                                if current_error_msg:
                                    try:
                                        await current_error_msg.delete(True)
                                    except:
                                        pass
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                if prog:
                                    try:
                                        await prog.delete(True)
                                    except:
                                        pass
                                if prog1:
                                    try:
                                        await prog1.delete(True)
                                    except:
                                        pass
                                
                                retry_msg = await bot.send_message(channel_id, f'🔄 **Retrying {attempt}/3**\n**Name** =>> `{str(count).zfill(3)} {name1}`')
                                await asyncio.sleep(2)

                            remaining_links = len(links) - count
                            progress = (count / len(links)) * 100
                            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n┃\n" \
                                   f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {count}/{len(links)}\n┃\n" \
                                   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧 » {remaining_links}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote><b>⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Sᴛᴀʀᴛᴇᴅ...⏳</b></blockquote>\n┃\n" \
                                   f'┣💃𝐂𝐫𝐞𝐝𝐢𝐭 » {CR}\n┃\n' \
                                   f"╰━📚𝐁𝐚𝐭𝐜𝐡 » {b_name}\n" \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"<blockquote>📚𝐓𝐢𝐭𝐥𝐞 » {namef}</blockquote>\n┃\n" \
                                   f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {quality}\n┃\n" \
                                   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">**Original Link**</a>\n┃\n' \
                                   f'╰━━🖇️𝐔𝐫𝐥 » <a href="{url}">**Api Link**</a>\n' \
                                   f"━━━━━━━━━━━━━━━━━━━━━━━━━\n" \
                                   f"🛑**Send** /stop **to stop process**\n┃\n" \
                                   f"╰━✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
                            
                            time_since_last_msg = time.time() - last_msg_time
                            if time_since_last_msg < 10:
                                await asyncio.sleep(10 - time_since_last_msg)
                            last_msg_time = time.time()
                            
                            prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                            prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                            
                            # CW / DRM Integration Check
                            if (keys_string and mpd) or (mpd and ".m3u8" in str(mpd)):
                                print(f"🔐 Executing CW/NRE Download for: {name1}")
                                res_file = await cw_helper.download_video_with_nre(mpd, keys_string if keys_string else "", name)
                                if res_file:
                                    print(f"✅ Download Successful: {res_file}")
                                else:
                                    print(f"❌ Download Failed via NRE")
                                    # Fallback to old method if needed, or raise error
                                    raise Exception("NRE Download Failed")
                            else:
                                res_file = await helper.download_video(url, cmd, name, check_duration=not cp_encn_video)
                            
                            # -- CLASSPLUS ENCRYPTED VIDEO DECRYPTION --
                            if cp_encn_video and res_file and os.path.exists(res_file):
                                try:
                                    status_msg = await bot.send_message(channel_id, f"🔐 **Decrypting Classplus Video...**\n`{name1}`")
                                    # Decrypt in-place
                                    print(f"DEBUG: URL passed to decrypt: {url}", flush=True)
                                    decrypt_cp_encn_video(res_file, url)
                                    await status_msg.delete()
                                    print(f"✅ Decryption Successful: {res_file}")
                                except Exception as e_dec:
                                    print(f"❌ Decryption Failed: {e_dec}")
                                    await bot.send_message(channel_id, f"⚠️ Decryption Error: {e_dec}")
                                    # We don't raise here to allow upload of encrypted file if needed, 
                                    # but typically it's useless. Let's proceed.

                            filename = res_file
                            if prog1:
                                try: await prog1.delete(True)
                                except: pass
                            if prog:
                                try: await prog.delete(True)
                                except: pass
                            await helper.send_vid(bot, m, cc, filename, vidwatermark, thumb, name, prog, channel_id, message_thread_id=upload_thread_id)
                            
                            # Success! Cleanup messages
                            if retry_msg:
                                try:
                                    await retry_msg.delete(True)
                                except:
                                    pass
                            
                            success = True
                            count += 1
                            await asyncio.sleep(1)
                            break  # Exit retry loop on success
                            
                        except Exception as e:
                            if prog:
                                try:
                                    await prog.delete(True)
                                except:
                                    pass
                            if prog1:
                                try:
                                    await prog1.delete(True)
                                except:
                                    pass
                            current_error_msg = await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                            
                            if attempt == 3:  # Last attempt failed
                                # Clean up retry msg, keep only success/fail
                                if retry_msg:
                                    try:
                                        await retry_msg.delete(True)
                                    except:
                                        pass
                                count += 1
                                failed_count += 1
                            else:
                                await asyncio.sleep(3)  # Wait before retry
                    
                    if success:
                        continue
                
            except Exception as e:
                await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {url}\n\n<blockquote expandable><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                count += 1
                failed_count += 1
                continue

    except Exception as e:
        await m.reply_text(e)
        time.sleep(2)

    success_count = len(links) - failed_count
    video_count = v2_count + mpd_count + m3u8_count + yt_count + drm_count + zip_count + other_count
    if m.document:
        if raw_text7 == "/d":
            await bot.send_message(channel_id, f"<b>-┈━═.•°✅ Completed ✅°•.═━┈-</b>\n<blockquote><b>🎯Batch Name : {b_name}</b></blockquote>\n<blockquote>🔗 Total URLs: {len(links)} \n┃   ┠🔴 Total Failed URLs: {failed_count}\n┃   ┠🟢 Total Successful URLs: {success_count}\n┃   ┃   ┠🎥 Total Video URLs: {video_count}\n┃   ┃   ┠📄 Total PDF URLs: {pdf_count}\n┃   ┃   ┠📸 Total IMAGE URLs: {img_count}</blockquote>\n")
        else:
            await bot.send_message(channel_id, f"<b>-┈━═.•°✅ Completed ✅°•.═━┈-</b>\n<blockquote><b>🎯Batch Name : {b_name}</b></blockquote>\n<blockquote>🔗 Total URLs: {len(links)} \n┃   ┠🔴 Total Failed URLs: {failed_count}\n┃   ┠🟢 Total Successful URLs: {success_count}\n┃   ┃   ┠🎥 Total Video URLs: {video_count}\n┃   ┃   ┠📄 Total PDF URLs: {pdf_count}\n┃   ┃   ┠📸 Total IMAGE URLs: {img_count}</blockquote>\n")
            await bot.send_message(m.chat.id, f"<blockquote><b>✅ Your Task is completed, please check your Set Channel📱</b></blockquote>")
