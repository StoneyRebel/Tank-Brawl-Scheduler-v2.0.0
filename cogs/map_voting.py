# Enhanced map_voting.py with persistent storage and 7-day duration
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sqlite3

logger = logging.getLogger(__name__)

# Map options for Hell Let Loose
MAP_OPTIONS = [
    {"label": "Foy Warfare", "value": "foy_warfare", "emoji": "❄️"},
    {"label": "Omaha Warfare", "value": "omaha_warfare", "emoji": "🏖️"},
    {"label": "Utah Warfare", "value": "utah_warfare", "emoji": "🌊"},
    {"label": "Stalingrad Warfare", "value": "stalingrad_warfare", "emoji": "🏭"},
    {"label": "Kursk Warfare", "value": "kursk_warfare", "emoji": "🌾"},
    {"label": "Carentan Warfare", "value": "carentan_warfare", "emoji": "🏘️"},
    {"label": "Sainte-Mère-Église Warfare", "value": "sme_warfare", "emoji": "⛪"},
    {"label": "Hill 400 Warfare", "value": "hill400_warfare", "emoji": "⛰️"},
    {"label": "Remagen Warfare", "value": "remagen_warfare", "emoji": "🌉"},
    {"label": "El Alamein Warfare", "value": "elalamein_warfare", "emoji": "🏜️"},
    {"label": "Kharkov Warfare", "value": "kharkov_warfare", "emoji": "🏙️"},
    {"label": "Hurtgen Forest Warfare", "value": "hurtgen_warfare", "emoji": "🌲"},
    {"label": "Purple Heart Lane Warfare", "value": "phl_warfare", "emoji": "💜"},
    {"label": "Saint-Marie-du-Mont Warfare", "value": "smdm_warfare", "emoji": "🏔️"},
    {"label": "Driel Warfare", "value": "driel_warfare", "emoji": "🌾"},
    {"label": "Elsenborn Ridge Warfare", "value": "elsenborn_warfare", "emoji": "⛰️"},
    {"label": "Mortain Warfare", "value": "mortain_warfare", "emoji": "🌄"},
    {"label": "Tobruk Warfare", "value": "tobruk_warfare", "emoji": "🏛️"}
]

MAX_DURATION_HOURS = 168  # 7 days max - INCREASED FROM 48 HOURS
VOTE_DATA_FILE = "data/active_votes.json"
UPDATE_INTERVALS = {
    'immediate': 30,   # Update every 30 seconds for votes ending in < 5 minutes
    'frequent': 30,    # Update every 30 seconds for votes ending in < 1 hour  
    'normal': 30,      # Update every 30 seconds for votes ending in < 6 hours
    'slow': 30,        # Update every 30 seconds for votes ending in < 24 hours
    'daily': 300       # Update every 5 minutes for votes ending in > 24 hours
}

# Configuration
ADMIN_ROLES = ["Moderator", "Admin", "Event Organizer"]
COLORS = {
    "success": 0x00ff00,
    "error": 0xff0000,
    "warning": 0xffff00,
    "info": 0x0099ff
}

