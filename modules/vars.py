#🇳‌🇮‌🇰‌🇭‌🇮‌🇱‌
# Add your details here and then deploy by clicking on HEROKU Deploy button
import os
from os import environ

API_ID = int(environ.get("API_ID", "26713214"))
API_HASH = environ.get("API_HASH", "fc87c0fb26949deb0bc940dd35c1658d")
BOT_TOKEN = environ.get("BOT_TOKEN", "")

OWNER = int(environ.get("OWNER", "7752941299"))
CREDIT = environ.get("CREDIT", '👨‍💻Rick Johnson')
CREDIT_LINK = environ.get("CREDIT_LINK", 'https://t.me/rick007contactbot')
cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")

# MongoDB Configuration
MONGO_URL = environ.get("MONGO_URL", "")
DATABASE_NAME = environ.get("DATABASE_NAME", "eagle")

# Owner and Admin Configuration
OWNER_ID = int(environ.get("OWNER_ID", "7752941299"))  # Use OWNER as fallback
ADMINS = [OWNER_ID]  # Can be extended via environment
  
#WEBHOOK = True  # Don't change this
#PORT = int(os.environ.get("PORT", 8080))  # Default to 8000 if not set


# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,
api_url = "http://master-api-v3.vercel.app/"
api_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNzkxOTMzNDE5NSIsInRnX3VzZXJuYW1lIjoi4p61IFtvZmZsaW5lXSIsImlhdCI6MTczODY5MjA3N30.SXzZ1MZcvMp5sGESj0hBKSghhxJ3k1GTWoBUbivUe1I"
token_cp ='eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9r'
adda_token = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJkcGthNTQ3MEBnbWFpbC5jb20iLCJhdWQiOiIxNzg2OTYwNSIsImlhdCI6MTc0NDk0NDQ2NCwiaXNzIjoiYWRkYTI0Ny5jb20iLCJuYW1lIjoiZHBrYSIsImVtYWlsIjoiZHBrYTU0NzBAZ21haWwuY29tIiwicGhvbmUiOiI3MzUyNDA0MTc2IiwidXNlcklkIjoiYWRkYS52MS41NzMyNmRmODVkZDkxZDRiNDkxN2FiZDExN2IwN2ZjOCIsImxvZ2luQXBpVmVyc2lvbiI6MX0.0QOuYFMkCEdVmwMVIPeETa6Kxr70zEslWOIAfC_ylhbku76nDcaBoNVvqN4HivWNwlyT0jkUKjWxZ8AbdorMLg"
photologo = 'https://i.ibb.co/zTPJFct8/photo-2025-04-25-12-55-01-7497233558289776672.jpg' #https://envs.sh/GV0.jpg
photoyt = 'https://i.ibb.co/zTPJFct8/photo-2025-04-25-12-55-01-7497233558289776672.jpg' #https://envs.sh/GVi.jpg
photocp = 'https://i.ibb.co/zTPJFct8/photo-2025-04-25-12-55-01-7497233558289776672.jpg'
photozip = 'https://i.ibb.co/zTPJFct8/photo-2025-04-25-12-55-01-7497233558289776672.jpg'
# .....,.....,.......,...,.......,....., .....,.....,.......,...,.

# Message Templates for Authentication
AUTH_MESSAGES = {
    "subscription_active": """<b>🎉 Subscription Activated!</b>

<blockquote>Your subscription has been activated and will expire on {expiry_date}.
You can now use the bot!</blockquote>

Type /start to start uploading """,

    "subscription_expired": """<b>⚠️ Your Subscription Has Ended</b>

<blockquote>Your access to the bot has been revoked as your subscription period has expired.
Please contact the admin to renew your subscription.</blockquote>""",

    "user_added": """<b>✅ User Added Successfully!</b>

<blockquote>👤 Name : {name}
🆔 USER ID : {user_id}
📅 EXPIRY : {expiry_date}</blockquote>""",

    "user_removed": """<b>✅ User Removed Successfully !</b>

<blockquote>User ID {user_id} has been removed from authorized users.</blockquote>""",

    "access_denied": """<b>⚠️ Access Denied!</b>

<blockquote>You are not authorized to use this bot.
Please contact the admin to get access.</blockquote>""",

    "not_admin": "⚠️ You are not authorized to use this command!",
    
    "invalid_format": """❌ <b>Invalid Format!</b>

<blockquote>Use format: {format}</blockquote>"""
}

