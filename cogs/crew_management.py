# cogs/crew_management.py - Persistent crew management system with public panel
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput, UserSelect
import logging
from typing import Optional, List, Dict
import sqlite3

from utils.database import EventDatabase
from utils.config import *

logger = logging.getLogger(__name__)

class CrewManagement(commands.Cog):
    """Persistent crew management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = EventDatabase()
        logger.info("Crew Management cog initialized")

    @app_commands.command(name="create_crew")
    @app_commands.describe(
        name="Name for your crew (must be unique)",
        description="Optional description for your crew"
    )
    async def create_crew(self, interaction: discord.Interaction, name: str, description: str = None):
        """Create a new persistent crew"""
        
        # Validate crew name
        if len(name) > 30:
            await interaction.response.send_message("❌ Crew name must be 30 characters or less.", ephemeral=True)
            return
        
        if not name.replace(' ', '').replace('-', '').replace('_', '').isalnum():
            await interaction.response.send_message("❌ Crew name can only contain letters, numbers, spaces, hyphens, and underscores.", ephemeral=True)
            return
        
        try:
            crew_id = self.db.create_persistent_crew(
                guild_id=interaction.guild.id,
                crew_name=name,
                commander_id=interaction.user.id,
                description=description
            )
            
            embed = discord.Embed(
                title="🎉 Crew Created Successfully!",
                description=f"Your crew **{name}** has been created.",
                color=COLORS["success"]
            )
            
            embed.add_field(
                name="Crew Details",
                value=f"**Name:** {name}\n"
                      f"**Commander:** {interaction.user.mention}\n"
                      f"**ID:** {crew_id}\n"
                      f"**Description:** {description or 'No description set'}",
                inline=False
            )
            
            embed.add_field(
                name="Next Steps",
                value="• Use `/crew_invite` to add members\n"
                      "• Use `/crew_info` to view your crew\n"
                      "• Use `/crew_edit` to modify details",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="crew_info")
    @app_commands.describe(crew_name="Name of the crew to view (leave empty to see your crews)")
    async def crew_info(self, interaction: discord.Interaction, crew_name: str = None):
        """View information about a crew"""
        
        if crew_name:
            # View specific crew
            crew = self.get_crew_by_name(interaction.guild.id, crew_name)
            if not crew:
                await interaction.response.send_message(f"❌ Crew '{crew_name}' not found.", ephemeral=True)
                return
            
            embed = self.build_crew_info_embed(crew, interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # View user's crews
            user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
            
            if not user_crews:
                await interaction.response.send_message(
                    "❌ You're not part of any crews. Use `/create_crew` to make one!", 
                    ephemeral=True
                )
                return
            
            if len(user_crews) == 1:
                embed = self.build_crew_info_embed(user_crews[0], interaction.guild)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # Multiple crews - show selection
                await interaction.response.send_message(
                    view=CrewSelectionView(user_crews, interaction.guild), 
                    ephemeral=True
                )

    @app_commands.command(name="crew_invite")
    @app_commands.describe(
        user="User to invite to your crew",
        role="Role to offer (Gunner or Driver)"
    )
    @app_commands.choices(role=[
        app_commands.Choice(name="Gunner", value="gunner"),
        app_commands.Choice(name="Driver", value="driver")
    ])
    async def crew_invite(self, interaction: discord.Interaction, user: discord.Member, role: app_commands.Choice[str]):
        """Invite a user to join your crew"""
        
        # Get user's crews where they're commander
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to invite members.", 
                ephemeral=True
            )
            return
        
        if len(commander_crews) == 1:
            await self.process_crew_invite(interaction, commander_crews[0], user, role.value)
        else:
            # Multiple crews - show selection
            await interaction.response.send_message(
                view=CrewInviteSelectionView(commander_crews, user, role.value), 
                ephemeral=True
            )

    @app_commands.command(name="crew_edit")
    async def crew_edit(self, interaction: discord.Interaction):
        """Edit your crew details"""
        
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to edit crew details.", 
                ephemeral=True
            )
            return
        
        if len(commander_crews) == 1:
            await interaction.response.send_message(
                view=CrewEditView(commander_crews[0]), 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                view=CrewEditSelectionView(commander_crews), 
                ephemeral=True
            )

    @app_commands.command(name="crew_leave")
    async def crew_leave(self, interaction: discord.Interaction):
        """Leave one of your crews"""
        
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        
        if not user_crews:
            await interaction.response.send_message("❌ You're not part of any crews.", ephemeral=True)
            return
        
        if len(user_crews) == 1:
            await self.process_crew_leave(interaction, user_crews[0])
        else:
            await interaction.response.send_message(
                view=CrewLeaveSelectionView(user_crews), 
                ephemeral=True
            )

    @app_commands.command(name="crew_list")
    @app_commands.describe(page="Page number to view (default: 1)")
    async def crew_list(self, interaction: discord.Interaction, page: int = 1):
        """List all crews in the server"""
        
        crews = self.get_all_guild_crews(interaction.guild.id, page)
        
        if not crews:
            await interaction.response.send_message("❌ No crews found in this server.", ephemeral=True)
            return
        
        embed = self.build_crew_list_embed(crews, page, interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="crew_panel")
    async def crew_panel(self, interaction: discord.Interaction):
        """Create a crew management panel in this channel"""
        
        if not any(role.name in ADMIN_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only admins can create crew panels.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎛️ Crew Management Panel",
            description="Manage your persistent crews using the buttons below.",
            color=COLORS["info"]
        )
        
        embed.add_field(
            name="📋 Available Actions",
            value="🆕 **Create Crew** - Form a new crew\n"
                  "ℹ️ **Crew Info** - View crew details\n"
                  "✏️ **Edit Crew** - Modify crew settings\n"
                  "📨 **Invite Player** - Add members to crew\n"
                  "🚪 **Leave Crew** - Exit a crew\n"
                  "📜 **List Crews** - Browse server crews",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Only commanders can edit and invite\n"
                  "• Crews persist across events\n"
                  "• You can be in multiple crews\n"
                  "• This panel stays active permanently",
            inline=False
        )
        
        view = CrewManagementPanelView(self.db)
        await interaction.response.send_message(embed=embed, view=view)
        await interaction.followup.send("✅ Crew management panel created in this channel!", ephemeral=True)

    # Helper methods
    def get_crew_by_name(self, guild_id: int, crew_name: str) -> Optional[Dict]:
        """Get crew by name"""
        conn = sqlite3.connect(self.db.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, crew_name, commander_id, gunner_id, driver_id, wins, losses, description
            FROM persistent_crews 
            WHERE guild_id = ? AND crew_name = ? AND active = 1
        ''', (guild_id, crew_name))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'crew_name': result[1],
                'commander_id': result[2],
                'gunner_id': result[3],
                'driver_id': result[4],
                'wins': result[5],
                'losses': result[6],
                'description': result[7]
            }
        return None

    def get_all_guild_crews(self, guild_id: int, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Get all crews in a guild with pagination"""
        conn = sqlite3.connect(self.db.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        offset = (page - 1) * per_page
        
        cursor.execute('''
            SELECT id, crew_name, commander_id, gunner_id, driver_id, wins, losses, description
            FROM persistent_crews 
            WHERE guild_id = ? AND active = 1
            ORDER BY crew_name
            LIMIT ? OFFSET ?
        ''', (guild_id, per_page, offset))
        
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

    def build_crew_info_embed(self, crew: Dict, guild: discord.Guild) -> discord.Embed:
        """Build embed with crew information"""
        embed = discord.Embed(
            title=f"{EMOJIS['commander']} {crew['crew_name']}",
            color=COLORS["info"]
        )
        
        # Get member objects
        commander = guild.get_member(crew['commander_id'])
        gunner = guild.get_member(crew['gunner_id']) if crew['gunner_id'] else None
        driver = guild.get_member(crew['driver_id']) if crew['driver_id'] else None
        
        members_text = f"**Commander:** {commander.mention if commander else 'Unknown'}\n"
        members_text += f"**Gunner:** {gunner.mention if gunner else '*Open Position*'}\n"
        members_text += f"**Driver:** {driver.mention if driver else '*Open Position*'}"
        
        embed.add_field(name="Members", value=members_text, inline=False)
        
        if crew['description']:
            embed.add_field(name="Description", value=crew['description'], inline=False)
        
        # Statistics
        total_matches = crew['wins'] + crew['losses']
        win_rate = (crew['wins'] / total_matches * 100) if total_matches > 0 else 0
        
        stats_text = f"**Matches:** {total_matches}\n"
        stats_text += f"**Wins:** {crew['wins']}\n"
        stats_text += f"**Losses:** {crew['losses']}\n"
        stats_text += f"**Win Rate:** {win_rate:.1f}%"
        
        embed.add_field(name="Statistics", value=stats_text, inline=True)
        
        embed.set_footer(text=f"Crew ID: {crew['id']}")
        
        return embed

    def build_crew_list_embed(self, crews: List[Dict], page: int, guild: discord.Guild) -> discord.Embed:
        """Build embed listing crews"""
        embed = discord.Embed(
            title=f"📋 Server Crews - Page {page}",
            color=COLORS["neutral"]
        )
        
        for crew in crews:
            commander = guild.get_member(crew['commander_id'])
            total_matches = crew['wins'] + crew['losses']
            
            crew_text = f"**Commander:** {commander.mention if commander else 'Unknown'}\n"
            crew_text += f"**Record:** {crew['wins']}W - {crew['losses']}L"
            
            embed.add_field(
                name=crew['crew_name'],
                value=crew_text,
                inline=True
            )
        
        return embed

    async def process_crew_invite(self, interaction: discord.Interaction, crew: Dict, 
                                target_user: discord.Member, role: str):
        """Process crew invitation"""
        
        # Check if position is available
        if role == "gunner" and crew['gunner_id']:
            await interaction.response.send_message(
                f"❌ The gunner position in {crew['crew_name']} is already filled.", 
                ephemeral=True
            )
            return
        
        if role == "driver" and crew['driver_id']:
            await interaction.response.send_message(
                f"❌ The driver position in {crew['crew_name']} is already filled.", 
                ephemeral=True
            )
            return
        
        # Send invitation
        embed = discord.Embed(
            title="🎯 Crew Invitation!",
            description=f"You've been invited to join **{crew['crew_name']}**!",
            color=COLORS["info"]
        )
        
        embed.add_field(
            name="Position Offered",
            value=f"**Role:** {role.title()}\n"
                  f"**Crew:** {crew['crew_name']}\n"
                  f"**Commander:** {interaction.user.mention}",
            inline=False
        )
        
        if crew['description']:
            embed.add_field(name="Crew Description", value=crew['description'], inline=False)
        
        try:
            view = CrewInvitationView(crew, role, interaction.user, target_user, self.db)
            await target_user.send(embed=embed, view=view)
            
            await interaction.response.send_message(
                f"✅ Invitation sent to {target_user.mention} for the {role} position!", 
                ephemeral=True
            )
            
        except discord.Forbidden:
            # Send in channel if DM fails
            view = CrewInvitationView(crew, role, interaction.user, target_user, self.db)
            await interaction.response.send_message(
                content=f"{target_user.mention} - You have a crew invitation!",
                embed=embed,
                view=view
            )

    async def process_crew_leave(self, interaction: discord.Interaction, crew: Dict):
        """Process leaving a crew"""
        
        user_id = interaction.user.id
        crew_name = crew['crew_name']
        
        if crew['commander_id'] == user_id:
            # Commander leaving - need confirmation
            embed = discord.Embed(
                title="⚠️ Disband Crew?",
                description=f"As commander of **{crew_name}**, leaving will disband the entire crew.",
                color=COLORS["warning"]
            )
            
            view = CrewDisbandConfirmView(crew, self.db)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # Regular member leaving
            # Update database to remove user from crew
            conn = sqlite3.connect(self.db.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            if crew['gunner_id'] == user_id:
                cursor.execute('UPDATE persistent_crews SET gunner_id = NULL WHERE id = ?', (crew['id'],))
                position = "gunner"
            elif crew['driver_id'] == user_id:
                cursor.execute('UPDATE persistent_crews SET driver_id = NULL WHERE id = ?', (crew['id'],))
                position = "driver"
            
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="✅ Left Crew",
                description=f"You've left **{crew_name}** ({position} position).",
                color=COLORS["success"]
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

# UI Components for Crew Management Panel

class CrewManagementPanelView(View):
    def __init__(self, db: EventDatabase):
        super().__init__(timeout=None)  # Persistent panel - no timeout
        self.db = db
        
        # Add all the crew management buttons
        self.add_item(CreateCrewPanelButton(db))
        self.add_item(CrewInfoPanelButton(db))
        self.add_item(EditCrewPanelButton(db))
        self.add_item(InvitePlayerPanelButton(db))
        self.add_item(LeaveCrewPanelButton(db))
        self.add_item(ListCrewsPanelButton(db))

class CreateCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="🆕 Create Crew", 
            style=discord.ButtonStyle.success, 
            row=0,
            custom_id="crew_panel_create"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateCrewPanelModal(self.db))

class CrewInfoPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="ℹ️ Crew Info", 
            style=discord.ButtonStyle.primary, 
            row=0,
            custom_id="crew_panel_info"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        # Get user's crews
        cog = interaction.client.get_cog('CrewManagement')
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        
        if not user_crews:
            await interaction.response.send_message(
                "❌ You're not part of any crews. Create one with the **Create Crew** button!", 
                ephemeral=True
            )
            return
        
        if len(user_crews) == 1:
            embed = cog.build_crew_info_embed(user_crews[0], interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Multiple crews - show selection
            await interaction.response.send_message(
                "Select a crew to view:",
                view=CrewInfoSelectionView(user_crews, interaction.guild), 
                ephemeral=True
            )

class EditCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="✏️ Edit Crew", 
            style=discord.ButtonStyle.secondary, 
            row=0,
            custom_id="crew_panel_edit"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to edit crew details.", 
                ephemeral=True
            )
            return
        
        if len(commander_crews) == 1:
            await interaction.response.send_message(
                view=CrewEditView(commander_crews[0]), 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Select a crew to edit:",
                view=CrewEditSelectionView(commander_crews), 
                ephemeral=True
            )

class InvitePlayerPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="📨 Invite Player", 
            style=discord.ButtonStyle.secondary, 
            row=1,
            custom_id="crew_panel_invite"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        # Get user's crews where they're commander
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        commander_crews = [crew for crew in user_crews if crew['commander_id'] == interaction.user.id]
        
        if not commander_crews:
            await interaction.response.send_message(
                "❌ You must be a crew commander to invite members.", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            view=CrewInviteSetupView(commander_crews), 
            ephemeral=True
        )

class LeaveCrewPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="🚪 Leave Crew", 
            style=discord.ButtonStyle.danger, 
            row=1,
            custom_id="crew_panel_leave"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        user_crews = self.db.get_user_crews(interaction.user.id, interaction.guild.id)
        
        if not user_crews:
            await interaction.response.send_message("❌ You're not part of any crews.", ephemeral=True)
            return
        
        if len(user_crews) == 1:
            cog = interaction.client.get_cog('CrewManagement')
            await cog.process_crew_leave(interaction, user_crews[0])
        else:
            await interaction.response.send_message(
                "Select a crew to leave:",
                view=CrewLeaveSelectionView(user_crews), 
                ephemeral=True
            )

class ListCrewsPanelButton(Button):
    def __init__(self, db: EventDatabase):
        super().__init__(
            label="📜 List Crews", 
            style=discord.ButtonStyle.primary, 
            row=1,
            custom_id="crew_panel_list"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog('CrewManagement')
        crews = cog.get_all_guild_crews(interaction.guild.id, 1)
        
        if not crews:
            await interaction.response.send_message("❌ No crews found in this server.", ephemeral=True)
            return
        
        embed = cog.build_crew_list_embed(crews, 1, interaction.guild)
        
        # Add pagination if needed
        if len(crews) >= 10:
            view = CrewListPaginationView(cog, interaction.guild, 1)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

# Modal for creating crews from the panel
class CreateCrewPanelModal(Modal):
    def __init__(self, db: EventDatabase):
        super().__init__(title="Create New Crew")
        self.db = db
        
        self.name_input = TextInput(
            label="Crew Name",
            placeholder="Enter a unique crew name...",
            max_length=30
        )
        self.add_item(self.name_input)
        
        self.description_input = TextInput(
            label="Crew Description (Optional)",
            placeholder="Describe your crew...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        description = self.description_input.value.strip() or None
        
        # Validate crew name
        if len(name) > 30:
            await interaction.response.send_message("❌ Crew name must be 30 characters or less.", ephemeral=True)
            return
        
        if not name.replace(' ', '').replace('-', '').replace('_', '').isalnum():
            await interaction.response.send_message("❌ Crew name can only contain letters, numbers, spaces, hyphens, and underscores.", ephemeral=True)
            return
        
        try:
            crew_id = self.db.create_persistent_crew(
                guild_id=interaction.guild.id,
                crew_name=name,
                commander_id=interaction.user.id,
                description=description
            )
            
            embed = discord.Embed(
                title="🎉 Crew Created Successfully!",
                description=f"Your crew **{name}** has been created.",
                color=COLORS["success"]
            )
            
            embed.add_field(
                name="Crew Details",
                value=f"**Name:** {name}\n"
                      f"**Commander:** {interaction.user.mention}\n"
                      f"**ID:** {crew_id}\n"
                      f"**Description:** {description or 'No description set'}",
                inline=False
            )
            
            embed.add_field(
                name="Next Steps",
                value="• Use **Invite Player** to add members\n"
                      "• Use **Crew Info** to view your crew\n"
                      "• Use **Edit Crew** to modify details",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

# Selection views for crews
class CrewInfoSelectionView(View):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.guild = guild
        self.add_item(CrewInfoSelectDropdown(crews, guild))

class CrewInfoSelectDropdown(Select):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description=f"W: {crew['wins']} L: {crew['losses']}"
            )
            for crew in crews[:25]  # Discord limit
        ]
        
        super().__init__(placeholder="Select a crew to view info", options=options)
        self.crews = {crew['id']: crew for crew in crews}
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        # Build crew info embed
        cog = interaction.client.get_cog('CrewManagement')
        embed = cog.build_crew_info_embed(crew, self.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Crew invitation setup from panel
class CrewInviteSetupView(View):
    def __init__(self, crews: List[Dict]):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.add_item(CrewInviteCrewSelect(crews))

class CrewInviteCrewSelect(Select):
    def __init__(self, crews: List[Dict]):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description="Select this crew to invite to"
            )
            for crew in crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to invite to", options=options)
        self.crews = {crew['id']: crew for crew in crews}

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        await interaction.response.send_message(
            f"Selected crew: **{crew['crew_name']}**\nNow select a user and role:",
            view=CrewInviteUserRoleView(crew),
            ephemeral=True
        )

class CrewInviteUserRoleView(View):
    def __init__(self, crew: Dict):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crew = crew
        self.selected_user = None
        self.selected_role = None
        
        self.add_item(InviteUserSelect(self))
        self.add_item(InviteRoleSelect(self))
        self.add_item(SendInviteButton(self))

class InviteUserSelect(UserSelect):
    def __init__(self, parent):
        super().__init__(placeholder="Select user to invite", min_values=1, max_values=1)
        self.view_parent = parent

    async def callback(self, interaction: discord.Interaction):
        self.view_parent.selected_user = self.values[0]
        await interaction.response.send_message(
            f"✅ Selected user: {self.values[0].mention}\nNow select a role and click Send Invite.",
            ephemeral=True
        )

class InviteRoleSelect(Select):
    def __init__(self, parent):
        options = [
            discord.SelectOption(label="Gunner", value="gunner", emoji="🎯"),
            discord.SelectOption(label="Driver", value="driver", emoji="🚗")
        ]
        super().__init__(placeholder="Select role to offer", options=options)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        self.parent.selected_role = self.values[0]
        await interaction.response.send_message(
            f"✅ Selected role: {self.values[0].title()}\nNow click Send Invite.",
            ephemeral=True
        )

class SendInviteButton(Button):
    def __init__(self, parent):
        super().__init__(label="📨 Send Invite", style=discord.ButtonStyle.success)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not self.parent.selected_user:
            await interaction.response.send_message("❌ Please select a user first.", ephemeral=True)
            return
        
        if not self.parent.selected_role:
            await interaction.response.send_message("❌ Please select a role first.", ephemeral=True)
            return
        
        # Get the cog instance to call process_crew_invite
        cog = interaction.client.get_cog('CrewManagement')
        await cog.process_crew_invite(
            interaction, 
            self.parent.crew, 
            self.parent.selected_user, 
            self.parent.selected_role
        )

# Pagination for crew list
class CrewListPaginationView(View):
    def __init__(self, cog, guild: discord.Guild, current_page: int):
        super().__init__(timeout=TIMEOUTS["view"])
        self.cog = cog
        self.guild = guild
        self.current_page = current_page
        
        self.add_item(PreviousPageButton(self))
        self.add_item(NextPageButton(self))

class PreviousPageButton(Button):
    def __init__(self, parent):
        super().__init__(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if self.parent.current_page <= 1:
            await interaction.response.send_message("❌ Already on first page.", ephemeral=True)
            return
        
        new_page = self.parent.current_page - 1
        crews = self.parent.cog.get_all_guild_crews(interaction.guild.id, new_page)
        
        if not crews:
            await interaction.response.send_message("❌ No crews on previous page.", ephemeral=True)
            return
        
        embed = self.parent.cog.build_crew_list_embed(crews, new_page, self.parent.guild)
        self.parent.current_page = new_page
        
        await interaction.response.send_message(embed=embed, view=self.parent, ephemeral=True)

class NextPageButton(Button):
    def __init__(self, parent):
        super().__init__(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        new_page = self.parent.current_page + 1
        crews = self.parent.cog.get_all_guild_crews(interaction.guild.id, new_page)
        
        if not crews:
            await interaction.response.send_message("❌ No more crews to display.", ephemeral=True)
            return
        
        embed = self.parent.cog.build_crew_list_embed(crews, new_page, self.parent.guild)
        self.parent.current_page = new_page
        
        await interaction.response.send_message(embed=embed, view=self.parent, ephemeral=True)

# Original UI Components for Crew Management

class CrewSelectionView(View):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.guild = guild
        self.add_item(CrewSelectDropdown(crews, guild))

class CrewSelectDropdown(Select):
    def __init__(self, crews: List[Dict], guild: discord.Guild):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description=f"W: {crew['wins']} L: {crew['losses']}"
            )
            for crew in crews[:25]  # Discord limit
        ]
        
        super().__init__(placeholder="Select a crew to view", options=options)
        self.crews = {crew['id']: crew for crew in crews}
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        # Build crew info embed
        cog = interaction.client.get_cog('CrewManagement')
        embed = cog.build_crew_info_embed(crew, self.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CrewInviteSelectionView(View):
    def __init__(self, crews: List[Dict], target_user: discord.Member, role: str):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crews = crews
        self.target_user = target_user
        self.role = role
        self.add_item(CrewInviteDropdown(crews, target_user, role))

class CrewInviteDropdown(Select):
    def __init__(self, crews: List[Dict], target_user: discord.Member, role: str):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description=f"Invite {target_user.display_name} as {role}"
            )
            for crew in crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to invite to", options=options)
        self.crews = {crew['id']: crew for crew in crews}
        self.target_user = target_user
        self.role = role

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        # Get the cog instance to call process_crew_invite
        cog = interaction.client.get_cog('CrewManagement')
        await cog.process_crew_invite(interaction, crew, self.target_user, self.role)

class CrewInvitationView(View):
    def __init__(self, crew: Dict, role: str, commander: discord.Member, target_user: discord.Member, db: EventDatabase):
        super().__init__(timeout=TIMEOUTS["recruitment_offer"])
        self.crew = crew
        self.role = role
        self.commander = commander
        self.target_user = target_user
        self.db = db
        
        self.add_item(AcceptCrewInviteButton(self))
        self.add_item(DeclineCrewInviteButton(self))

class AcceptCrewInviteButton(Button):
    def __init__(self, parent):
        super().__init__(label="✅ Accept", style=discord.ButtonStyle.success)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent.target_user:
            await interaction.response.send_message("❌ This invitation is not for you.", ephemeral=True)
            return
        
        # Update database
        conn = sqlite3.connect(self.parent.db.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        field_name = f"{self.parent.role}_id"
        cursor.execute(f'''
            UPDATE persistent_crews 
            SET {field_name} = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (self.parent.target_user.id, self.parent.crew['id']))
        
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🎉 Joined Crew!",
            description=f"You've joined **{self.parent.crew['crew_name']}** as {self.parent.role}!",
            color=COLORS["success"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Notify commander
        try:
            commander_embed = discord.Embed(
                title="✅ Invitation Accepted!",
                description=f"{self.parent.target_user.mention} joined your crew as {self.parent.role}!",
                color=COLORS["success"]
            )
            await self.parent.commander.send(embed=commander_embed)
        except discord.Forbidden:
            pass
        
        # Disable view
        for item in self.parent.children:
            item.disabled = True
        await interaction.edit_original_response(view=self.parent)

class DeclineCrewInviteButton(Button):
    def __init__(self, parent):
        super().__init__(label="❌ Decline", style=discord.ButtonStyle.danger)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent.target_user:
            await interaction.response.send_message("❌ This invitation is not for you.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ Invitation Declined",
            description=f"You declined the invitation to join **{self.parent.crew['crew_name']}**.",
            color=COLORS["error"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Notify commander
        try:
            commander_embed = discord.Embed(
                title="❌ Invitation Declined",
                description=f"{self.parent.target_user.mention} declined your crew invitation.",
                color=COLORS["error"]
            )
            await self.parent.commander.send(embed=commander_embed)
        except discord.Forbidden:
            pass
        
        # Disable view
        for item in self.parent.children:
            item.disabled = True
        await interaction.edit_original_response(view=self.parent)

class CrewEditView(View):
    def __init__(self, crew: Dict):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crew = crew
        
        self.add_item(EditCrewNameButton(self))
        self.add_item(EditCrewDescriptionButton(self))
        self.add_item(RemoveCrewMemberButton(self))

class EditCrewNameButton(Button):
    def __init__(self, parent):
        super().__init__(label="📝 Edit Name", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditCrewNameModal(self.parent.crew))

class EditCrewDescriptionButton(Button):
    def __init__(self, parent):
        super().__init__(label="📄 Edit Description", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditCrewDescriptionModal(self.parent.crew))

class RemoveCrewMemberButton(Button):
    def __init__(self, parent):
        super().__init__(label="👤 Remove Member", style=discord.ButtonStyle.danger)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # Show dropdown to select member to remove
        members = []
        if self.parent.crew['gunner_id']:
            members.append(('gunner', self.parent.crew['gunner_id']))
        if self.parent.crew['driver_id']:
            members.append(('driver', self.parent.crew['driver_id']))
        
        if not members:
            await interaction.response.send_message("❌ No members to remove.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            view=RemoveCrewMemberView(self.parent.crew, members), 
            ephemeral=True
        )

class EditCrewNameModal(Modal):
    def __init__(self, crew: Dict):
        super().__init__(title="Edit Crew Name")
        self.crew = crew
        
        self.name_input = TextInput(
            label="New Crew Name",
            placeholder="Enter new crew name...",
            default=crew['crew_name'],
            max_length=30
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        
        if not new_name:
            await interaction.response.send_message("❌ Crew name cannot be empty.", ephemeral=True)
            return
        
        # Update database
        from utils.database import EventDatabase
        db = EventDatabase()
        
        try:
            conn = sqlite3.connect(db.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE persistent_crews 
                SET crew_name = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (new_name, self.crew['id']))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="✅ Crew Name Updated",
                description=f"Crew name changed to **{new_name}**",
                color=COLORS["success"]
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except sqlite3.IntegrityError:
            await interaction.response.send_message(
                f"❌ A crew named '{new_name}' already exists.", 
                ephemeral=True
            )

class EditCrewDescriptionModal(Modal):
    def __init__(self, crew: Dict):
        super().__init__(title="Edit Crew Description")
        self.crew = crew
        
        self.description_input = TextInput(
            label="Crew Description",
            placeholder="Enter crew description...",
            default=crew.get('description', ''),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_description = self.description_input.value.strip() or None
        
        # Update database
        from utils.database import EventDatabase
        db = EventDatabase()
        
        conn = sqlite3.connect(db.db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE persistent_crews 
            SET description = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (new_description, self.crew['id']))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Description Updated",
            description="Crew description has been updated.",
            color=COLORS["success"]
        )
        
        if new_description:
            embed.add_field(name="New Description", value=new_description, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CrewEditSelectionView(View):
    def __init__(self, crews: List[Dict]):
        super().__init__(timeout=TIMEOUTS["view"])
        self.add_item(CrewEditDropdown(crews))

class CrewEditDropdown(Select):
    def __init__(self, crews: List[Dict]):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description="Edit this crew"
            )
            for crew in crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to edit", options=options)
        self.crews = {crew['id']: crew for crew in crews}

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        await interaction.response.send_message(view=CrewEditView(crew), ephemeral=True)

class CrewLeaveSelectionView(View):
    def __init__(self, crews: List[Dict]):
        super().__init__(timeout=TIMEOUTS["view"])
        self.add_item(CrewLeaveDropdown(crews))

class CrewLeaveDropdown(Select):
    def __init__(self, crews: List[Dict]):
        options = [
            discord.SelectOption(
                label=crew['crew_name'],
                value=str(crew['id']),
                description="Leave this crew"
            )
            for crew in crews[:25]
        ]
        
        super().__init__(placeholder="Select crew to leave", options=options)
        self.crews = {crew['id']: crew for crew in crews}

    async def callback(self, interaction: discord.Interaction):
        crew_id = int(self.values[0])
        crew = self.crews[crew_id]
        
        # Get the cog instance
        cog = interaction.client.get_cog('CrewManagement')
        await cog.process_crew_leave(interaction, crew)

class CrewDisbandConfirmView(View):
    def __init__(self, crew: Dict, db: EventDatabase):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crew = crew
        self.db = db
        
        self.add_item(ConfirmDisbandButton(self))
        self.add_item(CancelDisbandButton(self))

class ConfirmDisbandButton(Button):
    def __init__(self, parent):
        super().__init__(label="✅ Disband Crew", style=discord.ButtonStyle.danger)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # Mark crew as inactive
        conn = sqlite3.connect(self.parent.db.db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE persistent_crews 
            SET active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (self.parent.crew['id'],))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="💥 Crew Disbanded",
            description=f"**{self.parent.crew['crew_name']}** has been disbanded.",
            color=COLORS["error"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CancelDisbandButton(Button):
    def __init__(self, parent):
        super().__init__(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ Cancelled",
            description="Crew disbanding cancelled.",
            color=COLORS["neutral"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RemoveCrewMemberView(View):
    def __init__(self, crew: Dict, members: List[tuple]):
        super().__init__(timeout=TIMEOUTS["view"])
        self.crew = crew
        self.add_item(RemoveMemberDropdown(crew, members))

class RemoveMemberDropdown(Select):
    def __init__(self, crew: Dict, members: List[tuple]):
        options = [
            discord.SelectOption(
                label=f"Remove {role.title()}",
                value=role,
                description=f"Remove the {role} from the crew"
            )
            for role, user_id in members
        ]
        
        super().__init__(placeholder="Select member to remove", options=options)
        self.crew = crew
        self.members = {role: user_id for role, user_id in members}

    async def callback(self, interaction: discord.Interaction):
        role_to_remove = self.values[0]
        
        # Update database
        from utils.database import EventDatabase
        db = EventDatabase()
        
        conn = sqlite3.connect(db.db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE persistent_crews 
            SET {role_to_remove}_id = NULL, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (self.crew['id'],))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Member Removed",
            description=f"The {role_to_remove} has been removed from **{self.crew['crew_name']}**.",
            color=COLORS["success"]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CrewManagement(bot))
