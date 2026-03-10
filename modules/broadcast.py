import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import db
from vars import OWNER, CREDIT
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, PeerIdInvalid, UserIsBlocked, InputUserDeactivated

# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,
# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,

async def broadcast_handler(client: Client, message: Message):
    if message.chat.id != OWNER:
        return
    if not message.reply_to_message:
        await message.reply_text("**Reply to any message (text, photo, video, or file) with /broadcast to send it to all users.**")
        return
    
    bot_username = client.me.username
    users = db.list_users(bot_username)
    
    if not users:
        await message.reply_text("**No users found in database.**")
        return
    
    success = 0
    fail = 0
    for user in users:
        user_id = user['user_id']
        try:
            # Text
            if message.reply_to_message.text:
                await client.send_message(user_id, message.reply_to_message.text)
            # Photo
            elif message.reply_to_message.photo:
                await client.send_photo(
                    user_id,
                    photo=message.reply_to_message.photo.file_id,
                    caption=message.reply_to_message.caption or ""
                )
            # Video
            elif message.reply_to_message.video:
                await client.send_video(
                    user_id,
                    video=message.reply_to_message.video.file_id,
                    caption=message.reply_to_message.caption or ""
                )
            # Document
            elif message.reply_to_message.document:
                await client.send_document(
                    user_id,
                    document=message.reply_to_message.document.file_id,
                    caption=message.reply_to_message.caption or ""
                )
            else:
                await client.forward_messages(user_id, message.chat.id, message.reply_to_message.message_id)

            success += 1
        except (FloodWait, PeerIdInvalid, UserIsBlocked, InputUserDeactivated):
            fail += 1
            continue
        except Exception as e:
            fail += 1
            continue

    await message.reply_text(f"<b>Broadcast complete!</b>\n<blockquote><b>✅ Success: {success}\n❎ Failed: {fail}</b></blockquote>")
  
# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,

async def broadusers_handler(client: Client, message: Message):
    if message.chat.id != OWNER:
        return

    bot_username = client.me.username
    users = db.list_users(bot_username)

    if not users:
        await message.reply_text("**No users found in database.**")
        return

    user_infos = []
    for user in users:
        user_id = user['user_id']
        try:
            user_obj = await client.get_users(int(user_id))
            fname = user_obj.first_name if user_obj.first_name else " "
            user_infos.append(f"[{user_id}](tg://openmessage?user_id={user_id}) | `{fname}`")
        except Exception:
            user_infos.append(f"[{user_id}](tg://openmessage?user_id={user_id})")

    total = len(user_infos)
    text = (
        f"<blockquote><b>Total Users: {total}</b></blockquote>\n\n"
        "<b>Users List:</b>\n"
        + "\n".join(user_infos)
    )
    await message.reply_text(text)
    
# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,
# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,
