# utils/config.py - Configuration constants and settings

# Event configuration
MAX_CREWS_PER_TEAM = 4
DEFAULT_EVENT_DURATION_HOURS = 2
REMINDER_TIMES = [60, 30, 10]  # Minutes before event

# Role configuration
ADMIN_ROLES = ["Moderator", "Admin", "Event Organizer", "Staff"]
REQUIRED_ROLES = ["Verified Member"]

# Event types and their configurations
EVENT_TYPES = {
    "saturday_brawl": {
        "name": "Saturday Brawl",
        "emoji": "⚔️",
        "default_title": "Saturday Tank Brawl",
        "default_description": "**Victory Condition:** Team with the most time on the middle cap wins.\n**Format:** 6v6 Crew Battles",
        "role_prefix": "SAT",
        "color": 0xFF0000  # Red
    },
    "sunday_ops": {
        "name": "Sunday Operations",
        "emoji": "🎯",
        "default_title": "Sunday Armor Operations",
        "default_description": "**Mission Type:** Combined Arms Operations\n**Format:** Tactical Gameplay",
        "role_prefix": "SUN",
        "color": 0x0099FF  # Blue
    },
    "training": {
        "name": "Training Event",
        "emoji": "🎓",
        "default_title": "Armor Training Session",
        "default_description": "**Focus:** Skill Development & Practice\n**Format:** Training Exercises",
        "role_prefix": "TRN",
        "color": 0x00FF00  # Green
    },
    "tournament": {
        "name": "Tournament",
        "emoji": "🏆",
        "default_title": "Armor Tournament",
        "default_description": "**Format:** Competitive Bracket\n**Stakes:** Championship Event",
        "role_prefix": "TOUR",
        "color": 0xFFD700  # Gold
    },
    "custom": {
        "name": "Custom Event",
        "emoji": "⚔️",
        "default_title": "Custom Armor Event",
        "default_description": "**Format:** Custom Event\n**Details:** TBD",
        "role_prefix": "CUSTOM",
        "color": 0x800080  # Purple
    }
}

# Database configuration
DATABASE_CLEANUP_DAYS = 90  # Days to keep completed events
BACKUP_INTERVAL_HOURS = 24  # Hours between database backups

# Bot configuration
BOT_PREFIX = "!"
BOT_DESCRIPTION = "Tank Brawl Scheduler Bot"
BOT_VERSION = "2.0.0"

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Feature flags
FEATURES = {
    "recruitment_system": True,
    "persistent_crews": True,
    "tournament_brackets": True,
    "elo_system": True,
    "auto_reminders": True,
    "statistics_tracking": True,
    "role_management": True,
    "multi_guild_support": True
}

# Embed colors
COLORS = {
    "success": 0x00FF00,
    "error": 0xFF0000,
    "warning": 0xFFFF00,
    "info": 0x0099FF,
    "neutral": 0x808080
}

# Emoji constants
EMOJIS = {
    "allies": "🗾",
    "axis": "🔵",
    "solo": "🟨",
    "spectator": "👁️",
    "commander": "👑",
    "gunner": "🎯",
    "driver": "🚗",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "loading": "⏳",
    "edit": "✏️",
    "recruit": "🎯",
    "leave": "❌",
    "stats": "📊",
    "calendar": "📅",
    "clock": "🕐"
}

# Message limits
MAX_EMBED_FIELDS = 25
MAX_EMBED_FIELD_VALUE = 1024
MAX_EMBED_DESCRIPTION = 4096
MAX_MESSAGE_LENGTH = 2000

# Timeout values (in seconds)
TIMEOUTS = {
    "modal": 300,
    "view": 300,
    "recruitment_offer": 300,
    "admin_controls": 600
}

# Default guild settings
DEFAULT_GUILD_SETTINGS = {
    "admin_roles": ADMIN_ROLES,
    "event_channels": [],
    "reminder_times": REMINDER_TIMES,
    "default_event_duration": DEFAULT_EVENT_DURATION_HOURS * 60,
    "auto_role_assignment": True,
    "recruitment_enabled": True,
    "auto_map_votes": True,  # Auto-create map votes for events
    "map_vote_buffer_minutes": 60,  # Minutes before event to end map vote
    "max_crews_per_team": MAX_CREWS_PER_TEAM,
    "require_verification": True
}
