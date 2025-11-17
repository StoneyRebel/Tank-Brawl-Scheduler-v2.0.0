# 🚀 Deployment Guide

## Railway (Recommended)

### One-Click Deploy
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)

1. Click the deploy button
2. Connect your GitHub account
3. Set `DISCORD_BOT_TOKEN` environment variable
4. Deploy automatically!

### Manual Railway Deploy
1. Fork this repository
2. Create a Railway account at [railway.app](https://railway.app)
3. Create new project from GitHub repository
4. Add environment variables:
   - `DISCORD_BOT_TOKEN` - Your Discord bot token
   - `LOG_LEVEL` - Set to `INFO`
5. Deploy

## Other Platforms

### Heroku
```bash
heroku create your-bot-name
heroku config:set DISCORD_BOT_TOKEN=your_token_here
git push heroku master
```

### Docker
```bash
docker build -t tank-brawl-bot .
docker run -e DISCORD_BOT_TOKEN=your_token tank-brawl-bot
```

### Self-Hosting
```bash
python setup.py
./start_bot.sh
```

## Environment Variables
- `DISCORD_BOT_TOKEN` (Required) - Your Discord bot token
- `LOG_LEVEL` (Optional) - Logging level (INFO, DEBUG, WARNING, ERROR)

## Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application → Bot section → Copy token
3. Bot needs these permissions:
   - Manage Roles
   - Send Messages
   - Use Slash Commands
   - Read Message History

## Support
Check `data/logs/bot.log` for error messages
