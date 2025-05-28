import logging
import requests
import os
import time
import json
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Enable logging with more detailed format
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Base URL for Samurai API
SAMURAI_API_URL = "https://provider2api.onrender.com/api/provider2"

# Function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the user starts the bot."""
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"Hello {user_name}! I'm your AI-powered assistant. Use /ask <your question> to interact with me.\n\n"
        f"Use /help to see all available commands."
    )

# Function to handle the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with available commands when the command /help is issued."""
    help_text = (
        "Here are the commands you can use:\n\n"
        "/start - Start the bot and get welcome message\n"
        "/ask <question> - Ask me anything\n"
        "/help - Show this help message\n"
        "/status - Check if the API is working"
    )
    await update.message.reply_text(help_text)

# Function to handle the /ask command
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /ask command by sending the user's question to the Samurai API."""
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    if not context.args:
        await update.message.reply_text(
            "Please provide a question. Usage: /ask <your question>"
        )
        return

    # Combine the arguments into a single prompt
    prompt = " ".join(context.args)
    
    # Log the incoming question
    logger.info(f"Question from {update.message.from_user.username}: {prompt}")

    # Prepare the payload for the Samurai API
    payload = {
        "prompt": prompt,
        "model_id": "openai/gpt-4",  # You can change the model here
    }

    try:
        # Send the request to the Samurai API
        response = requests.post(SAMURAI_API_URL, json=payload, timeout=30)
        response.raise_for_status()  # Raise an error for HTTP issues
        response_data = response.json()
        
        # Log the raw API response for debugging
        logger.debug(f"API Response: {json.dumps(response_data, indent=2)}")

        # Process and send the response
        if "response" in response_data:
            await update.message.reply_text(response_data["response"])
        elif "output" in response_data:
            await update.message.reply_text(response_data["output"])
        elif "error" in response_data:
            await update.message.reply_text(f"Error: {response_data['error']}")
        else:
            # Unknown response format, send the raw data
            await update.message.reply_text(
                "Received an unexpected response format. Here's the raw data:\n\n"
                f"{json.dumps(response_data, indent=2)}"
            )
            
    except requests.exceptions.Timeout:
        logger.error("The request to the Samurai API timed out.")
        await update.message.reply_text("The request timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while calling the Samurai API: {e}")
        await update.message.reply_text("An error occurred while processing your request.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again.")

# Function to check API status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the API is working."""
    await update.message.chat.send_action(action="typing")
    
    try:
        # Use a simple prompt to test API connectivity
        payload = {
            "prompt": "Hello, are you working?",
            "model_id": "openai/gpt-4",
        }
        
        start_time = time.time()
        response = requests.post(SAMURAI_API_URL, json=payload, timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            await update.message.reply_text(
                f"✅ API is working properly!\n"
                f"Response time: {response_time:.2f} seconds"
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
    """Handle normal messages by redirecting them to the ask command."""
    if update.message.text:
        # Create a context with message text as args
        context.args = update.message.text.split()
        await ask(update, context)

# Set up bot commands
async def post_init(application) -> None:
    """Set up bot commands after initialization."""
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("ask", "Ask me anything"),
        BotCommand("help", "Show available commands"),
        BotCommand("status", "Check API status")
    ])

# Main function to set up the bot
def main():
    """Main function to initialize and run the Telegram bot."""
    # Get the bot token from environment variable
    bot_token = os.environ.get("BOT_TOKEN")
    
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Set up a simple persistence mechanism to store user data
    try:
        # Create the application with enhanced settings
        application = (
            ApplicationBuilder()
            .token(bot_token)
            .post_init(post_init)
            .concurrent_updates(True)  # Allow concurrent updates for better performance
            .build()
        )

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("ask", ask))
        application.add_handler(CommandHandler("status", status))
        
        # Add message handler for direct messages (without commands)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Start the bot
        logger.info("Starting bot...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
