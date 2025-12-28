import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from telegram import Update, ChatMember, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8369433260:AAFRgg9zRzBzChyKGqmZ3H9Nw9xjYxNJ6mY")
ADMIN_IDS = list(map(int, os.getenv("6871652449,7896059741", "").split(","))) if os.getenv("ADMIN_IDS") else []
MAX_WARNINGS = 3
WARNING_EXPIRE_DAYS = 7

# Data storage (in production, use a database)
user_warnings: Dict[int, List[datetime]] = {}
group_rules: Dict[int, str] = {}
welcome_messages: Dict[int, str] = {}

class GroupHelpBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all command and message handlers"""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("rules", self.rules_command))
        self.application.add_handler(CommandHandler("warn", self.warn_command))
        self.application.add_handler(CommandHandler("warnings", self.warnings_command))
        self.application.add_handler(CommandHandler("kick", self.kick_command))
        self.application.add_handler(CommandHandler("ban", self.ban_command))
        self.application.add_handler(CommandHandler("mute", self.mute_command))
        self.application.add_handler(CommandHandler("unmute", self.unmute_command))
        self.application.add_handler(CommandHandler("setrules", self.set_rules_command))
        self.application.add_handler(CommandHandler("setwelcome", self.set_welcome_command))
        self.application.add_handler(CommandHandler("purge", self.purge_command))
        self.application.add_handler(CommandHandler("promote", self.promote_command))
        self.application.add_handler(CommandHandler("demote", self.demote_command))
        self.application.add_handler(CommandHandler("pin", self.pin_command))
        self.application.add_handler(CommandHandler("unpin", self.unpin_command))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_members))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.goodbye_member))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a welcome message when the command /start is issued."""
        user = update.effective_user
        
        if update.effective_chat.type == "private":
            welcome_text = f"""
👋 Hello {user.mention_html()}!

🤖 I'm GroupHelpBot - Your friendly group management assistant!

📋 **Available Commands:**
• /help - Show all commands
• /rules - Show group rules
• /warn @user - Warn a user
• /warnings @user - Check user warnings
• /kick @user - Kick a user
• /ban @user - Ban a user
• /mute @user [time] - Mute a user
• /unmute @user - Unmute a user

🔧 **Admin Commands:**
• /setrules [rules] - Set group rules
• /setwelcome [message] - Set welcome message
• /purge [number] - Delete multiple messages
• /promote @user - Promote to admin
• /demote @user - Remove admin
• /pin - Pin current message
• /unpin - Unpin current message

Add me to your group and make me admin to start managing!
            """
            await update.message.reply_html(welcome_text)
        else:
            await update.message.reply_text(
                "Hello! I'm here to help manage this group. Use /help to see all available commands."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a help message with all commands."""
        help_text = """
📚 **GroupHelpBot Commands:**

👥 **Basic Commands:**
• /rules - Show group rules
• /help - Show this help message

⚡ **Moderation Commands:**
• /warn @user [reason] - Warn a user
• /warnings @user - Check user warnings
• /kick @user [reason] - Kick a user from group
• /ban @user [reason] - Ban a user from group
• /mute @user [1h/1d/1w] - Mute a user
• /unmute @user - Unmute a user
• /purge [number] - Delete multiple messages

⚙️ **Admin Commands:**
• /setrules [rules] - Set group rules
• /setwelcome [message] - Set welcome message
• /promote @user - Promote user to admin
• /demote @user - Remove admin rights
• /pin - Pin current message
• /unpin - Unpin current message

💡 **Tips:**
• Make sure I have admin privileges for full functionality
• Use @username to mention users
• Time formats for mute: 1h, 2d, 1w
        """
        
        keyboard = [
            [InlineKeyboardButton("📜 Rules", callback_data="show_rules")],
            [InlineKeyboardButton("👮 Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("➕ Add to Group", url="http://t.me/your_bot_username?startgroup=true")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group rules."""
        chat_id = update.effective_chat.id
        rules = group_rules.get(chat_id, "No rules set yet. Admins can set rules using /setrules")
        
        await update.message.reply_text(f"📜 **Group Rules:**\n\n{rules}")
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Warn a user."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to warn users!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /warn @username [reason]")
            return
        
        # Parse username and reason
        username = context.args[0].replace("@", "")
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        # Get user from message reply or username
        target_user = None
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        else:
            # You would need to implement user lookup by username
            await update.message.reply_text("Please reply to a message or implement user lookup")
            return
        
        chat_id = update.effective_chat.id
        user_id = target_user.id
        
        # Add warning
        if user_id not in user_warnings:
            user_warnings[user_id] = []
        
        user_warnings[user_id].append(datetime.now())
        
        # Clean old warnings
        self.clean_old_warnings(user_id)
        
        warning_count = len(user_warnings[user_id])
        
        warning_message = (
            f"⚠️ Warning #{warning_count}/{MAX_WARNINGS}\n"
            f"User: {target_user.mention_html()}\n"
            f"Reason: {reason}\n\n"
        )
        
        if warning_count >= MAX_WARNINGS:
            warning_message += "🔴 MAX WARNINGS REACHED! User will be kicked."
            # Kick user
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.unban_chat_member(chat_id, user_id)
                warning_message += "\n✅ User has been kicked!"
            except Exception as e:
                warning_message += f"\n❌ Failed to kick: {str(e)}"
        else:
            warning_message += f"⚠️ {MAX_WARNINGS - warning_count} warnings left before kick"
        
        await update.message.reply_html(warning_message)
    
    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user warnings."""
        chat_id = update.effective_chat.id
        
        # Get user from message reply
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            user_id = target_user.id
            
            if user_id in user_warnings:
                warnings = user_warnings[user_id]
                self.clean_old_warnings(user_id)
                warning_count = len(warnings)
                
                warning_list = "\n".join([
                    f"{i+1}. {warn.strftime('%Y-%m-%d %H:%M')}"
                    for i, warn in enumerate(warnings[-10:])  # Show last 10 warnings
                ])
                
                message = (
                    f"📊 Warnings for {target_user.mention_html()}\n"
                    f"Total: {warning_count}/{MAX_WARNINGS}\n\n"
                    f"Recent warnings:\n{warning_list if warning_list else 'No active warnings'}"
                )
            else:
                message = f"✅ {target_user.mention_html()} has no warnings!"
        else:
            message = "Please reply to a user's message to check their warnings"
        
        await update.message.reply_html(message)
    
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kick a user from the group."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to kick users!")
            return
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            chat_id = update.effective_chat.id
            reason = " ".join(context.args) if context.args else "No reason provided"
            
            try:
                await context.bot.ban_chat_member(chat_id, target_user.id)
                await context.bot.unban_chat_member(chat_id, target_user.id)
                
                kick_message = (
                    f"👢 User {target_user.mention_html()} has been kicked!\n"
                    f"Reason: {reason}"
                )
                await update.message.reply_html(kick_message)
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to kick user: {str(e)}")
        else:
            await update.message.reply_text("Please reply to a user's message to kick them")
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban a user from the group."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to ban users!")
            return
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            chat_id = update.effective_chat.id
            reason = " ".join(context.args) if context.args else "No reason provided"
            
            try:
                await context.bot.ban_chat_member(chat_id, target_user.id)
                
                ban_message = (
                    f"🚫 User {target_user.mention_html()} has been banned!\n"
                    f"Reason: {reason}"
                )
                await update.message.reply_html(ban_message)
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")
        else:
            await update.message.reply_text("Please reply to a user's message to ban them")
    
    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mute a user for a specified time."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to mute users!")
            return
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            chat_id = update.effective_chat.id
            
            # Parse mute duration
            mute_duration = 60 * 60  # Default: 1 hour
            if context.args:
                time_arg = context.args[0].lower()
                if 'h' in time_arg:
                    hours = int(time_arg.replace('h', ''))
                    mute_duration = hours * 60 * 60
                elif 'd' in time_arg:
                    days = int(time_arg.replace('d', ''))
                    mute_duration = days * 24 * 60 * 60
                elif 'w' in time_arg:
                    weeks = int(time_arg.replace('w', ''))
                    mute_duration = weeks * 7 * 24 * 60 * 60
            
            until_date = datetime.now() + timedelta(seconds=mute_duration)
            
            try:
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                
                await context.bot.restrict_chat_member(
                    chat_id, target_user.id, permissions,
                    until_date=int(until_date.timestamp())
                )
                
                duration_text = self.format_duration(mute_duration)
                mute_message = (
                    f"🔇 User {target_user.mention_html()} has been muted for {duration_text}!"
                )
                await update.message.reply_html(mute_message)
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to mute user: {str(e)}")
        else:
            await update.message.reply_text("Usage: Reply to a user's message with /mute [1h/2d/1w]")
    
    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unmute a user."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to unmute users!")
            return
        
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            chat_id = update.effective_chat.id
            
            try:
                permissions = ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                
                await context.bot.restrict_chat_member(chat_id, target_user.id, permissions)
                await update.message.reply_html(f"🔊 User {target_user.mention_html()} has been unmuted!")
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to unmute user: {str(e)}")
        else:
            await update.message.reply_text("Please reply to a user's message to unmute them")
    
    async def set_rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set group rules."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to set rules!")
            return
        
        if context.args:
            rules = " ".join(context.args)
            chat_id = update.effective_chat.id
            group_rules[chat_id] = rules
            
            await update.message.reply_text("✅ Group rules have been updated!")
        else:
            await update.message.reply_text("Usage: /setrules [rules text]")
    
    async def set_welcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set welcome message."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to set welcome message!")
            return
        
        if context.args:
            welcome_message = " ".join(context.args)
            chat_id = update.effective_chat.id
            welcome_messages[chat_id] = welcome_message
            
            await update.message.reply_text("✅ Welcome message has been updated!")
        else:
            await update.message.reply_text("Usage: /setwelcome [welcome message]\n\nYou can use {username} and {mention} in the message.")
    
    async def purge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete multiple messages."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to purge messages!")
            return
        
        if update.message.reply_to_message:
            try:
                # Delete command message
                await update.message.delete()
                
                # Get message IDs to delete
                start_message_id = update.message.reply_to_message.message_id
                end_message_id = update.message.message_id
                
                # Delete messages
                for message_id in range(start_message_id, end_message_id):
                    try:
                        await context.bot.delete_message(update.effective_chat.id, message_id)
                    except:
                        continue
                
                # Send confirmation
                deleted_count = end_message_id - start_message_id
                confirmation = await context.bot.send_message(
                    update.effective_chat.id,
                    f"✅ Deleted {deleted_count} messages!"
                )
                
                # Delete confirmation after 3 seconds
                await asyncio.sleep(3)
                await confirmation.delete()
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to purge messages: {str(e)}")
        else:
            await update.message.reply_text("Reply to a message to purge from that point")
    
    async def promote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Promote a user to admin."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to promote users!")
            return
        
        # This is a simplified version
        # In reality, you'd need to use promote_chat_member with specific permissions
        await update.message.reply_text("Promote functionality requires specific permissions setup")
    
    async def demote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Demote an admin."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to demote users!")
            return
        
        await update.message.reply_text("Demote functionality requires specific permissions setup")
    
    async def pin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pin a message."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to pin messages!")
            return
        
        if update.message.reply_to_message:
            try:
                await update.message.reply_to_message.pin()
                await update.message.reply_text("📌 Message pinned!")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to pin message: {str(e)}")
        else:
            await update.message.reply_text("Reply to a message to pin it")
    
    async def unpin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unpin a message."""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ You need to be an admin to unpin messages!")
            return
        
        if update.message.reply_to_message:
            try:
                await update.message.reply_to_message.unpin()
                await update.message.reply_text("📌 Message unpinned!")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to unpin message: {str(e)}")
        else:
            await update.message.reply_text("Reply to a message to unpin it")
    
    async def welcome_new_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members to the group."""
        chat_id = update.effective_chat.id
        welcome_message = welcome_messages.get(chat_id, "Welcome {mention} to the group! 🎉")
        
        for new_member in update.message.new_chat_members:
            if new_member.id == context.bot.id:
                # Bot was added to the group
                await update.message.reply_text(
                    "🤖 Thanks for adding me! Make me an admin with necessary permissions "
                    "to enable all features. Use /help to see available commands."
                )
            else:
                # Welcome regular user
                personalized_message = welcome_message.format(
                    username=new_member.username or new_member.first_name,
                    mention=new_member.mention_html()
                )
                
                # Create welcome buttons
                keyboard = [
                    [InlineKeyboardButton("📜 Read Rules", callback_data="show_rules")],
                    [InlineKeyboardButton("👋 Say Hello", url=f"tg://user?id={new_member.id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_html(
                    personalized_message,
                    reply_markup=reply_markup
                )
    
    async def goodbye_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Say goodbye when a member leaves."""
        left_member = update.message.left_chat_member
        if left_member:
            goodbye_message = f"👋 Goodbye {left_member.mention_html()}! We'll miss you!"
            await update.message.reply_html(goodbye_message)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "show_rules":
            chat_id = update.effective_chat.id
            rules = group_rules.get(chat_id, "No rules set yet.")
            await query.edit_message_text(f"📜 **Group Rules:**\n\n{rules}")
        
        elif query.data == "admin_panel":
            if await self.is_admin(update, context):
                admin_text = """
🔧 **Admin Panel**

Quick actions:
• Use /warn @user to warn
• Use /kick @user to kick
• Use /purge to clean messages
• Use /pin to pin important messages

Settings:
• /setrules - Configure group rules
• /setwelcome - Set welcome message
                """
                await query.edit_message_text(admin_text)
            else:
                await query.edit_message_text("❌ Admin panel is only available for group admins")
    
    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is admin."""
        user = update.effective_user
        chat = update.effective_chat
        
        if user.id in ADMIN_IDS:
            return True
        
        try:
            chat_member = await chat.get_member(user.id)
            return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except:
            return False
    
    def clean_old_warnings(self, user_id: int):
        """Remove warnings older than WARNING_EXPIRE_DAYS."""
        if user_id in user_warnings:
            cutoff_date = datetime.now() - timedelta(days=WARNING_EXPIRE_DAYS)
            user_warnings[user_id] = [
                warn for warn in user_warnings[user_id]
                if warn > cutoff_date
            ]
            
            if not user_warnings[user_id]:
                del user_warnings[user_id]
    
    def format_duration(self, seconds: int) -> str:
        """Format seconds into human readable duration."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes"
        elif seconds < 86400:
            return f"{seconds // 3600} hours"
        else:
            return f"{seconds // 86400} days"
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log errors."""
        logger.error(f"Update {update} caused error {context.error}")
    
    def run(self):
        """Run the bot."""
        print("🤖 GroupHelpBot is starting...")
        print("Press Ctrl+C to stop")
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

# Required imports for asyncio
import asyncio

def main():
    """Start the bot."""
    bot = GroupHelpBot(BOT_TOKEN)
    bot.run()

if __name__ == '__main__':
    main()
