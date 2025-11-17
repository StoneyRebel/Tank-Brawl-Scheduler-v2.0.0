#!/bin/bash
echo "🎮 Starting Tank Brawl Match Scheduler..."

# Activate virtual environment
source bot_env/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please configure your bot token"
    exit 1
fi

# Run the bot
python main.py
