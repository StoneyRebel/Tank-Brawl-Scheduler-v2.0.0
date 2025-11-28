# utils/database.py - Enhanced database management
import sqlite3
import datetime
import json
import logging
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

class EventDatabase:
    def __init__(self, db_path='tank_brawl.db'):
        self.db_path = db_path
        self.timeout = 30.0  # 30 second timeout for database operations
        self.init_database()

    def init_database(self):
        """Initialize all database tables"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        # Events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                creator_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                event_time TIMESTAMP,
                event_type TEXT DEFAULT 'custom',
                status TEXT DEFAULT 'Open',
                max_crews_per_team INTEGER DEFAULT 6,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Signups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                signup_type TEXT NOT NULL, -- 'commander', 'crew', 'solo', 'spectator'
                team TEXT, -- 'A', 'B', or NULL
                role TEXT, -- 'commander', 'gunner', 'driver', 'solo', 'spectator'
                crew_name TEXT,
                crew_slot INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id),
                UNIQUE(event_id, user_id)
            )
        ''')

        # Event history/audit log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
        ''')

        # User statistics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                events_participated INTEGER DEFAULT 0,
                events_commanded INTEGER DEFAULT 0,
                events_created INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                preferred_role TEXT,
                last_event TIMESTAMP,
                elo_rating INTEGER DEFAULT 1200,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Persistent crews
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS persistent_crews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                crew_name TEXT NOT NULL,
                commander_id INTEGER NOT NULL,
                gunner_id INTEGER,
                driver_id INTEGER,
                description TEXT,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, crew_name)
            )
        ''')

        # Guild settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                admin_roles TEXT, -- JSON array of role names
                event_channels TEXT, -- JSON array of allowed channel IDs
                reminder_times TEXT, -- JSON array of reminder minutes
                default_event_duration INTEGER DEFAULT 120,
                auto_role_assignment BOOLEAN DEFAULT 1,
                auto_map_votes BOOLEAN DEFAULT 1,
                recruitment_enabled BOOLEAN DEFAULT 1,
                settings_data TEXT, -- JSON for additional settings
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Ensure newer columns exist when upgrading older databases
        self._ensure_guild_setting_columns(cursor)

        # Reminders queue
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                reminder_time TIMESTAMP NOT NULL,
                reminder_type TEXT NOT NULL, -- 'before_event', 'custom'
                sent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def _ensure_guild_setting_columns(self, cursor: sqlite3.Cursor):
        """Add missing columns to guild_settings when upgrading."""
        cursor.execute("PRAGMA table_info(guild_settings)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            'auto_map_votes': 'BOOLEAN DEFAULT 1'
        }

        for column, definition in required_columns.items():
            if column not in columns:
                cursor.execute(f"ALTER TABLE guild_settings ADD COLUMN {column} {definition}")

        # Backfill defaults for newly added columns
        if 'auto_map_votes' in required_columns:
            cursor.execute("UPDATE guild_settings SET auto_map_votes = 1 WHERE auto_map_votes IS NULL")

    # Event management methods
    def create_event(self, guild_id: int, channel_id: int, creator_id: int, 
                    title: str, description: str = None, event_time: datetime.datetime = None,
                    event_type: str = "custom") -> int:
        """Create a new event and return its ID"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (guild_id, channel_id, creator_id, title, description, event_time, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, channel_id, creator_id, title, description, event_time, event_type))
        
        event_id = cursor.lastrowid

        # Update user stats
        self.update_user_stat(creator_id, guild_id, 'events_created', 1)

        conn.commit()
        conn.close()
        
        logger.info(f"Created event {event_id}: {title}")
        return event_id

    def get_event_by_id(self, event_id: int) -> Optional[Tuple]:
        """Get event data by ID"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, status, created_at, event_time, event_type
            FROM events WHERE id = ?
        ''', (event_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result

    def get_guild_events(self, guild_id: int, status: str = None, limit: int = 10) -> List[Tuple]:
        """Get events for a guild, optionally filtered by status"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT id, title, status, created_at, event_time, event_type
                FROM events 
                WHERE guild_id = ? AND status = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (guild_id, status, limit))
        else:
            cursor.execute('''
                SELECT id, title, status, created_at, event_time, event_type
                FROM events 
                WHERE guild_id = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (guild_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def update_event_message(self, event_id: int, message_id: int):
        """Update the message ID for an event"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE events SET message_id = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (message_id, event_id))
        conn.commit()
        conn.close()

    def update_event_status(self, event_id: int, status: str):
        """Update event status"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE events SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (status, event_id))
        conn.commit()
        conn.close()

    # Signup management methods
    def save_signup(self, event_id: int, user_id: int, signup_type: str, 
                   team: str = None, role: str = None, crew_name: str = None, crew_slot: int = None):
        """Save or update a user's signup"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        # Remove existing signup for this user in this event
        cursor.execute('DELETE FROM signups WHERE event_id = ? AND user_id = ?', (event_id, user_id))
        
        # Add new signup
        cursor.execute('''
            INSERT INTO signups (event_id, user_id, signup_type, team, role, crew_name, crew_slot)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (event_id, user_id, signup_type, team, role, crew_name, crew_slot))
        
        # Update user participation stats
        guild_id = self.get_event_guild_id(event_id)
        if guild_id:
            self.update_user_stat(user_id, guild_id, 'events_participated', 1)
            if role == 'commander':
                self.update_user_stat(user_id, guild_id, 'events_commanded', 1)
        
        conn.commit()
        conn.close()

    def get_event_signups(self, event_id: int) -> List[Dict]:
        """Get all signups for an event"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, signup_type, team, role, crew_name, crew_slot
            FROM signups WHERE event_id = ?
        ''', (event_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'signup_type': row[1],
                'team': row[2],
                'role': row[3],
                'crew_name': row[4],
                'crew_slot': row[5]
            }
            for row in results
        ]

    def remove_signup(self, event_id: int, user_id: int):
        """Remove a user's signup"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM signups WHERE event_id = ? AND user_id = ?', (event_id, user_id))
        conn.commit()
        conn.close()

    # Event history/logging methods
    def log_event_action(self, event_id: int, action: str, user_id: int = None, details: str = None):
        """Log an action for audit trail"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO event_history (event_id, action, user_id, details)
            VALUES (?, ?, ?, ?)
        ''', (event_id, action, user_id, details))
        conn.commit()
        conn.close()

    def get_event_history(self, event_id: int, limit: int = 20) -> List[Tuple]:
        """Get recent history for an event"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action, user_id, details, timestamp 
            FROM event_history 
            WHERE event_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (event_id, limit))
        results = cursor.fetchall()
        conn.close()
        return results

    # User statistics methods
    def get_user_stats(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get user statistics"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT events_participated, events_commanded, events_created, 
                   total_wins, total_losses, preferred_role, elo_rating
            FROM user_stats 
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'events_participated': result[0],
                'events_commanded': result[1],
                'events_created': result[2],
                'total_wins': result[3],
                'total_losses': result[4],
                'preferred_role': result[5],
                'elo_rating': result[6]
            }
        return None

    def update_user_stat(self, user_id: int, guild_id: int, stat_name: str, value: int):
        """Update a user statistic"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        # Insert or update user stats
        cursor.execute('''
            INSERT INTO user_stats (user_id, guild_id, {}) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                {} = {} + ?,
                updated_at = CURRENT_TIMESTAMP
        '''.format(stat_name, stat_name, stat_name), (user_id, guild_id, value, value))
        
        conn.commit()
        conn.close()

    def get_leaderboard(self, guild_id: int, stat_type: str = 'events_participated', limit: int = 10) -> List[Tuple]:
        """Get leaderboard for a specific statistic"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        valid_stats = ['events_participated', 'events_commanded', 'events_created', 'elo_rating']
        if stat_type not in valid_stats:
            stat_type = 'events_participated'
        
        cursor.execute(f'''
            SELECT user_id, {stat_type}
            FROM user_stats 
            WHERE guild_id = ? AND {stat_type} > 0
            ORDER BY {stat_type} DESC 
            LIMIT ?
        ''', (guild_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results

    # Persistent crew methods
    def create_persistent_crew(self, guild_id: int, crew_name: str, commander_id: int, 
                             gunner_id: int = None, driver_id: int = None, description: str = None) -> int:
        """Create a persistent crew"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO persistent_crews (guild_id, crew_name, commander_id, gunner_id, driver_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, crew_name, commander_id, gunner_id, driver_id, description))
            
            crew_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Created persistent crew {crew_id}: {crew_name}")
            return crew_id
            
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Crew name '{crew_name}' already exists in this guild")

    def get_user_crews(self, user_id: int, guild_id: int) -> List[Dict]:
        """Get all crews a user is part of"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, crew_name, commander_id, gunner_id, driver_id, wins, losses, description
            FROM persistent_crews 
            WHERE guild_id = ? AND active = 1 AND 
                  (commander_id = ? OR gunner_id = ? OR driver_id = ?)
        ''', (guild_id, user_id, user_id, user_id))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'crew_name': row[1],
                'commander_id': row[2],
                'gunner_id': row[3],
                'driver_id': row[4],
                'wins': row[5],
                'losses': row[6],
                'description': row[7]
            }
            for row in results
        ]

    def update_crew_record(self, crew_id: int, won: bool):
        """Update a crew's win/loss record"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        if won:
            cursor.execute('''
                UPDATE persistent_crews 
                SET wins = wins + 1, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (crew_id,))
        else:
            cursor.execute('''
                UPDATE persistent_crews 
                SET losses = losses + 1, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (crew_id,))
        
        conn.commit()
        conn.close()

    # Guild settings methods
    def get_guild_settings(self, guild_id: int) -> Dict:
        """Get guild settings, create default if not exists"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM guild_settings WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        
        if not result:
            # Create default settings
            default_settings = {
                'admin_roles': json.dumps(["Moderator", "Admin", "Event Organizer"]),
                'event_channels': json.dumps([]),
                'reminder_times': json.dumps([60, 30, 10]),
                'default_event_duration': 120,
                'auto_role_assignment': 1,
                'auto_map_votes': 1,
                'recruitment_enabled': 1,
                'settings_data': json.dumps({})
            }
            
            cursor.execute('''
                INSERT INTO guild_settings (guild_id, admin_roles, event_channels, reminder_times,
                                          default_event_duration, auto_role_assignment, auto_map_votes, recruitment_enabled, settings_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, *default_settings.values()))
            
            conn.commit()
            result = (guild_id, *default_settings.values(), None, None)
            columns = ['guild_id', *default_settings.keys(), 'created_at', 'updated_at']
        
        conn.close()

        settings_row = dict(zip(columns, result))

        return {
            'admin_roles': json.loads(settings_row.get('admin_roles') or '[]'),
            'event_channels': json.loads(settings_row.get('event_channels') or '[]'),
            'reminder_times': json.loads(settings_row.get('reminder_times') or '[]'),
            'default_event_duration': settings_row.get('default_event_duration', 120),
            'auto_role_assignment': bool(settings_row.get('auto_role_assignment', 1)),
            'auto_map_votes': bool(settings_row.get('auto_map_votes', 1)),
            'recruitment_enabled': bool(settings_row.get('recruitment_enabled', 1)),
            'settings_data': json.loads(settings_row.get('settings_data') or '{}')
        }

    def update_guild_setting(self, guild_id: int, setting_name: str, value: Any):
        """Update a specific guild setting"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        # Ensure guild settings exist
        self.get_guild_settings(guild_id)
        
        if setting_name in ['admin_roles', 'event_channels', 'reminder_times', 'settings_data']:
            value = json.dumps(value)
        
        cursor.execute(f'''
            UPDATE guild_settings 
            SET {setting_name} = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE guild_id = ?
        ''', (value, guild_id))
        
        conn.commit()
        conn.close()

    # Reminder system methods
    def add_reminder(self, event_id: int, reminder_time: datetime.datetime, reminder_type: str = 'before_event'):
        """Add a reminder to the queue"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminder_queue (event_id, reminder_time, reminder_type)
            VALUES (?, ?, ?)
        ''', (event_id, reminder_time, reminder_type))
        
        conn.commit()
        conn.close()

    def get_pending_reminders(self) -> List[Tuple]:
        """Get all pending reminders that should be sent"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        now = datetime.datetime.now()
        cursor.execute('''
            SELECT rq.id, rq.event_id, rq.reminder_time, rq.reminder_type,
                   e.guild_id, e.channel_id, e.message_id, e.title
            FROM reminder_queue rq
            JOIN events e ON rq.event_id = e.id
            WHERE rq.sent = 0 AND rq.reminder_time <= ?
        ''', (now,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def mark_reminder_sent(self, reminder_id: int):
        """Mark a reminder as sent"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('UPDATE reminder_queue SET sent = 1 WHERE id = ?', (reminder_id,))
        conn.commit()
        conn.close()

    # Utility methods
    def get_event_guild_id(self, event_id: int) -> Optional[int]:
        """Get guild ID for an event"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        cursor.execute('SELECT guild_id FROM events WHERE id = ?', (event_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def cleanup_old_data(self, days_old: int = 90):
        """Clean up old completed events and related data"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        
        # Get old event IDs
        cursor.execute('''
            SELECT id FROM events 
            WHERE status = 'Completed' AND updated_at < ?
        ''', (cutoff_date,))
        old_event_ids = [row[0] for row in cursor.fetchall()]
        
        if old_event_ids:
            # Clean up related data
            for event_id in old_event_ids:
                cursor.execute('DELETE FROM signups WHERE event_id = ?', (event_id,))
                cursor.execute('DELETE FROM event_history WHERE event_id = ?', (event_id,))
                cursor.execute('DELETE FROM reminder_queue WHERE event_id = ?', (event_id,))
            
            # Clean up old events
            cursor.execute('''
                DELETE FROM events 
                WHERE status = 'Completed' AND updated_at < ?
            ''', (cutoff_date,))
            
            logger.info(f"Cleaned up {len(old_event_ids)} old events")
        
        conn.commit()
        conn.close()

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        cursor = conn.cursor()

        stats = {}

        tables = ['events', 'signups', 'user_stats', 'persistent_crews', 'guild_settings']
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = cursor.fetchone()[0]

        conn.close()
        return stats

    def has_admin_permissions(self, user, guild_id: int) -> bool:
        """Check if user has admin permissions based on guild settings"""
        if not hasattr(user, 'roles'):
            return False

        # Allow server owners and Discord administrators as fallback
        if hasattr(user, 'guild_permissions') and user.guild_permissions.administrator:
            return True

        settings = self.get_guild_settings(guild_id)
        admin_roles = settings.get('admin_roles', [])

        return any(role.name in admin_roles for role in user.roles)
