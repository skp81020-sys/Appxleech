
import aiohttp
import asyncio
from vars import BOT_TOKEN
from pyrogram.errors import FloodWait

# Cache to store topic_name -> thread_id mapping to avoid API spam
# Format: { chat_id: { "Topic Name": thread_id } }
TOPIC_CACHE = {}

def extract_autotopic_name(filename):
    """
    Extracts the 'Autotopic' name from the filename.
    Rule: The content of the FIRST bracket group.
    Supports () and [].
    Example: "(a) (b) xyz" -> "a"
    """
    stack = []
    start_wrapper = None
    start_index = -1
    
    # Check if filename starts with a bracket (ignoring leading whitespace)
    clean_name = filename.strip()
    if not (clean_name.startswith("(") or clean_name.startswith("[")):
        return None
    
    for i, char in enumerate(filename):
        if char in "([":
            if not stack:
                start_index = i
                start_wrapper = char
            stack.append(char)
        elif char in ")]":
            if stack:
                last_open = stack[-1]
                if (last_open == "(" and char == ")") or (last_open == "[" and char == "]"):
                    stack.pop()
                    if not stack:
                        # Found the first complete group
                        return filename[start_index+1:i].strip()
    return None

async def get_or_create_forum_topic(db, bot_username, chat_id, topic_name):
    """
    Creates a forum topic using direct HTTP Bot API to avoid version conflicts.
    Checks DB first for existing topic to prevent duplicates.
    Updates the TOPIC_CACHE and DB with the new topic ID.
    """
    if not str(chat_id).startswith("-100"): # Only supergroups support topics
        return None

    global TOPIC_CACHE
    if chat_id not in TOPIC_CACHE:
        TOPIC_CACHE[chat_id] = {}

    # 1. Check Memory Cache
    if topic_name in TOPIC_CACHE[chat_id]:
        return TOPIC_CACHE[chat_id][topic_name]

    # 2. Check Database (Persistence)
    stored_thread_id = db.get_topic_thread(bot_username, chat_id, topic_name)
    if stored_thread_id:
        TOPIC_CACHE[chat_id][topic_name] = stored_thread_id
        return stored_thread_id

    # 3. Create via API
    try:
        async with aiohttp.ClientSession() as session:
            # print(f"🛠️ Creating topic '{topic_name}' via HTTP API...")
            api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/createForumTopic"
            payload = {
                "chat_id": chat_id,
                "name": topic_name,
                "icon_color": 0x6FB9F0 # Optional blueish color
            }
            async with session.post(api_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        current_message_thread_id = data["result"]["message_thread_id"]
                        
                        # 4. Save to Cache and DB
                        TOPIC_CACHE[chat_id][topic_name] = current_message_thread_id
                        db.save_topic_thread(bot_username, chat_id, topic_name, current_message_thread_id)
                        
                        print(f"✅ Topic '{topic_name}' created via HTTP. ID: {current_message_thread_id}")
                        await asyncio.sleep(1) # Rate limit safety
                        return current_message_thread_id
                    else:
                        print(f"❌ HTTP Topic API Error: {data}")
                        return None
                else:
                    err_text = await resp.text()
                    print(f"❌ HTTP Topic API Fail {resp.status}: {err_text}")
                    return None
                    
    except Exception as e:
        print(f"Failed to create topic '{topic_name}': {e}")
        return None

async def send_document_with_fallback(bot, chat_id, document, caption, message_thread_id, **kwargs):
    """
    Sends a document with automatic fallback to reply_to_message_id if message_thread_id fails.
    """
    try:
        return await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            message_thread_id=message_thread_id,
            **kwargs
        )
    except TypeError:
        # Fallback for older Pyrogram/Pyrofork versions
        return await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            reply_to_message_id=message_thread_id,
            **kwargs
        )

async def send_video_with_fallback(bot, chat_id, video, caption, message_thread_id, **kwargs):
    """
    Sends a video with automatic fallback.
    """
    try:
        print(f"DEBUG: Attempting send_video with message_thread_id={message_thread_id}")
        return await bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            message_thread_id=message_thread_id,
            **kwargs
        )
    except TypeError:
        print(f"DEBUG: Falling back to reply_to_message_id={message_thread_id}")
        return await bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            reply_to_message_id=message_thread_id,
            **kwargs
        )

async def send_photo_with_fallback(bot, chat_id, photo, caption, message_thread_id, **kwargs):
    """
    Sends a photo with automatic fallback.
    """
    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            message_thread_id=message_thread_id,
            **kwargs
        )
    except TypeError:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_to_message_id=message_thread_id,
            **kwargs
        )
