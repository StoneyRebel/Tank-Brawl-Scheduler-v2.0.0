# cogs/armor_events.py - Complete working version with persistent crew integration
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, UserSelect, Select, Modal, TextInput
import logging
import datetime
import pytz
from typing import Optional, Dict, List

from utils.database import EventDatabase
from utils.config import *

logger = logging.getLogger(__name__)

class ArmorEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Armor Events cog initialized")

    @app_commands.command(name="schedule_event")
    @app_commands.describe(
        event_type="Type of armor event",
        date="Date in YYYY-MM-DD format (e.g., 2025-06-15)",
        time="Time in HH:MM format, 24-hour (e.g., 20:00) - EST timezone",
        map_vote_channel="Channel for map vote (optional - defaults to current channel)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Saturday Brawl", value="saturday_brawl"),
        app_commands.Choice(name="Sunday Operations", value="sunday_ops"),
        app_commands.Choice(name="Training Event", value="training"),
        app_commands.Choice(name="Tournament", value="tournament"),
        app_commands.Choice(name="Custom Event", value="custom")
    ])
    async def schedule_event(self, interaction: discord.Interaction, event_type: app_commands.Choice[str],
                           date: str = None, time: str = None, map_vote_channel: discord.TextChannel = None):

        if not any(role.name in ADMIN_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ You need admin permissions.", ephemeral=True)
            return

        # Defer immediately to prevent timeout (we have 15 minutes instead of 3 seconds)
        await interaction.response.defer(ephemeral=True)

        # Parse datetime with EST timezone
        event_datetime = None
        if date:
            if not time:
                time = "20:00"
            try:
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                time_obj = datetime.datetime.strptime(time, "%H:%M").time()
                event_datetime = datetime.datetime.combine(date_obj, time_obj)
                
                # Convert to EST timezone
                est = pytz.timezone("US/Eastern")
                event_datetime = est.localize(event_datetime)
                
                # Check if in the past (compare with EST now)
                if event_datetime < datetime.datetime.now(est):
                    await interaction.followup.send("❌ Cannot schedule in the past!", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ Invalid date/time format.", ephemeral=True)
                return

        # Get preset (no custom title, use default)
        preset = self.get_event_preset(event_type.value)
        
        # Create event in database (with error handling)
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
            # If database fails, create without it
            logger.error(f"Database error: {e}")
            event_id = 99999  # Fake ID
        
        # Create event signup with full functionality
        view = EventSignupView(preset["title"], preset["description"], event_datetime, event_type.value, event_id)
        embed = view.build_embed(interaction.user)
        message = await interaction.channel.send(embed=embed, view=view)
        view.message = message
        
        # Auto-create map vote (separate message) - Use selected channel or current channel
        vote_channel = map_vote_channel if map_vote_channel else interaction.channel
        map_vote_success = await self.create_map_vote(vote_channel, event_datetime, event_id)
        
        # Response
        response = f"✅ {event_type.value.replace('_', ' ').title()} created!"
        if event_datetime:
            response += f"\n📅 <t:{int(event_datetime.timestamp())}:F>"

        if map_vote_success:
            if map_vote_channel:
                response += f"\n🗳️ Map vote created in {map_vote_channel.mention}!"
            else:
                response += f"\n🗳️ Map vote created automatically!"
        else:
            response += f"\n⚠️ Map vote could not be created (MapVoting cog not available)"

        await interaction.followup.send(response, ephemeral=True)

    def get_event_preset(self, event_type: str):
        presets = {
            "saturday_brawl": {
                "title": "⚔️ Saturday Tank Brawl",
                "description": "**Victory Condition:** Team with the most time on the middle cap wins.\n**Format:** 6v6 Crew Battles"
            },
            "sunday_ops": {
                "title": "🎯 Sunday Armor Operations", 
                "description": "**Mission Type:** Combined Arms Operations\n**Format:** Tactical Gameplay"
            },
            "training": {
                "title": "🎓 Armor Training Session",
                "description": "**Focus:** Skill Development & Practice\n**Format:** Training Exercises"
            },
            "tournament": {
                "title": "🏆 Armor Tournament",
                "description": "**Format:** Competitive Bracket\n**Stakes:** Championship Event"
            },
            "custom": {
                "title": "⚔️ Custom Armor Event",
                "description": "**Format:** Custom Event\n**Details:** TBD"
            }
        }
        return presets.get(event_type, presets["custom"])

    async def assign_event_role(self, user: discord.Member, event_type: str, team: str = None):
        """Assign team-specific roles based on event type and team"""
        try:
            guild = user.guild
            
            # Create event name for roles (make it clean)
            event_names = {
                "saturday_brawl": "Saturday Brawl",
                "sunday_ops": "Sunday Ops", 
                "training": "Training",
                "tournament": "Tournament",
                "custom": "Custom Event"
            }
            
            event_name = event_names.get(event_type, "Custom Event")
            
            logger.info(f"🎭 Assigning role for {user.display_name} - Event: {event_name}, Team: {team}")
            
            # Determine team name and role color
            if team == "A":
                team_name = "Allies"
                role_color = discord.Color.green()
            elif team == "B":
                team_name = "Axis"  
                role_color = discord.Color.red()
            else:
                # No team specified, just assign general participant role
                role_name = f"{event_name} Participant"
                role_color = discord.Color.blue()
                team_name = None
            
            # Create the role name
            if team_name:
                role_name = f"{event_name} {team_name}"
            else:
                role_name = f"{event_name} Participant"
            
            # Find or create the role
            target_role = discord.utils.get(guild.roles, name=role_name)
            
            if not target_role:
                try:
                    target_role = await guild.create_role(
                        name=role_name,
                        color=role_color,
                        mentionable=True,
                        reason=f"Auto-created for {event_name} events"
                    )
                    logger.info(f"✅ Created new role: {role_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to create role {role_name}: {e}")
                    return False
            
            # Assign the role to the user
            if target_role not in user.roles:
                await user.add_roles(target_role, reason=f"Joined {event_name} as {team_name or 'participant'}")
                logger.info(f"✅ Assigned {role_name} to {user.display_name}")
                return True
            else:
                logger.info(f"ℹ️ {user.display_name} already has {role_name}")
                return True
                    
        except Exception as e:
            logger.error(f"❌ Error assigning role: {e}")
            return False

    async def remove_event_role(self, user: discord.Member, event_type: str):
        """Remove all event-specific roles when user leaves"""
        try:
            guild = user.guild
            
            # Event name mapping
            event_names = {
                "saturday_brawl": "Saturday Brawl",
                "sunday_ops": "Sunday Ops",
                "training": "Training", 
                "tournament": "Tournament",
                "custom": "Custom Event"
            }
            
            event_name = event_names.get(event_type, "Custom Event")
            
            # Remove all possible roles for this event
            roles_to_remove = []
            
            # Check for team-specific roles
            allies_role = discord.utils.get(guild.roles, name=f"{event_name} Allies")
            axis_role = discord.utils.get(guild.roles, name=f"{event_name} Axis")
            participant_role = discord.utils.get(guild.roles, name=f"{event_name} Participant")
            
            for role in [allies_role, axis_role, participant_role]:
                if role and role in user.roles:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=f"Left {event_name} event")
                logger.info(f"🗑️ Removed {len(roles_to_remove)} event roles from {user.display_name}")
                return True
            
        except Exception as e:
            logger.error(f"❌ Error removing roles: {e}")
            return False

    async def create_map_vote(self, channel, event_datetime, event_id):
        """Create map vote that ends 1 hour before event starts"""
        try:
            logger.info(f"🔍 DEBUG: Looking for MapVoting cog...")
            map_voting_cog = self.bot.get_cog('MapVoting')

            if not map_voting_cog:
                logger.warning(f"❌ DEBUG: MapVoting cog not found!")
                logger.info(f"Available cogs: {list(self.bot.cogs.keys())}")
                return False

            logger.info(f"✅ DEBUG: Found MapVoting cog")

            # Setup timezone
            est = pytz.timezone("US/Eastern")

            # Calculate vote duration with timezone awareness
            if event_datetime:
                now = datetime.datetime.now(est)
                
                # Calculate when the vote should END (1 hour before event)
                vote_end_time = event_datetime - datetime.timedelta(hours=1)
                
                # Calculate how long the vote should run (from now until vote_end_time)
                vote_duration_seconds = (vote_end_time - now).total_seconds()
                vote_duration_minutes = int(vote_duration_seconds / 60)
                
                logger.info(f"🔍 DEBUG: Event time: {event_datetime}")
                logger.info(f"🔍 DEBUG: Current time: {now}")
                logger.info(f"🔍 DEBUG: Vote should END at: {vote_end_time}")
                logger.info(f"🔍 DEBUG: Calculated vote duration: {vote_duration_minutes} minutes")
                
                # Handle edge cases
                if vote_duration_minutes <= 15:
                    # Event is very soon (less than 1 hour 15 minutes away)
                    duration_minutes = 30  # Give at least 30 minutes
                    logger.info(f"🔍 DEBUG: Event too soon, using minimum 30 minute vote")
                else:
                    # Use the calculated duration (vote ends 1 hour before event)
                    # No maximum cap - vote runs however long needed
                    duration_minutes = vote_duration_minutes
                    logger.info(f"🔍 DEBUG: Using calculated duration to end 1 hour before event")
            else:
                # No event time set, use default 7 days
                duration_minutes = 10080  # 7 days
                logger.info(f"🔍 DEBUG: No event time set, using default 7 day vote")
            
            logger.info(f"🔍 DEBUG: Final vote duration: {duration_minutes} minutes ({duration_minutes/1440:.1f} days)")
            actual_end_time = datetime.datetime.now(est) + datetime.timedelta(minutes=duration_minutes)
            logger.info(f"🔍 DEBUG: Vote will actually end at: {actual_end_time}")
            
            # Create the map vote
            if hasattr(map_voting_cog, 'create_auto_mapvote'):
                result = await map_voting_cog.create_auto_mapvote(event_id, channel, duration_minutes)
                if result:
                    logger.info(f"✅ DEBUG: Map vote created successfully for {duration_minutes} minutes")
                    return True
                else:
                    logger.error(f"❌ DEBUG: Map vote creation returned None/False")
                    return False
            else:
                logger.error(f"❌ DEBUG: create_auto_mapvote method not found")
                available_methods = [method for method in dir(map_voting_cog) if not method.startswith('_')]
                logger.info(f"Available methods: {available_methods}")
                return False
                
        except Exception as e:
            logger.error(f"❌ DEBUG: Error creating map vote: {e}")
            return False

    # NOTE: /list_roles removed - use /event_roles list instead

class EventSignupView(View):
    def __init__(self, title, description, event_time=None, event_type="custom", event_id=None):
        super().__init__(timeout=None)
        self.title = title
        self.description = description
        self.event_time = event_time
        self.event_type = event_type
        self.event_id = event_id
        self.message = None
        
        # Initialize data
        self.commander_a = None
        self.commander_b = None
        self.crews_a = [None] * MAX_CREWS_PER_TEAM
        self.crews_b = [None] * MAX_CREWS_PER_TEAM
        self.recruits = []  # Changed from solo_players to recruits
        
        # Add buttons WITH persistent crew integration
        self.add_item(CommanderSelect(self))
        self.add_item(JoinCrewAButton(self))
        self.add_item(JoinCrewBButton(self))
        self.add_item(JoinWithCrewButton(self))  # NEW: Join with persistent crew
        self.add_item(RecruitMeButton(self))
        self.add_item(RecruitPlayersButton(self))
        self.add_item(EditCrewButton(self))
        self.add_item(LeaveEventButton(self))

    def build_embed(self, author=None):
        embed = discord.Embed(title=self.title, description=self.description, color=0xFF0000)
        
        if self.event_time:
            embed.add_field(name="⏰ Event Time", 
                          value=f"<t:{int(self.event_time.timestamp())}:F>\n<t:{int(self.event_time.timestamp())}:R>", 
                          inline=False)
        
        # Commanders
        commanders = f"**Allies:** {self.commander_a.display_name if self.commander_a else '[Unclaimed]'}\n"
        commanders += f"**Axis:** {self.commander_b.display_name if self.commander_b else '[Unclaimed]'}"
        embed.add_field(name="👑 Commanders", value=commanders, inline=False)

        # Format crews
        def format_crew(slot):
            if slot is None:
                return "[Empty Slot]"
            cmd = slot['commander'].display_name
            gun = slot['gunner'].display_name if slot['gunner'] != slot['commander'] else "*Self*"
            drv = slot['driver'].display_name if slot['driver'] != slot['commander'] else "*Self*"
            crew_tag = f"[{slot['crew_name']}]"
            if slot.get('persistent_crew_id'):
                crew_tag += " 🔗"  # Indicate it's a persistent crew
            return f"**{crew_tag}**\nCmd: {cmd}\nGun: {gun}\nDrv: {drv}"

        allies_text = "\n\n".join([f"{i+1}. {format_crew(crew)}" for i, crew in enumerate(self.crews_a)])
        axis_text = "\n\n".join([f"{i+1}. {format_crew(crew)}" for i, crew in enumerate(self.crews_b)])
        
        embed.add_field(name="🗾 Allies Crews", value=allies_text, inline=True)
        embed.add_field(name="🔵 Axis Crews", value=axis_text, inline=True)
        
        # Available recruits (changed from solo players)
        recruit_text = "\n".join([f"- {user.display_name}" for user in self.recruits]) or "[None Available]"
        embed.add_field(name="🎯 Available Recruits", value=recruit_text, inline=False)
        
        # Add legend
        embed.add_field(name="🔗 Legend", value="🔗 = Persistent Crew", inline=False)
        
        if author:
            embed.set_footer(text=f"Created by {author.display_name}")
        
        return embed

    def is_user_registered(self, user):
        """Check if user is already registered"""
        if user in [self.commander_a, self.commander_b]:
            return True
        for crew_list in [self.crews_a, self.crews_b]:
            for crew in crew_list:
                if isinstance(crew, dict) and user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    return True
        return user in self.recruits

    def get_user_crew(self, user):
        """Get the crew and team for a user"""
        for team, crew_list in [("A", self.crews_a), ("B", self.crews_b)]:
            for i, crew in enumerate(crew_list):
                if isinstance(crew, dict) and crew["commander"] == user:
                    return crew, team, i
        return None, None, None

    def is_user_commander(self, user):
        """Check if user is a crew commander"""
        crew, team, slot_index = self.get_user_crew(user)
        return crew is not None

    async def update_embed(self, interaction):
        if self.message:
            embed = self.build_embed()
            await self.message.edit(embed=embed, view=self)

# UI Components with Role Assignment
class CommanderSelect(Select):
    def __init__(self, view):
        options = [
            discord.SelectOption(label="Allies Commander", value="A", emoji="🗾"),
            discord.SelectOption(label="Axis Commander", value="B", emoji="🔵")
        ]
        super().__init__(placeholder="Become a Team Commander", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        team = self.values[0]  # "A" or "B"
        if team == "A":
            self.view_ref.commander_a = interaction.user
        else:
            self.view_ref.commander_b = interaction.user
        
        # Assign team role
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(interaction.user, self.view_ref.event_type, team)
        
        await self.view_ref.update_embed(interaction)
        team_name = "Allies" if team == "A" else "Axis"
        await interaction.response.send_message(f"✅ You are now {team_name} Commander! Team role assigned.", ephemeral=True)

class JoinCrewAButton(Button):
    def __init__(self, view):
        super().__init__(label="🗾 Join Allies Crew", style=discord.ButtonStyle.primary)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        # Pre-assign Allies role before crew selection
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(interaction.user, self.view_ref.event_type, "A")
        
        await interaction.response.send_message(view=CrewSelectView(self.view_ref, "A", interaction.user), ephemeral=True)

class JoinCrewBButton(Button):
    def __init__(self, view):
        super().__init__(label="🔵 Join Axis Crew", style=discord.ButtonStyle.danger)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        # Pre-assign Axis role before crew selection  
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(interaction.user, self.view_ref.event_type, "B")
        
        await interaction.response.send_message(view=CrewSelectView(self.view_ref, "B", interaction.user), ephemeral=True)

class JoinWithCrewButton(Button):
    def __init__(self, view):
        super().__init__(label="🔗 Join with My Crew", style=discord.ButtonStyle.success, row=1)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        # Get user's persistent crews where they're commander
        crew_cog = interaction.client.get_cog('CrewManagement')
        if not crew_cog:
            await interaction.response.send_message("❌ Crew management system not available.", ephemeral=True)
            return
        
        user_crews = crew_cog.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to join with your crew.\nUse `/crew_panel` to create a crew first!",
                ephemeral=True
            )
            return
        
        # Check if any crew members are already registered
        for crew in commander_crews:
            members = [crew['commander_id'], crew['gunner_id'], crew['driver_id']]
            for member_id in members:
                if member_id:
                    member = interaction.guild.get_member(member_id)
                    if member and self.view_ref.is_user_registered(member):
                        await interaction.response.send_message(
                            f"❌ Crew member {member.mention} is already registered for this event!",
                            ephemeral=True
                        )
                        return
        
        if len(commander_crews) == 1:
            await interaction.response.send_message(
                view=PersistentCrewTeamSelectView(self.view_ref, commander_crews[0]),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Select which crew to join with:",
                view=PersistentCrewSelectionView(self.view_ref, commander_crews),
                ephemeral=True
            )

class RecruitMeButton(Button):
    def __init__(self, view):
        super().__init__(label="🎯 Recruit Me", style=discord.ButtonStyle.secondary, row=1)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if self.view_ref.is_user_registered(interaction.user):
            await interaction.response.send_message("❌ Already registered!", ephemeral=True)
            return
        
        self.view_ref.recruits.append(interaction.user)
        
        # Assign general participant role (no team)
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(interaction.user, self.view_ref.event_type)
        
        await self.view_ref.update_embed(interaction)
        await interaction.response.send_message("✅ Added to recruit pool! Event role assigned.", ephemeral=True)

class RecruitPlayersButton(Button):
    def __init__(self, view):
        super().__init__(label="👥 Recruit Players", style=discord.ButtonStyle.secondary, row=1)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        # Check if user is a crew commander
        if not self.view_ref.is_user_commander(interaction.user):
            await interaction.response.send_message("⚠️ Only crew commanders can recruit players.", ephemeral=True)
            return
        
        # Check if there are any recruits available
        if not self.view_ref.recruits:
            await interaction.response.send_message("⚠️ No recruits available to recruit.", ephemeral=True)
            return
        
        await interaction.response.send_message(view=RecruitSelectionView(self.view_ref, interaction.user), ephemeral=True)

class EditCrewButton(Button):
    def __init__(self, view):
        super().__init__(label="✏️ Edit My Crew", style=discord.ButtonStyle.secondary, row=2)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        crew, team, slot_index = self.view_ref.get_user_crew(interaction.user)
        
        if not crew:
            await interaction.response.send_message("⚠️ You must be a crew commander to edit your crew.", ephemeral=True)
            return
        
        await interaction.response.send_message(view=EditCrewView(self.view_ref, crew, team, slot_index), ephemeral=True)

class LeaveEventButton(Button):
    def __init__(self, view):
        super().__init__(label="❌ Leave Event", style=discord.ButtonStyle.danger, row=2)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        user = interaction.user
        removed = False

        # Remove from all positions
        if user == view.commander_a:
            view.commander_a = None
            removed = True
        elif user == view.commander_b:
            view.commander_b = None
            removed = True

        for i in range(MAX_CREWS_PER_TEAM):
            if isinstance(view.crews_a[i], dict):
                crew = view.crews_a[i]
                if user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    view.crews_a[i] = None
                    removed = True
            if isinstance(view.crews_b[i], dict):
                crew = view.crews_b[i]
                if user in [crew["commander"], crew["gunner"], crew["driver"]]:
                    view.crews_b[i] = None
                    removed = True

        if user in view.recruits:
            view.recruits.remove(user)
            removed = True

        if removed:
            # Remove all event roles when leaving
            armor_events_cog = interaction.client.get_cog('ArmorEvents')
            if armor_events_cog:
                await armor_events_cog.remove_event_role(interaction.user, view.event_type)
            
            await view.update_embed(interaction)
            await interaction.response.send_message("❌ Removed from event! All event roles removed.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Not registered!", ephemeral=True)

# NEW: Persistent Crew Integration Components

class PersistentCrewSelectionView(View):
    def __init__(self, main_view, crews):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.crews = crews
        self.add_item(PersistentCrewDropdown(self))

class PersistentCrewDropdown(Select):
    def __init__(self, parent):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description=f"W:{crew['wins']} L:{crew['losses']} - Join with this crew"
            )
            for crew in parent.crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to join event with", options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        selected_crew = None
        
        for crew in self.parent.crews:
            if crew['id'] == crew_id:
                selected_crew = crew
                break
        
        if selected_crew:
            await interaction.response.send_message(
                f"Selected crew: **{selected_crew['crew_name']}**\nChoose your team:",
                view=PersistentCrewTeamSelectView(self.parent.main_view, selected_crew),
                ephemeral=True
            )

