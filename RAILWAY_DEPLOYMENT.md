# Railway Deployment Guide

Complete guide to deploy Tank Brawl Scheduler on Railway.

---

## Prerequisites

Before deploying, you need:
1. A GitHub account
2. A Discord bot token (see Step 1 below)

---

## Step 1: Create Your Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** and give it a name (e.g., "Tank Brawl Scheduler")
3. Go to the **"Bot"** section in the left sidebar
4. Click **"Add Bot"** and confirm
5. Under the bot's username, click **"Reset Token"** and copy your bot token
   - **IMPORTANT:** Save this token somewhere safe - you'll need it for Railway
6. Scroll down and enable these **Privileged Gateway Intents**:
   - Server Members Intent
   - Message Content Intent
7. Go to **"OAuth2" > "URL Generator"** in the left sidebar
8. Select these scopes:
   - `bot`
   - `applications.commands`
9. Select these bot permissions:
   - Manage Roles
   - Send Messages
   - Use Slash Commands
   - Read Message History
   - Embed Links
   - Attach Files
   - Add Reactions
10. Copy the generated URL at the bottom and open it in your browser to invite the bot to your server

---

## Step 2: Fork the Repository on GitHub

1. Go to the Tank Brawl Scheduler repository on GitHub
2. Click the **"Fork"** button in the top-right corner
3. This creates your own copy of the repository

---

## Step 3: Deploy to Railway

1. Go to [Railway.app](https://railway.app) and sign in with your GitHub account
2. Click **"New Project"** (or "Start a New Project")
3. Select **"Deploy from GitHub repo"**
4. Find and select your forked **Tank-Brawl-Scheduler** repository
5. Railway will automatically detect the project settings

---

## Step 4: Add Environment Variables

1. In your Railway project, click on your service
2. Go to the **"Variables"** tab
3. Click **"+ New Variable"** and add:

| Variable Name | Value |
|---------------|-------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token from Step 1 |
| `LOG_LEVEL` | `INFO` (optional, for logging) |

---

## Step 5: Add Persistent Storage (Important!)

The bot uses a SQLite database that needs to persist between deployments:

1. In your Railway project, click **"+ New"**
2. Select **"Volume"**
3. Set the mount path to: `/app/data`
4. Click **"Add"**

This ensures your database and settings are saved even when Railway redeploys.

---

## Step 6: Deploy

1. Railway should automatically deploy after adding variables
2. If not, go to **"Deployments"** tab and click **"Deploy"**
3. Wait for the deployment to complete (usually 1-2 minutes)
4. Check the **"Logs"** tab to confirm the bot started successfully

You should see:
```
Tank Battle Scheduler#XXXX has connected to Discord!
Tank Brawl Scheduler is active in X guilds
```

---

## Step 7: Verify the Bot Works

1. Go to your Discord server where you invited the bot
2. Type `/` and you should see the bot's slash commands
3. Try `/settings` to configure the bot for your server

---

## Updating the Bot

When you want to update with new code:

1. Push changes to your GitHub repository
2. Railway automatically redeploys

Or manually:
1. Go to Railway dashboard
2. Click **"Deployments"** > **"Deploy"**

---

## Troubleshooting

### Bot not responding to commands
- Check the Railway logs for errors
- Verify `DISCORD_BOT_TOKEN` is set correctly
- Make sure the bot has proper permissions in Discord

### Database errors
- Ensure the volume is mounted at `/app/data`
- Check that the volume is attached to your service

### Bot goes offline
- Railway free tier has usage limits
- Consider upgrading to a paid plan for 24/7 uptime

### Commands not showing up
- Wait a few minutes for Discord to sync commands
- Try kicking and re-inviting the bot

---

## Railway Configuration Files

The repository includes these files for Railway:

- `Procfile` - Tells Railway how to start the bot
- `requirements.txt` - Python dependencies
- `railway.json` - Railway-specific settings

---

## Support

- Check `data/logs/bot.log` in Railway for detailed error logs
- Open a GitHub issue with error details
- Review the main README.md for usage instructions