class VoteDatabase:
    """Enhanced database class for vote persistence with better recovery"""
    
    def __init__(self, db_path='data/votes.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize vote database with enhanced schema"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Enhanced votes table with better persistence fields
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                creator_id INTEGER,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                duration_minutes INTEGER NOT NULL,
                active BOOLEAN DEFAULT 1,
                event_id INTEGER,
                auto_created BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                embed_title TEXT,
                embed_description TEXT,
                view_restored BOOLEAN DEFAULT 0
            )
        ''')

        # Individual votes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                map_choice TEXT NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vote_id) REFERENCES votes (id),
                UNIQUE(vote_id, user_id)
            )
        ''')

        # Vote history for analytics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vote_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vote_id) REFERENCES votes (id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Vote database initialized with persistence support")

    def create_vote(self, message_id: int, channel_id: int, guild_id: int, 
                   creator_id: int, start_time: datetime, end_time: datetime,
                   duration_minutes: int, event_id: int = None, auto_created: bool = False,
                   embed_title: str = None, embed_description: str = None) -> int:
        """Create a new vote record with enhanced persistence data"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO votes (message_id, channel_id, guild_id, creator_id, start_time, 
                             end_time, duration_minutes, event_id, auto_created, embed_title, embed_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, channel_id, guild_id, creator_id, start_time.isoformat(),
              end_time.isoformat(), duration_minutes, event_id, auto_created, embed_title, embed_description))
        
        vote_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return vote_id

    def update_vote_status(self, message_id: int, active: bool):
        """Update vote active status"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE votes SET active = ?, last_updated = CURRENT_TIMESTAMP 
            WHERE message_id = ?
        ''', (active, message_id))
        conn.commit()
        conn.close()

    def mark_view_restored(self, message_id: int):
        """Mark that a vote's view has been restored after bot restart"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE votes SET view_restored = 1, last_updated = CURRENT_TIMESTAMP 
            WHERE message_id = ?
        ''', (message_id,))
        conn.commit()
        conn.close()

    def cast_vote(self, message_id: int, user_id: int, map_choice: str):
        """Cast or update a user's vote"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Get vote_id
        cursor.execute('SELECT id FROM votes WHERE message_id = ?', (message_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        vote_id = result[0]
        
        # Insert or update vote
        cursor.execute('''
            INSERT OR REPLACE INTO user_votes (vote_id, user_id, map_choice, voted_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (vote_id, user_id, map_choice))
        
        conn.commit()
        conn.close()
        return True

    def get_vote_results(self, message_id: int) -> Dict[str, int]:
        """Get current vote results"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uv.map_choice, COUNT(*) as vote_count
            FROM user_votes uv
            JOIN votes v ON uv.vote_id = v.id
            WHERE v.message_id = ?
            GROUP BY uv.map_choice
            ORDER BY vote_count DESC
        ''', (message_id,))
        
        results = dict(cursor.fetchall())
        conn.close()
        return results

    def get_active_votes(self) -> List[Dict]:
        """Get all active votes for restoration after restart"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message_id, channel_id, guild_id, creator_id, start_time, end_time,
                   duration_minutes, event_id, auto_created, last_updated, embed_title, embed_description
            FROM votes 
            WHERE active = 1
        ''', )
        
        columns = ['message_id', 'channel_id', 'guild_id', 'creator_id', 'start_time', 
                  'end_time', 'duration_minutes', 'event_id', 'auto_created', 'last_updated',
                  'embed_title', 'embed_description']
        
        results = []
        for row in cursor.fetchall():
            vote_dict = dict(zip(columns, row))
            # Get vote count
            vote_dict['total_votes'] = self.get_total_votes(vote_dict['message_id'])
            results.append(vote_dict)
        
        conn.close()
        return results

    def get_total_votes(self, message_id: int) -> int:
        """Get total number of votes for a message"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*)
            FROM user_votes uv
            JOIN votes v ON uv.vote_id = v.id
            WHERE v.message_id = ?
        ''', (message_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def cleanup_expired_votes(self):
        """Clean up votes that ended more than 24 hours ago"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Mark expired votes as inactive
        cursor.execute('''
            UPDATE votes 
            SET active = 0 
            WHERE active = 1 AND datetime(end_time) < datetime('now', '-1 day')
        ''')
        
        cleaned = cursor.rowcount
        conn.commit()
        conn.close()
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired votes")

    def log_vote_action(self, message_id: int, action: str, user_id: int = None, details: str = None):
        """Log vote-related actions"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Get vote_id
        cursor.execute('SELECT id FROM votes WHERE message_id = ?', (message_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return
        
        vote_id = result[0]
        
        cursor.execute('''
            INSERT INTO vote_history (vote_id, action, user_id, details)
            VALUES (?, ?, ?, ?)
        ''', (vote_id, action, user_id, details))
        
        conn.commit()
        conn.close()

class MapVoting(commands.Cog):
    """Enhanced map voting system with 7-day persistence and restart recovery"""
    
    def __init__(self, bot):
        self.bot = bot
        self.vote_db = VoteDatabase()
        self.active_votes = {}
        
        # Track update intervals to optimize performance
        self.last_update_times = {}
        
        # Track restoration status
        self.restoration_complete = False
        
        logger.info("Enhanced Map Voting cog initialized with 7-day persistence")

    async def cog_load(self):
        """Called when cog is loaded"""
        # Load active votes from database first
        await self.restore_active_votes()
        
        # Start the update task with dynamic intervals
        if not self.dynamic_update_task.is_running():
            self.dynamic_update_task.start()
            logger.info("Started dynamic map vote update task")

        # Start cleanup task
        if not self.cleanup_task.is_running():
            self.cleanup_task.start()
            logger.info("Started vote cleanup task")

    async def cog_unload(self):
        """Called when cog is unloaded"""
        self.dynamic_update_task.cancel()
        self.cleanup_task.cancel()

    async def restore_active_votes(self):
        """Restore active votes from database after bot restart"""
        try:
            active_votes = self.vote_db.get_active_votes()
            restored_count = 0
            
            for vote in active_votes:
                message_id = str(vote['message_id'])
                end_time = datetime.fromisoformat(vote['end_time'])
                
                # Skip votes that have already ended
                if datetime.utcnow() >= end_time:
                    self.vote_db.update_vote_status(vote['message_id'], False)
                    continue
                
                # Try to restore the message and view
                try:
                    channel = self.bot.get_channel(vote['channel_id'])
                    if channel:
                        try:
                            message = await channel.fetch_message(vote['message_id'])
                            
                            # Restore the view to the message
                            view = MapVoteView()
                            await message.edit(view=view)
                            
                            # Mark as restored
                            self.vote_db.mark_view_restored(vote['message_id'])
                            restored_count += 1
                            
                            logger.info(f"Restored vote message {message_id} in #{channel.name}")
                            
                        except discord.NotFound:
                            # Message was deleted, mark vote as inactive
                            self.vote_db.update_vote_status(vote['message_id'], False)
                            logger.warning(f"Vote message {message_id} not found, marking inactive")
                            continue
                        except discord.Forbidden:
                            logger.warning(f"No permission to edit vote message {message_id}")
                            
                except Exception as e:
                    logger.error(f"Error restoring vote {message_id}: {e}")
                    continue
                
                # Convert to format expected by existing code
                self.active_votes[message_id] = {
                    'message_id': vote['message_id'],
                    'channel_id': vote['channel_id'],
                    'guild_id': vote['guild_id'],
                    'creator_id': vote['creator_id'],
                    'end_time': vote['end_time'],
                    'active': True,
                    'event_id': vote['event_id'],
                    'duration_minutes': vote['duration_minutes'],
                    'auto_created': vote['auto_created'],
                    'votes': self.vote_db.get_vote_results(vote['message_id'])
                }
                
                # Initialize update tracking
                self.last_update_times[message_id] = datetime.utcnow()
            
            logger.info(f"Restored {restored_count} active votes from database")
            self.restoration_complete = True
            
        except Exception as e:
            logger.error(f"Error restoring active votes: {e}")
            self.restoration_complete = True

    def get_update_interval(self, end_time: datetime) -> int:
        """Get appropriate update interval based on time remaining"""
        remaining = end_time - datetime.utcnow()
        remaining_seconds = remaining.total_seconds()
        
        if remaining_seconds <= 0:
            return UPDATE_INTERVALS['immediate']
        elif remaining_seconds < 300:  # < 5 minutes
            return UPDATE_INTERVALS['immediate']
        elif remaining_seconds < 3600:  # < 1 hour
            return UPDATE_INTERVALS['frequent']
        elif remaining_seconds < 21600:  # < 6 hours
            return UPDATE_INTERVALS['normal']
        elif remaining_seconds < 86400:  # < 24 hours
            return UPDATE_INTERVALS['slow']
        else:  # > 24 hours
            return UPDATE_INTERVALS['daily']

    def should_update_vote(self, message_id: str, end_time: datetime) -> bool:
        """Determine if a vote should be updated based on its interval"""
        last_update = self.last_update_times.get(message_id, datetime.min)
        interval = self.get_update_interval(end_time)
        
        return (datetime.utcnow() - last_update).total_seconds() >= interval

    @app_commands.command(name="mapvote")
    @app_commands.describe(
        days="Days (0-7)", 
        hours="Hours (0-23)", 
        minutes="Minutes (0-59)",
        event_id="Link to a specific armor event (optional)"
    )
    async def mapvote(self, interaction: discord.Interaction, days: int = 0, hours: int = 0, 
                     minutes: int = 0, event_id: int = None):
        """Start a map vote. Duration in days, hours, and minutes. Max 7 days."""
        
        # Calculate total duration
        total_minutes = (days * 24 * 60) + (hours * 60) + minutes
        max_minutes = MAX_DURATION_HOURS * 60  # 7 days in minutes
        
        # If no duration specified, default to 7 days
        if total_minutes == 0:
            total_minutes = max_minutes  # Default to full 7 days
        
        if total_minutes < 1 or total_minutes > max_minutes:
            await interaction.response.send_message(
                f"❌ Please enter a duration between 1 minute and {MAX_DURATION_HOURS} hours (7 days).",
                ephemeral=True
            )
            return
        
        # Create the vote
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=total_minutes)
        view = MapVoteView()
        
        # Create initial embed
        embed = self.create_vote_embed(
            message_id=0,  # Will be updated
            end_time=end_time,
            votes={},
            event_id=event_id,
            total_minutes=total_minutes,
            auto_created=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        
        # Save to database with enhanced persistence data
        vote_id = self.vote_db.create_vote(
            message_id=message.id,
            channel_id=interaction.channel.id,
            guild_id=interaction.guild.id,
            creator_id=interaction.user.id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=total_minutes,
            event_id=event_id,
            auto_created=False,
            embed_title=embed.title,
            embed_description=embed.description
        )
        
        # Add to active votes
        self.active_votes[str(message.id)] = {
            'message_id': message.id,
            'channel_id': interaction.channel.id,
            'guild_id': interaction.guild.id,
            'creator_id': interaction.user.id,
            'end_time': end_time.isoformat(),
            'active': True,
            'event_id': event_id,
            'duration_minutes': total_minutes,
            'auto_created': False,
            'votes': {}
        }
        
        # Initialize update tracking
        self.last_update_times[str(message.id)] = datetime.utcnow()
        
        # Log the action
        self.vote_db.log_vote_action(message.id, 'vote_created', interaction.user.id, 
                                   f"Duration: {total_minutes} minutes ({days}d {hours}h {minutes}m)")
        
        logger.info(f"Started {total_minutes}-minute map vote in {interaction.guild.name} - {interaction.channel.name}, ending at {end_time}")

    # THIS IS THE METHOD YOUR ARMOR_EVENTS.PY CALLS
    async def create_auto_mapvote(self, event_id: int, channel: discord.TextChannel, duration_minutes: int):
        """Create an automatic map vote for an event with proper 7-day support"""
        try:
            # Ensure duration doesn't exceed 7 days
            max_minutes = MAX_DURATION_HOURS * 60  # 7 days
            if duration_minutes > max_minutes:
                duration_minutes = max_minutes
                logger.info(f"Capped auto map vote duration to {max_minutes} minutes (7 days)")
            
            # Create the vote
            start_time = datetime.utcnow()
            end_time = start_time + timedelta(minutes=duration_minutes)
            view = MapVoteView()
            
            # Create initial embed
            embed = self.create_vote_embed(
                message_id=0,  # Will be updated
                end_time=end_time,
                votes={},
                event_id=event_id,
                total_minutes=duration_minutes,
                auto_created=True
            )
            
            # Send the message
            message = await channel.send(embed=embed, view=view)
            
            # Save to database with enhanced persistence
            vote_id = self.vote_db.create_vote(
                message_id=message.id,
                channel_id=channel.id,
                guild_id=channel.guild.id,
                creator_id=None,  # Auto-created, no specific creator
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                event_id=event_id,
                auto_created=True,
                embed_title=embed.title,
                embed_description=embed.description
            )
            
            # Add to active votes
            self.active_votes[str(message.id)] = {
                'message_id': message.id,
                'channel_id': channel.id,
                'guild_id': channel.guild.id,
                'creator_id': None,
                'end_time': end_time.isoformat(),
                'active': True,
                'event_id': event_id,
                'duration_minutes': duration_minutes,
                'auto_created': True,
                'votes': {}
            }
            
            # Initialize update tracking
            self.last_update_times[str(message.id)] = datetime.utcnow()
            
            # Log the action
            self.vote_db.log_vote_action(message.id, 'auto_vote_created', None, 
                                       f"Event: {event_id}, Duration: {duration_minutes} minutes")
            
            logger.info(f"Auto-created {duration_minutes}-minute map vote for event {event_id} in {channel.name}")
            
            return message
            
        except Exception as e:
            logger.error(f"Error creating auto map vote: {e}")
            return None

    def create_vote_embed(self, message_id: int, end_time: datetime, votes: Dict[str, int], 
                         event_id: int = None, total_minutes: int = 0, auto_created: bool = False,
                         is_ended: bool = False, event_title: str = None) -> discord.Embed:
        """Create embed for vote display with event countdown instead of vote countdown"""
        
        if is_ended:
            title = "🏁 MAP VOTE ENDED"
            color = COLORS["error"]
            footer_text = f"Vote ended • {sum(votes.values())} total votes"
        else:
            title = "🗳️ MAP VOTE IN PROGRESS"
            color = COLORS["success"]
            
            # Show event countdown instead of vote countdown if we have an event
            if event_id and auto_created:
                # Calculate event time from vote end time + 1 hour
                event_time = end_time + timedelta(hours=1)
                event_countdown = self.format_time_remaining_to_event(event_time)
                footer_text = f"⏰ Event in: {event_countdown} • {sum(votes.values())} votes"
            else:
                # Fall back to vote countdown for manual votes
                time_remaining = self.format_time_remaining(end_time)
                footer_text = f"⏰ Vote ends: {time_remaining} • {sum(votes.values())} votes"
        
        # Add event context if linked
        description = ""
        if event_id:
            event_id_display = event_title or f'Event #{event_id}'
            event_link = f"**🎯 Event:** {event_id_display}\n\n"
            description += event_link
        
        description += "🗳️ **Current Results:**\n" + self.get_vote_results_text(votes)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        # Add duration info with better formatting for long durations
        duration_text = self.format_duration(total_minutes)
        if auto_created:
            footer_text += f" • Auto-created • Duration: {duration_text}"
        else:
            footer_text += f" • Duration: {duration_text}"
        
        embed.set_footer(text=footer_text)
        
        # Add progress bar for time remaining if not ended
        if not is_ended and total_minutes > 0:
            if event_id and auto_created:
                # Show progress toward event time instead of vote end time
                event_time = end_time + timedelta(hours=1)
                total_event_duration = (event_time - (end_time - timedelta(minutes=total_minutes))).total_seconds() / 60
                elapsed_minutes = total_event_duration - ((event_time - datetime.utcnow()).total_seconds() / 60)
                progress = max(0, min(100, (elapsed_minutes / total_event_duration) * 100))
                progress_bar = self.create_progress_bar(progress)
                embed.add_field(name="⏱️ Event Progress", value=progress_bar, inline=False)
            else:
                # Original vote progress bar for manual votes
                elapsed_minutes = total_minutes - ((end_time - datetime.utcnow()).total_seconds() / 60)
                progress = max(0, min(100, (elapsed_minutes / total_minutes) * 100))
                progress_bar = self.create_progress_bar(progress)
                embed.add_field(name="⏱️ Vote Progress", value=progress_bar, inline=False)
        
        return embed

    def format_time_remaining_to_event(self, event_time: datetime) -> str:
        """Format time remaining until event starts (same format as armor events)"""
        remaining = event_time - datetime.utcnow()
        if remaining.total_seconds() <= 0:
            return "🔴 EVENT STARTED"
        
        total_seconds = int(remaining.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 and days == 0:  # Only show seconds if less than a day
            parts.append(f"{seconds}s")
        
        return " ".join(parts) if parts else "<1s"

    def create_progress_bar(self, percentage: float, length: int = 20) -> str:
        """Create a visual progress bar"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"`{bar}` {percentage:.1f}%"

    def get_vote_results_text(self, votes_dict: Dict[str, int]) -> str:
        """Convert vote results to formatted text"""
        if not votes_dict:
            return "No votes cast yet."

        sorted_results = sorted(votes_dict.items(), key=lambda x: x[1], reverse=True)

        results = []
        for i, (map_value, count) in enumerate(sorted_results):
            # Find label and emoji for this map value
            emoji = "🗺️"
            map_label = map_value  # Default to value if not found
            for map_opt in MAP_OPTIONS:
                if map_opt["value"] == map_value:
                    emoji = map_opt.get("emoji", "🗺️")
                    map_label = map_opt["label"]
                    break

            # Add winner indicator
            if i == 0 and len(sorted_results) > 1:
                results.append(f"👑 **{map_label}** {emoji} – {count} vote(s)")
            else:
                results.append(f"{emoji} **{map_label}** – {count} vote(s)")

        return "\n".join(results)

    def format_time_remaining(self, end_time: datetime) -> str:
        """Format time remaining with proper support for days"""
        remaining = end_time - datetime.utcnow()
        if remaining.total_seconds() <= 0:
            return "ENDED"
        
        total_seconds = int(remaining.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 and days == 0:  # Only show seconds if less than a day
            parts.append(f"{seconds}s")
        
        return " ".join(parts) if parts else "<1s"

    def format_duration(self, total_minutes: int) -> str:
        """Format total duration with proper day support"""
        if total_minutes < 60:
            return f"{total_minutes}m"
        elif total_minutes < 1440:  # < 24 hours
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"
        else:  # >= 24 hours
            days = total_minutes // 1440
            hours = (total_minutes % 1440) // 60
            return f"{days}d {hours}h" if hours else f"{days}d"

    @tasks.loop(seconds=30)  # Check every 30 seconds for better responsiveness
    async def dynamic_update_task(self):
        """Dynamic background task to update vote embeds and end votes"""
        if not self.restoration_complete:
            return  # Wait for restoration to complete
            
        try:
            current_time = datetime.utcnow()
            
            for message_id, vote_data in list(self.active_votes.items()):
                if not vote_data['active']:
                    continue
                
                end_time = datetime.fromisoformat(vote_data['end_time'])
                
                try:
                    # Check if vote should end
                    if current_time >= end_time:
                        await self.end_vote_automatically(message_id, vote_data)
                        continue
                    
                    # Check if we should update this vote based on its interval
                    if not self.should_update_vote(message_id, end_time):
                        continue
                    
                    channel = self.bot.get_channel(vote_data['channel_id'])
                    if not channel:
                        continue
                    
                    message = await channel.fetch_message(int(message_id))
                    if not message:
                        continue
                    
                    # Get current results from database
                    current_votes = self.vote_db.get_vote_results(int(message_id))
                    vote_data['votes'] = current_votes
                    
                    # Update the embed with current results
                    embed = self.create_vote_embed(
                        message_id=int(message_id),
                        end_time=end_time,
                        votes=current_votes,
                        event_id=vote_data.get('event_id'),
                        total_minutes=vote_data['duration_minutes'],
                        auto_created=vote_data.get('auto_created', False)
                    )
                    
                    await message.edit(embed=embed)
                    self.last_update_times[message_id] = current_time
                        
                except discord.NotFound:
                    # Message was deleted, mark as inactive
                    self.vote_db.update_vote_status(int(message_id), False)
                    self.active_votes[message_id]['active'] = False
                except Exception as e:
                    logger.error(f"Error updating vote {message_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in dynamic_update_task: {e}")

    @tasks.loop(hours=6)  # Clean up expired votes every 6 hours
    async def cleanup_task(self):
        """Clean up expired votes periodically"""
        try:
            self.vote_db.cleanup_expired_votes()
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

    async def end_vote_automatically(self, message_id: str, vote_data: Dict):
        """End a vote automatically when time expires"""
        
        # End the vote in database
        self.vote_db.update_vote_status(int(message_id), False)
        self.active_votes[message_id]['active'] = False
        
        try:
            channel = self.bot.get_channel(vote_data['channel_id'])
            message = await channel.fetch_message(int(message_id))
            
            # Get final results from database
            final_votes = self.vote_db.get_vote_results(int(message_id))
            
            # Update embed to show ended state
            embed = self.create_vote_embed(
                message_id=int(message_id),
                end_time=datetime.fromisoformat(vote_data['end_time']),
                votes=final_votes,
                event_id=vote_data.get('event_id'),
                total_minutes=vote_data['duration_minutes'],
                auto_created=vote_data.get('auto_created', False),
                is_ended=True
            )
            await message.edit(embed=embed, view=None)
            
            # Post final results
            results = self.get_vote_results_text(final_votes)
            final_message = f"🏁 **Final Map Vote Results:**\n{results}"
            
            if vote_data.get('event_id'):
                final_message += f"\n\n🎯 **For Event:** Event #{vote_data['event_id']}"
            
            await channel.send(final_message)
            
            # Log the action
            self.vote_db.log_vote_action(int(message_id), 'vote_ended_auto', None, results)
            
        except Exception as e:
            logger.error(f"Error ending vote automatically {message_id}: {e}")

    @app_commands.command(name="endvote")
    @app_commands.describe(message_id="The ID of the vote message to end")
    async def endvote(self, interaction: discord.Interaction, message_id: str):
        """Manually end an active vote"""

        if message_id not in self.active_votes or not self.active_votes[message_id]['active']:
            await interaction.response.send_message("❌ No active vote found with that message ID.", ephemeral=True)
            return

        vote_data = self.active_votes[message_id]

        # Check permissions - only creator or admins can end vote
        if (vote_data['creator_id'] != interaction.user.id and
            not any(role.name in ADMIN_ROLES for role in interaction.user.roles)):
            await interaction.response.send_message(
                "❌ You can only end votes you created, or you need admin permissions.",
                ephemeral=True
            )
            return

        # Defer to prevent timeout when fetching message
        await interaction.response.defer()

        await self.end_vote_manually(interaction, message_id, vote_data)

    async def end_vote_manually(self, interaction: discord.Interaction, message_id: str, vote_data: Dict):
        """End a vote manually"""
        
        # End the vote in database
        self.vote_db.update_vote_status(int(message_id), False)
        self.active_votes[message_id]['active'] = False
        
        try:
            channel = self.bot.get_channel(vote_data['channel_id'])
            message = await channel.fetch_message(int(message_id))
            
            # Get final results from database
            final_votes = self.vote_db.get_vote_results(int(message_id))
            
            # Update embed to show ended state
            embed = self.create_vote_embed(
                message_id=int(message_id),
                end_time=datetime.fromisoformat(vote_data['end_time']),
                votes=final_votes,
                event_id=vote_data.get('event_id'),
                total_minutes=vote_data['duration_minutes'],
                auto_created=vote_data.get('auto_created', False),
                is_ended=True
            )
            await message.edit(embed=embed, view=None)
            
            # Post final results
            results = self.get_vote_results_text(final_votes)
            await interaction.followup.send(f"🏁 **Vote Ended Manually - Final Results:**\n{results}")

            # Log the action
            self.vote_db.log_vote_action(int(message_id), 'vote_ended_manually',
                                       interaction.user.id, results)

        except Exception as e:
            await interaction.followup.send(f"❌ Error ending vote: {e}", ephemeral=True)

    @app_commands.command(name="listvotes")
    async def list_votes(self, interaction: discord.Interaction):
        """List all active votes in this guild"""
        
        guild_votes = [
            vote for vote in self.active_votes.values() 
            if vote['guild_id'] == interaction.guild.id and vote['active']
        ]
        
        if not guild_votes:
            await interaction.response.send_message("No active votes in this server.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🗳️ Active Map Votes", color=COLORS["info"])
        
        for vote in guild_votes:
            end_time = datetime.fromisoformat(vote['end_time'])
            time_remaining = self.format_time_remaining(end_time)
            
            field_value = f"**Channel:** <#{vote['channel_id']}>\n"
            field_value += f"**Time Left:** {time_remaining}\n"
            field_value += f"**Total Votes:** {sum(vote['votes'].values())}"
            
            if vote.get('event_id'):
                field_value += f"\n**Event ID:** {vote['event_id']}"
            
            embed.add_field(
                name=f"Vote ID: {vote['message_id']}",
                value=field_value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dynamic_update_task.before_loop
    async def before_dynamic_update(self):
        await self.bot.wait_until_ready()

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready"""
        logger.info("Enhanced Map Voting cog is ready with 7-day persistence")


# UI Components for Map Voting

class MapVoteView(View):
    def __init__(self):
        super().__init__(timeout=None)  # No timeout for persistent views
        self.add_item(MapVoteDropdown())

class MapVoteDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=option["label"],
                value=option["value"],
                emoji=option.get("emoji", "🗺️")
            )
            for option in MAP_OPTIONS[:25]  # Discord limit
        ]
        
        super().__init__(
            placeholder="Choose a map...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="map_vote_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        # Get the map voting cog
        cog = interaction.client.get_cog('MapVoting')
        if not cog:
            await interaction.response.send_message("❌ Map voting system not available.", ephemeral=True)
            return
        
        message_id = str(interaction.message.id)
        
        # Check if this vote is still active
        if message_id not in cog.active_votes or not cog.active_votes[message_id]['active']:
            await interaction.response.send_message("❌ This vote is no longer active.", ephemeral=True)
            return
        
        # Check if vote has ended
        end_time = datetime.fromisoformat(cog.active_votes[message_id]['end_time'])
        if datetime.utcnow() >= end_time:
            await interaction.response.send_message("❌ This vote has ended.", ephemeral=True)
            return
        
        # Cast the vote
        user_id = str(interaction.user.id)
        selected_map = self.values[0]
        
        # Update in database
        success = cog.vote_db.cast_vote(int(message_id), interaction.user.id, selected_map)
        
        if not success:
            await interaction.response.send_message("❌ Error casting vote.", ephemeral=True)
            return
        
        # Update local storage
        cog.active_votes[message_id]['votes'][user_id] = selected_map
        
        # Find the emoji and label for the selected map
        selected_emoji = "🗺️"
        selected_label = selected_map
        for opt in MAP_OPTIONS:
            if opt["value"] == selected_map:
                selected_emoji = opt.get("emoji", "🗺️")
                selected_label = opt["label"]
                break

        await interaction.response.send_message(
            f"✅ Vote registered for **{selected_label}** {selected_emoji}!",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(MapVoting(bot))
