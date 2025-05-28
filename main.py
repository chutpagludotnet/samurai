import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Enable logging
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
    await update.message.reply_text(
        "Hello! I am your AI-powered bot. Use /ask <your question> to interact with me."
    )

# Function to handle the /ask command
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /ask command by sending the user's question to the Samurai API."""
    if not context.args:
        await update.message.reply_text(
            "Please provide a question. Usage: /ask <your question>"
        )
        return

    # Combine the arguments into a single prompt
    prompt = " ".join(context.args)

    # Prepare the payload for the Samurai API
    payload = {
        "prompt": prompt,
        "model_id": "openai/gpt-4",  # You can change the model here
    }

    try:
        # Send the request to the Samurai API
        response = requests.post(SAMURAI_API_URL, json=payload, timeout=10)
        response.raise_for_status()  # Raise an error for HTTP issues
        response_data = response.json()

        # Check if the API call was successful
        if response_data.get("success"):
            ai_response = response_data.get("response", "No response received.")
            await update.message.reply_text(ai_response)
        else:
            error_message = response_data.get("error", "Unknown error occurred.")
            await update.message.reply_text(f"API Error: {error_message}")
    except requests.exceptions.Timeout:
        logger.error("The request to the Samurai API timed out.")
        await update.message.reply_text("The request timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while calling the Samurai API: {e}")
        await update.message.reply_text("An error occurred while processing your request.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again.")

# Main function to set up the bot
def main():
    """Main function to initialize and run the Telegram bot."""
    # Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your bot's API token
    bot_token = "YOUR_TELEGRAM_BOT_TOKEN"

    # Create the application
    application = ApplicationBuilder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ask", ask))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
