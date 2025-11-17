#!/usr/bin/env python3
"""
Tank Brawl Scheduler Setup Script
This script helps you set up the bot with minimal configuration.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_header():
    print("=" * 60)
    print("  Tank Brawl Scheduler Setup")
    print("=" * 60)
    print()

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def create_directories():
    """Create necessary directories"""
    directories = ["data", "data/logs"]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def setup_virtual_environment():
    """Set up Python virtual environment"""
    venv_path = Path("bot_env")
    
    if venv_path.exists():
        print("⚠️  Virtual environment already exists")
        return True
    
    try:
        print("🔄 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "bot_env"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to create virtual environment")
        return False

def install_dependencies():
    """Install required Python packages"""
    try:
        # Determine the correct pip path
        if os.name == 'nt':  # Windows
            pip_path = Path("bot_env/Scripts/pip")
        else:  # macOS/Linux
            pip_path = Path("bot_env/bin/pip")
        
        print("🔄 Installing dependencies...")
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def setup_environment_file():
    """Set up the .env file"""
    if Path(".env").exists():
        print("⚠️  .env file already exists")
        overwrite = input("   Do you want to overwrite it? (y/n): ").lower()
        if overwrite != 'y':
            return True
    
    if not Path(".env.example").exists():
        print("❌ .env.example file not found")
        return False
    
    # Copy .env.example to .env
    shutil.copy(".env.example", ".env")
    print("✅ Created .env file from template")
    
    # Get bot token from user
    print()
    print("🔑 Discord Bot Token Setup")
    print("   Go to https://discord.com/developers/applications")
    print("   1. Create a new application")
    print("   2. Go to 'Bot' section")
    print("   3. Click 'Add Bot'")
    print("   4. Copy the token")
    print()
    
    token = input("   Enter your bot token (or press Enter to skip): ").strip()
    
    if token:
        # Update .env file with the token
        with open(".env", "r") as f:
            content = f.read()
        
        content = content.replace("your_bot_token_here", token)
        
        with open(".env", "w") as f:
            f.write(content)
        
        print("✅ Bot token configured")
    else:
        print("⚠️  Bot token not configured - you'll need to edit .env manually")
    
    return True

def create_run_script():
    """Create platform-specific run scripts"""
    
    # Unix shell script
    with open("start_bot.sh", "w") as f:
        f.write("""#!/bin/bash
echo "🎮 Starting Tank Brawl Scheduler..."
echo

# Check if virtual environment exists
if [ ! -d "bot_env" ]; then
    echo "❌ Virtual environment not found! Run python3 setup.py first"
    exit 1
fi

# Activate virtual environment
source bot_env/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please configure your bot token"
    exit 1
fi

# Run the bot
python main.py
""")
    
    # Make shell script executable
    os.chmod("start_bot.sh", 0o755)
    
    print("✅ Created start_bot.sh script")

def print_completion_message():
    """Print setup completion message with next steps"""
    print()
    print("=" * 60)
    print("  🎉 Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Edit .env file and add your Discord bot token (if not done)")
    print("2. Invite the bot to your Discord server with admin permissions")
    print("3. Run the bot:")
    print()
    print("   ./start_bot.sh")
    print("   Or manually: source bot_env/bin/activate && python main.py")
    print()
    print("📖 For detailed instructions, see README.md")
    print("🐛 For help, visit: https://github.com/yourusername/tank-brawl-scheduler")
    print()

def main():
    """Main setup function"""
    print_header()
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Create necessary directories
    create_directories()
    
    # Set up virtual environment
    if not setup_virtual_environment():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Set up environment file
    if not setup_environment_file():
        return 1
    
    # Create run scripts
    create_run_script()
    
    # Print completion message
    print_completion_message()
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
