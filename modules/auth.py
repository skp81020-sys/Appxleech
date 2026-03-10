from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler
from datetime import datetime
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import db
from vars import *

async def handle_subscription_end(client: Client, user_id: int):
    try:
        await client.send_message(
            user_id,
            "**⚠️ Subscription Ended**\n"
            "Your access has expired. Contact admin to renew."
        )
    except Exception:
        pass

# Command to add a new user
async def add_user_cmd(client: Client, message: Message):
    """Add a new user to the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text(AUTH_MESSAGES["not_admin"])
            return

        # Parse command arguments
        args = message.text.split()[1:]
        if len(args) != 2:
            await message.reply_text(
                AUTH_MESSAGES["invalid_format"].format(
                    format="/add user_id days\n\nExample:\n/add 123456789 30"
                )
            )
            return

        user_id = int(args[0])
        days = int(args[1])

        # Get bot username
        bot_username = client.me.username

        try:
            # Try to get user info from Telegram
            user = await client.get_users(user_id)
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
        except:
            # If can't get user info, use ID as name
            name = f"User {user_id}"

        # Add user to database with bot username
        success, expiry_date = db.add_user(user_id, name, days, bot_username)
        
        if success:
            # Format expiry date
            expiry_str = expiry_date.strftime("%d-%m-%Y %H:%M:%S")
            
            # Send success message to admin using template
            await message.reply_text(
                AUTH_MESSAGES["user_added"].format(
                    name=name,
                    user_id=user_id,
                    expiry_date=expiry_str
                )
            )

            # Try to notify the user using template
            try:
                await client.send_message(
                    user_id,
                    AUTH_MESSAGES["subscription_active"].format(
                        expiry_date=expiry_str
                    )
                )
            except Exception as e:
                print(f"Failed to notify user {user_id}: {str(e)}")
        else:
            await message.reply_text("❌ Failed to add user. Please try again.")

    except ValueError:
        await message.reply_text("❌ Invalid user ID or days. Please use numbers only.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to remove a user
async def remove_user_cmd(client: Client, message: Message):
    """Remove a user from the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("❌ Not authorized to remove users.")
            return

        # Parse command arguments
        args = message.text.split()[1:]
        if len(args) != 1:
            await message.reply_text(
                "❌ Invalid format!\n"
                "Use: /remove user_id\n"
                "Example: /remove 123456789"
            )
            return

        user_id = int(args[0])
        
        # Remove user from database
        if db.remove_user(user_id, client.me.username):
            await message.reply_text(f"✅ User {user_id} removed.")
        else:
            await message.reply_text(f"❌ User {user_id} not found.")

    except ValueError:
        await message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to list all users
async def list_users_cmd(client: Client, message: Message):
    """List all users of the bot"""
    try:
        # Check if sender is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("❌ Not authorized to list users.")
            return

        users = db.list_users(client.me.username)
        
        if not users:
            await message.reply_text("📝 No users found.")
            return

        # Format user list
        user_list = "**📝 Users List**\n\n"
        for user in users:
            expiry = user['expiry_date']
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            days_left = (expiry - datetime.now()).days
            
            user_list += (
                f"• Name: {user['name']}\n"
                f"• ID: {user['user_id']}\n"
                f"• Days Left: {days_left}\n"
                f"• Expires: {expiry.strftime('%d-%m-%Y')}\n"
                f"───────────────\n"
            )

        await message.reply_text(user_list)

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Command to check user's plan
async def my_plan_cmd(client: Client, message: Message):
    """Show user's current plan details"""
    try:
        user = db.get_user(message.from_user.id, client.me.username)
        
        if not user:
            await message.reply_text("❌ No active plan.")
            return

        expiry = user['expiry_date']
        if isinstance(expiry, str):
            expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        days_left = (expiry - datetime.now()).days

        await message.reply_text(
            f"**📱 Plan Details**\n\n"
            f"• Name: {user['name']}\n"
            f"• Days Left: {days_left}\n"
            f"• Expires: {expiry.strftime('%d-%m-%Y')}"
        )

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Register command handlers
add_user_handler = filters.command("add") & filters.private, add_user_cmd
remove_user_handler = filters.command("remove") & filters.private, remove_user_cmd
list_users_handler = filters.command("users") & filters.private, list_users_cmd
my_plan_handler = filters.command("plan") & filters.private, my_plan_cmd

# Decorator for checking user authorization
def check_auth():
    def decorator(func):
        async def wrapper(client, message, *args, **kwargs):
            bot_info = await client.get_me()
            bot_username = bot_info.username
            if not db.is_user_authorized(message.from_user.id, bot_username):
                return await message.reply(
                    "**❌ Access Denied**\n"
                    "Contact admin to get access."
                )
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator
