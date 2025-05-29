import logging
import requests
import os
import time
import json
import signal
import sys
from collections import defaultdict
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Enable logging with more detailed format
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Base URL for Samurai API
SAMURAI_API_URL = "https://provider2api.onrender.com/api/provider2"

# Define available AI models
AI_MODELS = {
    "claude": {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4"},
    "opus": {"id": "anthropic/claude-opus-4", "name": "Claude Opus 4"},
    "gpt4": {"id": "openai/gpt-4", "name": "GPT-4"},
    "gpt45": {"id": "openai/gpt-4.5-preview", "name": "GPT-4.5 (Preview)"},
    "o1pro": {"id": "openai/o1-pro", "name": "OpenAI o1-pro"},
    "gemini": {"id": "google/gemini-pro", "name": "Gemini Pro"},
    "gemini25": {"id": "google/gemini-2.5-pro-preview-03-25", "name": "Gemini 2.5 Pro (Preview)"}
}

# Default model
DEFAULT_MODEL = "openai/gpt-4"

# ------------------ RATE LIMITING IMPLEMENTATION ------------------

# Track user requests
user_request_times = defaultdict(list)
# Default rate limits
DEFAULT_REQUESTS_PER_MINUTE = 5
REQUEST_WINDOW = 60  # seconds

def get_user_rate_limit(user_id):
    """Get rate limit based on user role"""
    role = get_user_role(user_id)
    if role == "admin":
        return 30  # Higher limit for admins
    elif role == "premium":
        return 15  # Medium limit for premium users
    return DEFAULT_REQUESTS_PER_MINUTE  # Standard limit

def is_rate_limited(user_id):
    """Check if a user has exceeded their rate limit"""
    current_time = time.time()
    # Remove old requests outside the window
    user_request_times[user_id] = [t for t in user_request_times[user_id] 
                                  if current_time - t < REQUEST_WINDOW]
    
    # Get user's rate limit
    user_limit = get_user_rate_limit(user_id)
    
    # Check if user has made too many requests
    if len(user_request_times[user_id]) >= user_limit:
        return True
    
    # Add current request time
    user_request_times[user_id].append(current_time)
    return False

# ------------------ USER ROLES IMPLEMENTATION ------------------

# Define user roles (could be stored in a database for persistence)
user_roles = {
    # Example - replace with actual admin user IDs
    123456789: "admin",  # Replace with your Telegram user ID
    # Add more users as needed
}

def get_user_role(user_id):
    """Get user role (default to "standard" if not specified)"""
    return user_roles.get(user_id, "standard")

# ------------------ ANALYTICS IMPLEMENTATION ------------------

# Track global usage statistics
total_requests = 0
model_usage_counts = defaultdict(int)
user_usage_counts = defaultdict(int)
user_first_seen = {}
daily_usage = defaultdict(int)
hourly_usage = defaultdict(int)

def record_usage(user_id, model_id):
    """Record usage statistics"""
    global total_requests
    
    # Increment counters
    total_requests += 1
    model_usage_counts[model_id] += 1
    user_usage_counts[user_id] += 1
    
    # Record first time seeing this user if new
    if user_id not in user_first_seen:
        user_first_seen[user_id] = time.time()
    
    # Record time-based analytics
    current_time = time.time()
    current_date = time.strftime("%Y-%m-%d", time.localtime(current_time))
    current_hour = time.strftime("%Y-%m-%d-%H", time.localtime(current_time))
    
    daily_usage[current_date] += 1
    hourly_usage[current_hour] += 1

# ------------------ TELEGRAM BOT FUNCTIONS ------------------

# Function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the user starts the bot."""
    user_name = update.message.from_user.first_name
    user_id = update.message.from_user.id
    
    # Record this user for analytics
    if user_id not in user_first_seen:
        user_first_seen[user_id] = time.time()
    
    role = get_user_role(user_id)
    role_info = ""
    
    if role == "admin":
        role_info = "🔑 You have admin privileges with higher rate limits and access to analytics.\n\n"
    elif role == "premium":
        role_info = "⭐ You have premium access with higher rate limits.\n\n"
    
    # Calculate user's rate limit
    rate_limit = get_user_rate_limit(user_id)
    
    welcome_message = (
        f"👋 Hello {user_name}! I'm your multi-AI assistant powered by @medusaXD\n\n"
        f"{role_info}"
        f"Your current rate limit: {rate_limit} requests per minute.\n\n"
        f"Here are the commands you can use:\n\n"
        f"• Simply type your question to use the default model (GPT-4)\n"
        f"• /claude <question> - Ask Claude Sonnet 4\n"
        f"• /opus <question> - Ask Claude Opus 4\n"
        f"• /gpt4 <question> - Ask GPT-4\n"
        f"• /gpt45 <question> - Ask GPT-4.5 Preview\n"
        f"• /o1pro <question> - Ask OpenAI o1-pro\n"
        f"• /gemini <question> - Ask Google Gemini Pro\n"
        f"• /gemini25 <question> - Ask Gemini 2.5 Pro\n\n"
        f"Additional commands:\n"
        f"• /models - View all available AI models\n"
        f"• /status - Check API status\n"
        f"• /help - Show this help message"
    )
    
    if role == "admin":
        welcome_message += f"\n\nAdmin commands:\n• /stats - View bot usage statistics"
    
    await update.message.reply_text(welcome_message)

# Function to handle the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with available commands when the command /help is issued."""
    user_id = update.message.from_user.id
    role = get_user_role(user_id)
    rate_limit = get_user_rate_limit(user_id)
    
    help_text = (
        "🤖 **Multi-AI Assistant Help**\n\n"
        f"Your role: {role.upper()} (Rate limit: {rate_limit}/minute)\n\n"
        "Choose your AI model with these commands:\n\n"
        "• /claude <question> - Ask Claude Sonnet 4\n"
        "• /opus <question> - Ask Claude Opus 4\n"
        "• /gpt4 <question> - Ask GPT-4\n"
        "• /gpt45 <question> - Ask GPT-4.5 Preview\n"
        "• /o1pro <question> - Ask OpenAI o1-pro\n"
        "• /gemini <question> - Ask Google Gemini Pro\n"
        "• /gemini25 <question> - Ask Gemini 2.5 Pro\n\n"
        "You can also just send your question directly without any commands to use the default model (GPT-4).\n\n"
        "Additional commands:\n"
        "• /models - View all available AI models\n"
        "• /status - Check if the API is working\n"
        "• /start - Show welcome message"
    )
    
    if role == "admin":
        help_text += "\n\nAdmin commands:\n• /stats - View bot usage statistics"
    
    await update.message.reply_text(help_text)

# Function to handle the /models command
async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with all available AI models."""
    models_text = "🧠 **Available AI Models**\n\n"
    
    for cmd, model_info in AI_MODELS.items():
        models_text += f"• {model_info['name']} - Use with /{cmd} command\n"
    
    models_text += "\nSimply type your question without a command to use the default model (GPT-4)."
    
    await update.message.reply_text(models_text)

# Function to handle the /stats command (admin only)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage statistics (admin only)"""
    user_id = update.message.from_user.id
    
    if get_user_role(user_id) != "admin":
        await update.message.reply_text("⚠️ You don't have permission to use this command.")
        return
    
    # Calculate some statistics
    num_users = len(user_usage_counts)
    current_date = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    today_requests = daily_usage.get(current_date, 0)
    
    stats = f"📊 **Bot Usage Statistics**\n\n"
    stats += f"Total requests: {total_requests}\n"
    stats += f"Unique users: {num_users}\n"
    stats += f"Requests today: {today_requests}\n\n"
    
    stats += "**Model Usage:**\n"
    for model_id, count in sorted(model_usage_counts.items(), key=lambda x: x[1], reverse=True):
        model_name = next((m["name"] for cmd, m in AI_MODELS.items() if m["id"] == model_id), model_id)
        percentage = (count / total_requests) * 100 if total_requests > 0 else 0
        stats += f"• {model_name}: {count} ({percentage:.1f}%)\n"
    
    stats += "\n**Top Users:**\n"
    top_users = sorted(user_usage_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for user_id, count in top_users:
        user_role = get_user_role(user_id)
        stats += f"• User {user_id} ({user_role}): {count} requests\n"
    
    await update.message.reply_text(stats)

# Generic function to ask AI models
async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, model_id: str, model_name: str) -> None:
    """Generic function to ask any AI model."""
    # Get user ID for rate limiting
    user_id = update.message.from_user.id
    
    # Check rate limit
    if is_rate_limited(user_id):
        role = get_user_role(user_id)
        limit = get_user_rate_limit(user_id)
        await update.message.reply_text(
            f"⚠️ Rate limit reached ({limit} requests per minute for {role} users).\n"
            f"Please wait a moment before trying again."
        )
        return
    
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Fix for the command attribute issue
    if not hasattr(context, 'command'):
        context.command = update.message.text.split()[0].lstrip('/')
    
    if not context.args:
        await update.message.reply_text(
            f"Please provide a question. Usage: /{context.command} <your question>"
        )
        return

    # Combine the arguments into a single prompt
    prompt = " ".join(context.args)
    
    # Log the incoming question and model choice
    username = update.message.from_user.username or f"user_{user_id}"
    logger.info(f"Question from {username} using {model_name}: {prompt}")
    
    # Record usage for analytics
    record_usage(user_id, model_id)

    # Prepare the payload for the API
    payload = {
        "prompt": prompt,
        "model_id": model_id
    }

    try:
        # Send the request to the API
        response = requests.post(SAMURAI_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        # Log the complete API response for debugging
        logger.info(f"Complete API Response: {json.dumps(response_data)}")

        # Create a formatted response with the model name
        header = f"🤖 **{model_name}:**\n\n"
        
        # FIXED RESPONSE HANDLING: For this specific API that puts responses in the error field
        # when success is false
        if "success" in response_data and response_data["success"] is False and "error" in response_data:
            # This is actually a successful response in the error field
            await update.message.reply_text(header + response_data["error"])
        elif "response" in response_data:
            await update.message.reply_text(header + response_data["response"])
        elif "output" in response_data:
            await update.message.reply_text(header + response_data["output"])
        elif "error" in response_data and response_data.get("success") is True:
            # This is a true error case
            await update.message.reply_text(f"⚠️ Error from {model_name}: {response_data['error']}")
        else:
            # If we can't find a standard response field, try to extract text from any field that might contain the response
            for key, value in response_data.items():
                if isinstance(value, str) and len(value) > 20:  # Likely a response if it's a longer string
                    await update.message.reply_text(header + value)
                    return
                    
            # If all else fails, send the raw data
            await update.message.reply_text(
                f"Received an unexpected response format from {model_name}. Here's the raw data:\n\n"
                f"{json.dumps(response_data, indent=2)}"
            )
            
    except requests.exceptions.Timeout:
        logger.error(f"Request to {model_name} timed out.")
        await update.message.reply_text(f"⏱️ The request to {model_name} timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        logger.error(f"API error with {model_name}: {e}")
        await update.message.reply_text(f"⚠️ Error with {model_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error with {model_name}: {e}")
        await update.message.reply_text(f"❌ An unexpected error occurred with {model_name}. Please try again.")

# Model-specific command handlers
async def claude_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /claude command to ask Claude Sonnet 4."""
    context.command = "claude"
    await ask_ai(update, context, AI_MODELS["claude"]["id"], AI_MODELS["claude"]["name"])

async def opus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /opus command to ask Claude Opus 4."""
    context.command = "opus"
    await ask_ai(update, context, AI_MODELS["opus"]["id"], AI_MODELS["opus"]["name"])

async def gpt4_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gpt4 command to ask GPT-4."""
    context.command = "gpt4"
    await ask_ai(update, context, AI_MODELS["gpt4"]["id"], AI_MODELS["gpt4"]["name"])

async def gpt45_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gpt45 command to ask GPT-4.5 Preview."""
    context.command = "gpt45"
    await ask_ai(update, context, AI_MODELS["gpt45"]["id"], AI_MODELS["gpt45"]["name"])

async def o1pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /o1pro command to ask o1-pro."""
    context.command = "o1pro"
    await ask_ai(update, context, AI_MODELS["o1pro"]["id"], AI_MODELS["o1pro"]["name"])

async def gemini_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gemini command to ask Gemini Pro."""
    context.command = "gemini"
    await ask_ai(update, context, AI_MODELS["gemini"]["id"], AI_MODELS["gemini"]["name"])

async def gemini25_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gemini25 command to ask Gemini 2.5 Pro."""
    context.command = "gemini25"
    await ask_ai(update, context, AI_MODELS["gemini25"]["id"], AI_MODELS["gemini25"]["name"])

# Function to check API status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the API is working."""
    await update.message.chat.send_action(action="typing")
    
    try:
        # Use a simple prompt to test API connectivity
        payload = {
            "prompt": "Hello, are you working?",
            "model_id": DEFAULT_MODEL,
        }
        
        start_time = time.time()
        response = requests.post(SAMURAI_API_URL, json=payload, timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            await update.message.reply_text(
                f"✅ Provider 2 API is working properly!\n"
                f"Response time: {response_time:.2f} seconds\n"
                f"Default model: GPT-4"
            )
        else:
            await update.message.reply_text(
                f"⚠️ API returned status code {response.status_code}\n"
                f"Response time: {response_time:.2f} seconds"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ API check failed: {str(e)}")

# Handle direct messages (no command)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle normal messages with the default model."""
    if update.message and update.message.text:
        # Set the command for logging purposes
        context.command = "direct_message"
        # Create a context with message text as args
        context.args = update.message.text.split()
        await ask_ai(update, context, DEFAULT_MODEL, "GPT-4 (Default)")

# Error handler function
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors caused by updates."""
    logger.warning(f"Update {update} caused error {context.error}")
    
    # Check if the error is related to network or polling
    if "Conflict" in str(context.error):
        logger.error("Polling conflict detected. This might indicate multiple bot instances running.")
    elif "NetworkError" in str(context.error):
        logger.error("Network error occurred. Will retry on next update.")
    elif "AttributeError" in str(context.error) and "'CallbackContext' object has no attribute 'command'" in str(context.error):
        # This is a specific error we're handling now
        if update and hasattr(update, 'message'):
            await update.message.reply_text(
                "Please provide a question with your command. For example:\n"
                f"/{update.message.text.split()[0][1:]} What is the capital of France?"
            )
    
    # For serious errors, you might want to notify an admin
    admin_id = os.environ.get("ADMIN_CHAT_ID")
    if admin_id:
        error_message = f"⚠️ Bot Error: {type(context.error).__name__}: {context.error}"
        try:
            await context.bot.send_message(chat_id=admin_id, text=error_message)
        except Exception as send_error:
            logger.error(f"Failed to notify admin: {send_error}")

# Set up bot commands
async def post_init(application) -> None:
    """Set up bot commands after initialization."""
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("models", "View all available AI models"),
        BotCommand("claude", "Ask Claude Sonnet 4"),
        BotCommand("opus", "Ask Claude Opus 4"),
        BotCommand("gpt4", "Ask GPT-4"),
        BotCommand("gpt45", "Ask GPT-4.5 Preview"),
        BotCommand("o1pro", "Ask OpenAI o1-pro"),
        BotCommand("gemini", "Ask Google Gemini Pro"),
        BotCommand("gemini25", "Ask Gemini 2.5 Pro"),
        BotCommand("status", "Check API status")
    ])

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)

# Main function to set up the bot
def main():
    """Main function to initialize and run the Telegram bot."""
    # Get the bot token from environment variable
    bot_token = os.environ.get("BOT_TOKEN")
    
    # Set the admin user ID if provided
    admin_id = os.environ.get("ADMIN_CHAT_ID")
    if admin_id and admin_id.isdigit():
        admin_id = int(admin_id)
        user_roles[admin_id] = "admin"
        logger.info(f"Added user {admin_id} as admin")
    
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create the application with enhanced settings
        application = (
            ApplicationBuilder()
            .token(bot_token)
            .post_init(post_init)
            .concurrent_updates(True)
            .build()
        )

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("models", models_command))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Add model-specific command handlers
        application.add_handler(CommandHandler("claude", claude_command))
        application.add_handler(CommandHandler("opus", opus_command))
        application.add_handler(CommandHandler("gpt4", gpt4_command))
        application.add_handler(CommandHandler("gpt45", gpt45_command))
        application.add_handler(CommandHandler("o1pro", o1pro_command))
        application.add_handler(CommandHandler("gemini", gemini_command))
        application.add_handler(CommandHandler("gemini25", gemini25_command))
        
        # Add message handler for direct messages (without commands)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Start the bot with improved polling parameters
        logger.info("Starting Multi-AI Assistant Bot with rate limiting...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            read_timeout=7,
            write_timeout=7,
            pool_timeout=7,
            connect_timeout=7
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
