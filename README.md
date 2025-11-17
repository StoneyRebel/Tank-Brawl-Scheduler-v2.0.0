# 🎮 Tank Brawl Scheduler Bot

A comprehensive Discord bot for managing Hell Let Loose armor events, crew formations, and tournament scheduling.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)

## ✨ Features

### 🛡️ Event Management
- **Event Scheduling** - Saturday Brawls, Sunday Ops, training sessions, tournaments
- **Team-based Signups** - Allies vs Axis crew formations (6v6)
- **Auto Role Assignment** - Team-specific Discord roles
- **Map Voting** - 7-day Hell Let Loose map voting system

### 👥 Persistent Crew System
- **Crew Management Panel** - User-friendly button interface
- **Persistent Crews** - Crews that last across events
- **One-Click Event Joining** - Crews join events together
- **Statistics Tracking** - Win/loss records

### 🎯 Smart Features
- **Recruitment Pool** - Solo players can be recruited
- **Role Integration** - Automatic Discord role assignment
- **Admin Tools** - Server configuration and management
- **Database Persistence** - All data saved automatically

## 🚀 Quick Start

### Deploy to Railway (30 seconds)
1. [![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)
2. Add your Discord bot token
3. Invite bot to server with admin permissions
4. Done!

### Local Setup
```bash
python setup.py
./start_bot.sh
```

## 🎮 Usage

### For Players
- `/crew_panel` - Manage your persistent crews
- Join events with **🔗 Join with My Crew** button
- Or join individually with team buttons

### For Admins
- `/schedule_event` - Create events
- `/settings` - Configure server
- `/crew_panel` - Create crew management panels

## 📋 Commands

**Player Commands:**
- `/crew_panel` - Crew management interface
- `/crew_info` - View crew details

**Admin Commands:**
- `/schedule_event` - Create armor events
- `/settings` - Server configuration
- `/event_roles` - Manage event roles
- `/mapvote` - Create map votes

## 🔧 Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create application → Bot → Copy token
3. Bot needs: Manage Roles, Send Messages, Use Slash Commands
4. Invite URL: `https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=268435456&scope=bot%20applications.commands`

## 🛠️ Development

```bash
git clone https://github.com/yourusername/tank-brawl-scheduler.git
cd tank-brawl-scheduler
python setup.py
```

## 📄 License
MIT License - see [LICENSE](LICENSE) file.

## 🆘 Support
- Check `data/logs/bot.log` for errors
- Open GitHub issue with error details
- Review DEPLOYMENT.md for platform-specific help

---
**Ready to organize your tank battles? Deploy now! 🚗💥**
