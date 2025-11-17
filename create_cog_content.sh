#!/bin/bash

echo "🔨 Creating Tank Brawl Scheduler cog content..."

# Create __init__.py for cogs
touch cogs/__init__.py

# Create simplified but functional admin_tools.py
cat > cogs/admin_tools.py << 'ADMIN_EOF'
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.database import EventDatabase
from utils.config import ADMIN_ROLES, COLORS

logger = logging.getLogger(__name__)

class AdminTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Admin Tools cog initialized")

    def has_admin_permissions(self, user: discord.Member) -> bool:
        if not hasattr(user, 'roles'):
            return False
        return any(role.name in ADMIN_ROLES for role in user.roles)

    @app_commands.command(name="settings")
    async def server_settings(self, interaction: discord.Interaction):
        """Configure bot settings for this server"""
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚙️ Tank Brawl Scheduler Settings",
            description="Bot configuration for this server",
            color=COLORS["info"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="database_stats")
    async def database_stats(self, interaction: discord.Interaction):
        """Show database statistics"""
        if not self.has_admin_permissions(interaction.user):
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        
        stats = self.db.get_database_stats()
        embed = discord.Embed(title="📊 Database Statistics", color=COLORS["info"])
        
        for table, count in stats.items():
            embed.add_field(name=table.replace('_', ' ').title(), value=f"{count:,}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminTools(bot))
ADMIN_EOF

echo "✅ Created admin_tools.py"

# Create simplified armor_events.py
cat > cogs/armor_events.py << 'ARMOR_EOF'
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import logging
import datetime
from utils.database import EventDatabase
from utils.config import ADMIN_ROLES, COLORS, MAX_CREWS_PER_TEAM

logger = logging.getLogger(__name__)

class ArmorEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Armor Events cog initialized")

    @app_commands.command(name="schedule_event")
    @app_commands.describe(
        event_type="Type of tank battle event",
        date="Date in YYYY-MM-DD format",
        time="Time in HH:MM format (24-hour)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Saturday Tank Brawl", value="saturday_brawl"),
        app_commands.Choice(name="Sunday Tank Ops", value="sunday_ops"),
        app_commands.Choice(name="Tank Training", value="training"),
        app_commands.Choice(name="Tank Tournament", value="tournament"),
        app_commands.Choice(name="Custom Event", value="custom")
    ])
    async def schedule_event(self, interaction: discord.Interaction, event_type: app_commands.Choice[str],
                           date: str = None, time: str = None):
        
        if not any(role.name in ADMIN_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return
        
        # Get preset
        preset = self.get_event_preset(event_type.value)
        
        # Parse datetime if provided
        event_datetime = None
        if date:
            try:
                if not time:
                    time = "20:00"
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                time_obj = datetime.datetime.strptime(time, "%H:%M").time()
                event_datetime = datetime.datetime.combine(date_obj, time_obj)
            except ValueError:
                await interaction.response.send_message("❌ Invalid date/time format.", ephemeral=True)
                return
        
        # Create event
        try:
            event_id = self.db.create_event(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                creator_id=interaction.user.id,
                title=preset["title"],
                description=preset["description"],
                event_time=event_datetime,
                event_type=event_type.value
            )
        except Exception as e:
            logger.error(f"Database error: {e}")
            event_id = 99999
        
        # Create event signup view
        view = EventSignupView(preset["title"], preset["description"], event_datetime)
        embed = view.build_embed(interaction.user)
        
        await interaction.response.send_message(embed=embed, view=view)

    def get_event_preset(self, event_type: str):
        presets = {
            "saturday_brawl": {
                "title": "🚗 Saturday Tank Brawl",
                "description": "**Victory:** Destroy enemy tanks and hold objectives\n**Format:** Tank vs Tank Combat"
            },
            "sunday_ops": {
                "title": "🎯 Sunday Tank Operations", 
                "description": "**Mission:** Combined tank operations\n**Format:** Tactical tank gameplay"
            },
            "training": {
                "title": "🎓 Tank Training Session",
                "description": "**Focus:** Tank combat skills\n**Format:** Training exercises"
            },
            "tournament": {
                "title": "🏆 Tank Tournament",
                "description": "**Format:** Competitive tournament\n**Stakes:** Championship event"
            },
            "custom": {
                "title": "⚔️ Custom Tank Event",
                "description": "**Format:** Custom tank battle\n**Details:** TBD"
            }
        }
        return presets.get(event_type, presets["custom"])

class EventSignupView(View):
    def __init__(self, title, description, event_time=None):
        super().__init__(timeout=None)
        self.title = title
        self.description = description
        self.event_time = event_time
        self.commander_a = None
        self.commander_b = None
        self.recruits = []
        
        self.add_item(CommanderSelect(self))
        self.add_item(RecruitMeButton(self))
        self.add_item(LeaveEventButton(self))

    def build_embed(self, author=None):
        embed = discord.Embed(title=self.title, description=self.description, color=COLORS["info"])
        
        if self.event_time:
            embed.add_field(name="⏰ Event Time", 
                          value=f"<t:{int(self.event_time.timestamp())}:F>", inline=False)
        
        commanders = f"**Allies:** {self.commander_a.mention if self.commander_a else '[Open]'}\n"
        commanders += f"**Axis:** {self.commander_b.mention if self.commander_b else '[Open]'}"
        embed.add_field(name="👑 Commanders", value=commanders, inline=False)
        
        recruit_text = "\n".join([f"- {user.mention}" for user in self.recruits]) or "[None yet]"
        embed.add_field(name="🎯 Available Players", value=recruit_text, inline=False)
        
        if author:
            embed.set_footer(text=f"Created by {author.display_name}")
        
        return embed

    def is_user_registered(self, user):
        return user in [self.commander_a, self.commander_b] or user in self.recruits

    async def update_embed(self, interaction):
        embed = self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

class CommanderSelect(Select):
    def __init__(self, view):
        options = [
            discord.SelectOption(label="Allies Commander", value="A", emoji="🔵"),
            discord.SelectOption(label="Axis Commander", value="B", emoji="🔴")
        ]
        super().__init__(placeholder="Become a Team Commander", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        team = self.values[0]
        if team == "A":
            self.view_ref.commander_a = interaction.user
        else:
            self.view_ref.commander_b = interaction.user
        
        await self.view_ref.update_embed(interaction)
        await interaction.response.send_message(f"✅ You are now {team} Commander!", ephemeral=True)

class RecruitMeButton(Button):
    def __init__(self, view):
        super().__init__(label="🎯 Join as Player", style=discord.ButtonStyle.success)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        self.view_ref.recruits.append(interaction.user)
        await self.view_ref.update_embed(interaction)
        await interaction.response.send_message("✅ Added to player pool!", ephemeral=True)

class LeaveEventButton(Button):
    def __init__(self, view):
        super().__init__(label="❌ Leave Event", style=discord.ButtonStyle.danger)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        user = interaction.user
        removed = False

        if user == view.commander_a:
            view.commander_a = None
            removed = True
        elif user == view.commander_b:
            view.commander_b = None
            removed = True
        elif user in view.recruits:
            view.recruits.remove(user)
            removed = True

        if removed:
            await view.update_embed(interaction)
            await interaction.response.send_message("❌ Removed from event!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Not registered!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ArmorEvents(bot))
ARMOR_EOF

echo "✅ Created armor_events.py"

echo "🎉 Basic cog content created! The bot will now have functional commands."
