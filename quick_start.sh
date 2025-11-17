#!/bin/bash

# Tank Brawl Scheduler - Quick Start Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "================================================================"
echo "  🎮 Tank Brawl Scheduler - Quick Start"
echo "================================================================"
echo

print_status "Setting up Python virtual environment..."
python3 -m venv bot_env
source bot_env/bin/activate
print_success "Virtual environment created and activated"

print_status "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies installed"

print_status "Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "Created .env file"
else
    print_warning ".env file already exists"
fi

echo
echo "🔑 Setup your Discord bot token:"
echo "1. Go to https://discord.com/developers/applications"
echo "2. Create application → Bot → Copy token"
echo "3. Edit .env file and replace 'your_bot_token_here' with your token"
echo
echo "🚀 Start the bot with: ./start_bot.sh"
echo "📖 See README.md for detailed setup instructions"
