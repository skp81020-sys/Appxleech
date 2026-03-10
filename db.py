import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
from pymongo import MongoClient, errors
from pymongo.database import Database as MongoDatabase
from pymongo.collection import Collection
from modules.vars import *
import colorama
from colorama import Fore, Style
import time
import certifi
from typing_extensions import Literal

# Init colors for Windows
colorama.init()

class Database:
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        """
        Initialize MongoDB connection with retry logic
        
        Args:
            max_retries: Maximum connection attempts
            retry_delay: Delay between retries in seconds
        """
        self._print_startup_message()
        self.client: Optional[MongoClient] = None
        self.db: Optional[MongoDatabase] = None
        self.users: Optional[Collection] = None
        self.settings: Optional[Collection] = None
        
        self._connect_with_retry(max_retries, retry_delay)
        
    def _connect_with_retry(self, max_retries: int, retry_delay: float):
        """Establish MongoDB connection with retry mechanism"""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"{Fore.YELLOW}⌛ Attempt {attempt}/{max_retries}: Connecting to MongoDB...{Style.RESET_ALL}")
                
                # Enhanced connection parameters
                self.client = MongoClient(
                    MONGO_URL,
                    serverSelectionTimeoutMS=20000,
                    connectTimeoutMS=20000,
                    socketTimeoutMS=30000,
                    tlsCAFile=certifi.where(),
                    retryWrites=True,
                    retryReads=True
                )
                
                # Test connection
                self.client.server_info()
                
                # Initialize database and collections
                self.db = self.client.get_database(DATABASE_NAME)
                self.users = self.db['users']
                self.settings = self.db['user_settings']
                
                print(f"{Fore.GREEN}✓ MongoDB Connected Successfully!{Style.RESET_ALL}")
                self._initialize_database()
                return
                
            except errors.ServerSelectionTimeoutError as e:
                print(f"{Fore.RED}✕ Connection attempt {attempt} failed: {str(e)}{Style.RESET_ALL}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    raise ConnectionError(f"Failed to connect to MongoDB after {max_retries} attempts") from e
            except Exception as e:
                print(f"{Fore.RED}✕ Unexpected error during connection: {str(e)}{Style.RESET_ALL}")
                raise

    def _print_startup_message(self):
        """Print formatted startup message"""
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"{Fore.CYAN}🚀 DRM Handler Bot - Database Initialization")
        print(f"{'='*50}{Style.RESET_ALL}\n")

    def _initialize_database(self):
        """Initialize database indexes and perform migrations"""
        print(f"{Fore.YELLOW}⌛ Setting up database...{Style.RESET_ALL}")
        
        try:
            # Create indexes with error handling
            self._create_indexes()
            print(f"{Fore.GREEN}✓ Database indexes created!{Style.RESET_ALL}")
            
            # Run migrations
            self._migrate_existing_users()
            
            print(f"{Fore.GREEN}✓ Database initialization complete!{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"{Fore.RED}⚠ Database initialization error: {str(e)}{Style.RESET_ALL}")
            raise

    def _create_indexes(self):
        """Create necessary indexes with error handling"""
        index_results = []
        
        try:
            # Compound index for users collection
            self.users.create_index(
                [("bot_username", 1), ("user_id", 1)], 
                unique=True,
                name="user_identity"
            )
            index_results.append("users compound index")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Could not create users compound index: {str(e)}{Style.RESET_ALL}")

        try:
            # Single field index for settings
            self.settings.create_index(
                [("user_id", 1)],
                unique=True,
                name="user_settings"
            )
            index_results.append("settings index")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Could not create settings index: {str(e)}{Style.RESET_ALL}")

        try:
            # TTL index for expiry dates
            self.users.create_index(
                "expiry_date",
                name="user_expiry",
                expireAfterSeconds=0  # Documents will be deleted at expiry_date
            )
            index_results.append("expiry TTL index")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Could not create expiry index: {str(e)}{Style.RESET_ALL}")
            
        # ✅ NEW INDEXES FOR TOPIC THREADS
        try:
            # Compound index for topic_threads collection
            self.db.topic_threads.create_index(
                [("bot_username", 1), ("channel_id", 1), ("topic_name", 1)], 
                unique=True,
                name="topic_identity"
            )
            index_results.append("topic_threads compound index")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Could not create topic_threads index: {str(e)}{Style.RESET_ALL}")

        try:
            # TTL index for old topics (auto-delete after 30 days)
            self.db.topic_threads.create_index(
                "last_used",
                name="topic_last_used",
                expireAfterSeconds=60*60*24*30  # 30 days
            )
            index_results.append("topic TTL index")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Could not create topic TTL index: {str(e)}{Style.RESET_ALL}")
            
        return index_results

    def _migrate_existing_users(self):
        """Migrate existing users to new schema if needed"""
        try:
            update_result = self.users.update_many(
                {"bot_username": {"$exists": False}},
                {"$set": {"bot_username": "drmhandler"}}
            )
            
            if update_result.modified_count > 0:
                print(f"{Fore.YELLOW}⚠ Migrated {update_result.modified_count} users to new schema{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}⚠ Could not migrate users: {str(e)}{Style.RESET_ALL}")

    def get_user(self, user_id: int, bot_username: str = "drmhandler") -> Optional[dict]:
        """
        Retrieve a user document
        
        Args:
            user_id: Telegram user ID
            bot_username: Bot username (default: "drmhandler")
            
        Returns:
            User document or None if not found
        """
        try:
            return self.users.find_one({
                "user_id": user_id,
                "bot_username": bot_username
            })
        except Exception as e:
            print(f"{Fore.RED}Error getting user {user_id}: {str(e)}{Style.RESET_ALL}")
            return None

    def is_user_authorized(self, user_id: int, bot_username: str = "drmhandler") -> bool:
        """
        Check if user is authorized (admin or has valid subscription)
        
        Args:
            user_id: Telegram user ID
            bot_username: Bot username
            
        Returns:
            True if authorized, False otherwise
        """
        try:
            # First check if user is admin/owner
            if user_id == OWNER_ID or user_id in ADMINS:
                return True
                
            # Then check subscription status
            user = self.get_user(user_id, bot_username)
            if not user:
                return False
                
            expiry = user.get('expiry_date')
            if not expiry:
                return False
                
            # Handle string expiry dates (backward compatibility)
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                
            return expiry > datetime.now()
            
        except Exception as e:
            print(f"{Fore.RED}Authorization error for {user_id}: {str(e)}{Style.RESET_ALL}")
            return False

    def add_user(self, user_id: int, name: str, days: int, 
                bot_username: str = "drmhandler") -> tuple[bool, Optional[datetime]]:
        """
        Add or update a user in the database
        
        Args:
            user_id: Telegram user ID
            name: User's display name
            days: Subscription duration in days
            bot_username: Bot username
            
        Returns:
            Tuple of (success, expiry_date)
        """
        try:
            expiry_date = datetime.now() + timedelta(days=days)
            update_result = self.users.update_one(
                {"user_id": user_id, "bot_username": bot_username},
                {"$set": {
                    "name": name,
                    "expiry_date": expiry_date,
                    "added_date": datetime.now(),
                    "last_updated": datetime.now()
                }},
                upsert=True
            )
            
            if update_result.upserted_id or update_result.modified_count > 0:
                return True, expiry_date
            return False, None
            
        except Exception as e:
            print(f"{Fore.RED}Add user error for {user_id}: {str(e)}{Style.RESET_ALL}")
            return False, None

    def remove_user(self, user_id: int, bot_username: str = "drmhandler") -> bool:
        """
        Remove a user from the database
        
        Args:
            user_id: Telegram user ID
            bot_username: Bot username
            
        Returns:
            True if user was deleted, False otherwise
        """
        try:
            result = self.users.delete_one({
                "user_id": user_id,
                "bot_username": bot_username
            })
            return result.deleted_count > 0
        except Exception as e:
            print(f"{Fore.RED}Remove user error for {user_id}: {str(e)}{Style.RESET_ALL}")
            return False

    def list_users(self, bot_username: str = "drmhandler") -> List[dict]:
        """
        List all users for a specific bot
        
        Args:
            bot_username: Bot username to filter by
            
        Returns:
            List of user documents
        """
        try:
            return list(self.users.find(
                {"bot_username": bot_username},
                {"_id": 0, "name": 1, "user_id": 1, "expiry_date": 1}
            ))
        except Exception as e:
            print(f"{Fore.RED}List users error: {str(e)}{Style.RESET_ALL}")
            return []

    def is_admin(self, user_id: int) -> bool:
        """
        Check if user is admin or owner
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if admin/owner, False otherwise
        """
        try:
            is_admin = user_id == OWNER_ID or user_id in ADMINS
            if is_admin:
                print(f"{Fore.GREEN}✓ Admin/Owner {user_id} verified{Style.RESET_ALL}")
            return is_admin
        except Exception as e:
            print(f"{Fore.RED}Admin check error: {str(e)}{Style.RESET_ALL}")
            return False

    def get_log_channel(self, bot_username: str):
        """Get the log channel ID for a specific bot"""
        try:
            settings = self.db.bot_settings.find_one({"bot_username": bot_username})
            if settings and 'log_channel' in settings:
                return settings['log_channel']
            return None
        except Exception as e:
            print(f"Error getting log channel: {str(e)}")
            return None

    def set_log_channel(self, bot_username: str, channel_id: int):
        """Set the log channel ID for a specific bot"""
        try:
            self.db.bot_settings.update_one(
                {"bot_username": bot_username},
                {"$set": {"log_channel": channel_id}},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error setting log channel: {str(e)}")
            return False
            
    def list_bot_usernames(self) -> List[str]:
        """
        Get distinct bot usernames from users collection
        
        Returns:
            List of bot usernames
        """
        try:
            usernames = self.users.distinct("bot_username")
            return usernames if usernames else ["drmhandler"]
        except Exception as e:
            print(f"{Fore.RED}List bot usernames error: {str(e)}{Style.RESET_ALL}")
            return ["drmhandler"]

    async def cleanup_expired_users(self, bot) -> int:
        """
        Clean up expired users and notify them
        
        Args:
            bot: Telegram bot instance
            
        Returns:
            Number of users removed
        """
        try:
            current_time = datetime.now()
            expired_users = self.users.find({
                "expiry_date": {"$lt": current_time},
                "user_id": {"$nin": [OWNER_ID] + ADMINS}
            })

            removed_count = 0
            for user in expired_users:
                try:
                    # Notify user
                    await bot.send_message(
                        user["user_id"],
                        f"**⚠️ Your subscription has expired!**\n\n"
                        f"• Name: {user['name']}\n"
                        f"• Expired on: {user['expiry_date'].strftime('%d-%m-%Y')}\n\n"
                        f"Contact admin to renew your subscription."
                    )
                    
                    # Remove user
                    self.users.delete_one({"_id": user["_id"]})
                    removed_count += 1

                    # Log to admins
                    log_msg = (
                        f"**🚫 Removed Expired User**\n\n"
                        f"• Name: {user['name']}\n"
                        f"• ID: {user['user_id']}\n"
                        f"• Expired on: {user['expiry_date'].strftime('%d-%m-%Y')}"
                    )
                    for admin in ADMINS + [OWNER_ID]:
                        try:
                            await bot.send_message(admin, log_msg)
                        except:
                            continue

                except Exception as e:
                    print(f"{Fore.YELLOW}Error processing user {user['user_id']}: {str(e)}{Style.RESET_ALL}")
                    continue

            return removed_count

        except Exception as e:
            print(f"{Fore.RED}Cleanup error: {str(e)}{Style.RESET_ALL}")
            return 0

    def get_user_expiry_info(self, user_id: int, bot_username: str = "drmhandler") -> Optional[dict]:
        """
        Get user's subscription expiry information
        
        Args:
            user_id: Telegram user ID
            bot_username: Bot username
            
        Returns:
            Dictionary with expiry info or None if not found
        """
        try:
            user = self.get_user(user_id, bot_username)
            if not user:
                return None

            expiry = user.get('expiry_date')
            if not expiry:
                return None

            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")

            days_left = (expiry - datetime.now()).days

            return {
                "name": user.get('name', 'Unknown'),
                "user_id": user_id,
                "expiry_date": expiry.strftime("%d-%m-%Y"),
                "days_left": days_left,
                "added_date": user.get('added_date', 'Unknown'),
                "is_active": days_left > 0
            }

        except Exception as e:
            print(f"{Fore.RED}Get expiry info error for {user_id}: {str(e)}{Style.RESET_ALL}")
            return None

    # ==================== TOPIC THREADS FUNCTIONS ====================
    
    def get_topic_thread(self, bot_username: str, channel_id: int, topic_name: str) -> Optional[int]:
        """
        Get existing topic thread ID from database
        
        Args:
            bot_username: Bot username
            channel_id: Channel ID
            topic_name: Topic name
            
        Returns:
            Thread ID if found, None otherwise
        """
        try:
            collection = self.db['topic_threads']
            topic_data = collection.find_one({
                'bot_username': bot_username,
                'channel_id': channel_id,
                'topic_name': topic_name
            })
            return topic_data['thread_id'] if topic_data else None
        except Exception as e:
            print(f"{Fore.RED}Error getting topic thread: {str(e)}{Style.RESET_ALL}")
            return None

    def save_topic_thread(self, bot_username: str, channel_id: int, topic_name: str, thread_id: int) -> bool:
        """
        Save topic thread ID to database
        
        Args:
            bot_username: Bot username
            channel_id: Channel ID
            topic_name: Topic name
            thread_id: Thread ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self.db['topic_threads']
            collection.update_one(
                {
                    'bot_username': bot_username,
                    'channel_id': channel_id,
                    'topic_name': topic_name
                },
                {
                    '$set': {
                        'thread_id': thread_id,
                        'created_at': datetime.now(),
                        'last_used': datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            print(f"{Fore.RED}Error saving topic thread: {str(e)}{Style.RESET_ALL}")
            return False

    def get_all_topics(self, bot_username: str, channel_id: int) -> List[dict]:
        """
        Get all topics for a specific channel
        
        Args:
            bot_username: Bot username
            channel_id: Channel ID
            
        Returns:
            List of topic documents
        """
        try:
            collection = self.db['topic_threads']
            return list(collection.find({
                'bot_username': bot_username,
                'channel_id': channel_id
            }, {'_id': 0}))
        except Exception as e:
            print(f"{Fore.RED}Error getting topics: {str(e)}{Style.RESET_ALL}")
            return []

    def cleanup_old_topics(self, bot_username: str, days: int = 30) -> int:
        """
        Delete topics older than specified days
        
        Args:
            bot_username: Bot username
            days: Days threshold
            
        Returns:
            Number of topics deleted
        """
        try:
            collection = self.db['topic_threads']
            cutoff_date = datetime.now() - timedelta(days=days)
            result = collection.delete_many({
                'bot_username': bot_username,
                'last_used': {'$lt': cutoff_date}
            })
            return result.deleted_count
        except Exception as e:
            print(f"{Fore.RED}Error cleaning up topics: {str(e)}{Style.RESET_ALL}")
            return 0

    # ==================== END OF TOPIC FUNCTIONS ====================


    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print(f"{Fore.YELLOW}✓ MongoDB connection closed{Style.RESET_ALL}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection"""
        self.close()

# 🔰 Startup Message
print(f"\n{Fore.CYAN}{'='*50}")
print(f"🤖 Initializing DRM Handler Bot Database")
print(f"{'='*50}{Style.RESET_ALL}\n")

# 🔌 Connect to DB with error handling
try:
    db = Database(max_retries=3, retry_delay=2)
except Exception as e:
    print(f"{Fore.RED}✕ Fatal Error: DB initialization failed!{Style.RESET_ALL}")
    raise