class PersistentCrewTeamSelectView(View):
    def __init__(self, main_view, crew):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.crew = crew
        
        self.add_item(JoinAlliesWithCrewButton(self))
        self.add_item(JoinAxisWithCrewButton(self))

class JoinAlliesWithCrewButton(Button):
    def __init__(self, parent):
        super().__init__(label="🗾 Join Allies", style=discord.ButtonStyle.primary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await self.join_with_crew(interaction, "A")

    async def join_with_crew(self, interaction, team):
        crew = self.parent.crew
        main_view = self.parent.main_view
        
        # Get guild members
        guild = interaction.guild
        commander = guild.get_member(crew['commander_id'])
        gunner = guild.get_member(crew['gunner_id']) if crew['gunner_id'] else commander
        driver = guild.get_member(crew['driver_id']) if crew['driver_id'] else commander
        
        # Check if any are already registered
        for member in [commander, gunner, driver]:
            if member and main_view.is_user_registered(member):
                await interaction.response.send_message(
                    f"❌ {member.mention} is already registered for this event!",
                    ephemeral=True
                )
                return
        
        # Find empty slot
        slot_list = main_view.crews_a if team == "A" else main_view.crews_b
        empty_slot = None
        
        for i in range(MAX_CREWS_PER_TEAM):
            if slot_list[i] is None:
                empty_slot = i
                break
        
        if empty_slot is None:
            team_name = "Allies" if team == "A" else "Axis"
            await interaction.response.send_message(f"❌ {team_name} team is full!", ephemeral=True)
            return
        
        # Create crew entry
        slot_list[empty_slot] = {
            "commander": commander,
            "crew_name": crew['crew_name'],
            "gunner": gunner,
            "driver": driver,
            "persistent_crew_id": crew['id']  # Link to persistent crew
        }
        
        # Assign roles to all crew members
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            for member in [commander, gunner, driver]:
                if member:
                    await armor_events_cog.assign_event_role(member, main_view.event_type, team)
        
        await main_view.update_embed(interaction)
        team_name = "Allies" if team == "A" else "Axis"
        await interaction.response.send_message(
            f"✅ Crew **{crew['crew_name']}** joined {team_name} team! All members assigned team roles.",
            ephemeral=True
        )

class JoinAxisWithCrewButton(Button):
    def __init__(self, parent):
        super().__init__(label="🔵 Join Axis", style=discord.ButtonStyle.danger)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await self.join_with_crew(interaction, "B")

    async def join_with_crew(self, interaction, team):
        crew = self.parent.crew
        main_view = self.parent.main_view
        
        # Get guild members
        guild = interaction.guild
        commander = guild.get_member(crew['commander_id'])
        gunner = guild.get_member(crew['gunner_id']) if crew['gunner_id'] else commander
        driver = guild.get_member(crew['driver_id']) if crew['driver_id'] else commander
        
        # Check if any are already registered
        for member in [commander, gunner, driver]:
            if member and main_view.is_user_registered(member):
                await interaction.response.send_message(
                    f"❌ {member.mention} is already registered for this event!",
                    ephemeral=True
                )
                return
        
        # Find empty slot
        slot_list = main_view.crews_a if team == "A" else main_view.crews_b
        empty_slot = None
        
        for i in range(MAX_CREWS_PER_TEAM):
            if slot_list[i] is None:
                empty_slot = i
                break
        
        if empty_slot is None:
            team_name = "Allies" if team == "A" else "Axis"
            await interaction.response.send_message(f"❌ {team_name} team is full!", ephemeral=True)
            return
        
        # Create crew entry
        slot_list[empty_slot] = {
            "commander": commander,
            "crew_name": crew['crew_name'],
            "gunner": gunner,
            "driver": driver,
            "persistent_crew_id": crew['id']  # Link to persistent crew
        }
        
        # Assign roles to all crew members
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            for member in [commander, gunner, driver]:
                if member:
                    await armor_events_cog.assign_event_role(member, main_view.event_type, team)
        
        await main_view.update_embed(interaction)
        team_name = "Allies" if team == "A" else "Axis"
        await interaction.response.send_message(
            f"✅ Crew **{crew['crew_name']}** joined {team_name} team! All members assigned team roles.",
            ephemeral=True
        )

# Keep all the existing recruit and edit crew components from the previous version...
# (All the other classes remain the same: RecruitSelectionView, AssignGunnerButton, etc.)

# NEW: Recruit Selection System
class RecruitSelectionView(View):
    def __init__(self, main_view, commander):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.commander = commander
        self.selected_recruit = None
        
        # Get commander's crew info
        self.crew, self.team, self.slot_index = main_view.get_user_crew(commander)
        
        self.add_item(RecruitSelect(self))

class RecruitSelect(Select):
    def __init__(self, parent):
        # Create options from available recruits
        options = []
        for recruit in parent.main_view.recruits:
            options.append(discord.SelectOption(
                label=recruit.display_name,
                value=str(recruit.id),
                description=f"Recruit {recruit.display_name}"
            ))
        
        super().__init__(
            placeholder="Select a recruit to add to your crew...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # Find the selected recruit
        selected_id = int(self.values[0])
        selected_recruit = None
        
        for recruit in self.parent.main_view.recruits:
            if recruit.id == selected_id:
                selected_recruit = recruit
                break
        
        if not selected_recruit:
            await interaction.response.send_message("❌ Recruit not found!", ephemeral=True)
            return
        
        self.parent.selected_recruit = selected_recruit
        
        # Now show position selection
        await interaction.response.send_message(
            f"Selected {selected_recruit.mention} - choose their position:",
            view=PositionSelectView(self.parent),
            ephemeral=True
        )

class PositionSelectView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        
        self.add_item(AssignGunnerButton(parent))
        self.add_item(AssignDriverButton(parent))

class AssignGunnerButton(Button):
    def __init__(self, parent):
        super().__init__(label="🎯 Assign as Gunner", style=discord.ButtonStyle.primary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        recruit = self.parent.selected_recruit
        crew = self.parent.crew
        
        # Assign recruit as gunner
        crew['gunner'] = recruit
        
        # Assign team role to the recruit
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(recruit, self.parent.main_view.event_type, self.parent.team)
        
        # Remove from recruit pool
        self.parent.main_view.recruits.remove(recruit)
        
        await self.parent.main_view.update_embed(interaction)
        team_name = "Allies" if self.parent.team == "A" else "Axis"
        await interaction.response.send_message(
            f"✅ {recruit.mention} recruited as gunner for **{crew['crew_name']}**! {team_name} role assigned.",
            ephemeral=True
        )

class AssignDriverButton(Button):
    def __init__(self, parent):
        super().__init__(label="🚗 Assign as Driver", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        recruit = self.parent.selected_recruit
        crew = self.parent.crew
        
        # Assign recruit as driver
        crew['driver'] = recruit
        
        # Assign team role to the recruit
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(recruit, self.parent.main_view.event_type, self.parent.team)
        
        # Remove from recruit pool
        self.parent.main_view.recruits.remove(recruit)
        
        await self.parent.main_view.update_embed(interaction)
        team_name = "Allies" if self.parent.team == "A" else "Axis"
        await interaction.response.send_message(
            f"✅ {recruit.mention} recruited as driver for **{crew['crew_name']}**! {team_name} role assigned.",
            ephemeral=True
        )

# Edit Crew System (unchanged)
class EditCrewView(View):
    def __init__(self, main_view, crew, team, slot_index):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.crew = crew
        self.team = team
        self.slot_index = slot_index

        self.add_item(EditGunnerButton(self))
        self.add_item(EditDriverButton(self))
        # Note: Crew name editing is only available in crew management panel for persistent crews

class EditGunnerButton(Button):
    def __init__(self, parent):
        super().__init__(label="🎯 Change Gunner", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=EditGunnerView(self.parent), ephemeral=True)

class EditDriverButton(Button):
    def __init__(self, parent):
        super().__init__(label="🚗 Change Driver", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=EditDriverView(self.parent), ephemeral=True)

class EditGunnerView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(UpdateGunnerSelect(self))

class UpdateGunnerSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select new gunner (or leave empty to clear)", min_values=0, max_values=1)
        self.view_parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.values:
            new_gunner = self.values[0]
            if self.view_parent.main_view.is_user_registered(new_gunner):
                await interaction.response.send_message("❌ User already registered!", ephemeral=True)
                return

            # Assign team role to new gunner
            armor_events_cog = interaction.client.get_cog('ArmorEvents')
            if armor_events_cog:
                await armor_events_cog.assign_event_role(new_gunner, self.view_parent.main_view.event_type, self.view_parent.team)

            self.view_parent.crew['gunner'] = new_gunner
            team_name = "Allies" if self.view_parent.team == "A" else "Axis"
            await interaction.response.send_message(f"✅ Gunner updated to {new_gunner.mention}! {team_name} role assigned.", ephemeral=True)
        else:
            self.view_parent.crew['gunner'] = self.view_parent.crew['commander']
            await interaction.response.send_message("✅ Gunner cleared - commander will gun!", ephemeral=True)

        await self.view_parent.main_view.update_embed(interaction)

class EditDriverView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(UpdateDriverSelect(self))

class UpdateDriverSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select new driver (or leave empty to clear)", min_values=0, max_values=1)
        self.view_parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.values:
            new_driver = self.values[0]
            if self.view_parent.main_view.is_user_registered(new_driver):
                await interaction.response.send_message("❌ User already registered!", ephemeral=True)
                return

            # Assign team role to new driver
            armor_events_cog = interaction.client.get_cog('ArmorEvents')
            if armor_events_cog:
                await armor_events_cog.assign_event_role(new_driver, self.view_parent.main_view.event_type, self.view_parent.team)

            self.view_parent.crew['driver'] = new_driver
            team_name = "Allies" if self.view_parent.team == "A" else "Axis"
            await interaction.response.send_message(f"✅ Driver updated to {new_driver.mention}! {team_name} role assigned.", ephemeral=True)
        else:
            self.view_parent.crew['driver'] = self.view_parent.crew['commander']
            await interaction.response.send_message("✅ Driver cleared - commander will drive!", ephemeral=True)

        await self.view_parent.main_view.update_embed(interaction)

class EditCrewNameModal(Modal):
    def __init__(self, parent):
        super().__init__(title="Edit Crew Name")
        self.parent = parent
        
        self.name_input = TextInput(
            label="New Crew Name",
            placeholder="Enter new crew name...",
            default=self.parent.crew['crew_name'],
            max_length=30
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message("❌ Crew name cannot be empty!", ephemeral=True)
            return
        
        self.parent.crew['crew_name'] = new_name
        await self.parent.main_view.update_embed(interaction)
        await interaction.response.send_message(f"✅ Crew name updated to '{new_name}'!", ephemeral=True)

# Crew selection system with role assignment
class CrewSelectView(View):
    def __init__(self, main_view, team, commander):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.team = team
        self.commander = commander
        self.gunner = None
        self.add_item(GunnerSelect(self))

class GunnerSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select Gunner", min_values=1, max_values=1)
        self.view_parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.view_parent.main_view.is_user_registered(self.values[0]):
            await interaction.response.send_message("❌ User already registered!", ephemeral=True)
            return

        self.view_parent.gunner = self.values[0]

        # Assign team role to gunner
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(self.view_parent.gunner, self.view_parent.main_view.event_type, self.view_parent.team)

        await interaction.response.send_message(view=DriverSelectView(self.view_parent), ephemeral=True)

class DriverSelectView(View):
    def __init__(self, parent):
        super().__init__(timeout=300)
        self.parent = parent
        self.add_item(DriverSelect(parent))

class DriverSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select Driver", min_values=1, max_values=1)
        self.view_parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.view_parent.main_view.is_user_registered(self.values[0]):
            await interaction.response.send_message("❌ User already registered!", ephemeral=True)
            return

        driver = self.values[0]

        # Assign team role to driver
        armor_events_cog = interaction.client.get_cog('ArmorEvents')
        if armor_events_cog:
            await armor_events_cog.assign_event_role(driver, self.view_parent.main_view.event_type, self.view_parent.team)

        await interaction.response.send_modal(CrewNameModal(self.view_parent, driver))

class CrewNameModal(Modal):
    def __init__(self, parent, driver):
        super().__init__(title="Name Your Crew")
        self.parent = parent
        self.driver = driver
        self.name_input = TextInput(
            label="Crew Name",
            placeholder="Enter crew name...",
            default=f"{self.parent.commander.display_name}'s Crew",
            max_length=30
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        crew_name = self.name_input.value.strip() or f"{self.parent.commander.display_name}'s Crew"
        main_view = self.parent.main_view
        slot_list = main_view.crews_a if self.parent.team == "A" else main_view.crews_b

        # Get the armor events cog for role assignment
        armor_events_cog = interaction.client.get_cog('ArmorEvents')

        for i in range(MAX_CREWS_PER_TEAM):
            if slot_list[i] is None:
                slot_list[i] = {
                    "commander": self.parent.commander,
                    "crew_name": crew_name,
                    "gunner": self.parent.gunner,
                    "driver": self.driver
                }
                
                # Assign team roles to all crew members
                if armor_events_cog:
                    # Assign role to commander
                    await armor_events_cog.assign_event_role(self.parent.commander, main_view.event_type, self.parent.team)
                    
                    # Assign role to gunner  
                    await armor_events_cog.assign_event_role(self.parent.gunner, main_view.event_type, self.parent.team)
                    
                    # Assign role to driver
                    await armor_events_cog.assign_event_role(self.driver, main_view.event_type, self.parent.team)
                
                await main_view.update_embed(interaction)
                team_name = "Allies" if self.parent.team == "A" else "Axis"
                await interaction.response.send_message(f"✅ Crew '{crew_name}' registered for {team_name}! Team roles assigned to all members.", ephemeral=True)
                return

        await interaction.response.send_message("❌ Team is full!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ArmorEvents(bot))
