# Tank Brawl Scheduler – Copilot Guide
## Architecture & Boot Flow
- `main.py` instantiates `TankBrawlBot`, enables message/member/voice intents, syncs slash commands inside `setup_hook`, and logs both to stdout and `data/logs/bot.log`; add new startup logic here so it benefits from the shared logging/error handling.
- The bot is organized into cogs: `cogs/armor_events.py` schedules events and builds interactive signups, `cogs/map_voting.py` owns long-running map polls, `cogs/crew_management.py` manages persistent crews, and `cogs/admin_tools.py` exposes guild settings plus moderation helpers.
- New cogs must be listed in `TankBrawlBot.initial_extensions` or explicitly loaded before `self.tree.sync()` runs, otherwise slash commands will never register with Discord.
- Interaction-heavy flows live alongside their `discord.ui.View`/Modal classes (e.g., `EventSignupView`, `CrewManagementPanelView`); persistent panels set `timeout=None`, so be intentional about lifecycle and memory when adding new views.

## Persistence & Config
- Core state lives in SQLite `tank_brawl.db` behind `utils/database.EventDatabase`; it auto-creates tables for events, signups, reminder_queue, user_stats, persistent_crews, and guild_settings—rely on its helper methods instead of writing ad-hoc SQL.
- Map votes use a separate `data/votes.db` via `VoteDatabase`; `MapVoting.restore_active_votes()` reloads UI state on reboot, so any schema change must keep those queries compatible.
- Secrets and feature toggles come from `.env` (see `.env.example`); `setup.py` and `quick_start.sh` create the `bot_env` virtualenv, install `requirements.txt`, copy `.env`, and drop `start_bot.sh` for local runs.
- Shared constants (event presets, emoji, timeouts, `MAX_CREWS_PER_TEAM`) live in `utils/config.py` and are imported with `from utils.config import *`; add new knobs there so every cog can consume them consistently.
- `data/logs/bot.log` is created on startup (see `os.makedirs('data/logs', exist_ok=True)`); avoid changing log destinations unless you also update deployment docs (Railway tailing assumes this path).

## Discord Interaction Patterns
- `/schedule_event` immediately calls `interaction.response.defer(ephemeral=True)` and parses EST timestamps with `pytz`; use the same defer-and-validate pattern for any command that touches the database or creates channels.
- `ArmorEvents.create_event_channels()` expects the hard-coded `EVENTS_CATEGORY_ID = 1368336239832338552`; change that constant or make it configurable before testing in a different guild to prevent permission failures.
- Team roles are derived from event titles (`f"{event_title} Allies/Axis/Participant"`) via `assign_event_role` and `remove_event_role`; reuse those helpers instead of rolling custom role logic so cleanup stays automatic.
- `EventSignupView` owns crew slots, commander buttons, and recruitment pools using `MAX_CREWS_PER_TEAM`; extend this view when adding buttons (e.g., spectators) so both UI and persistence stay in sync.
- `ArmorEvents.create_map_vote()` dynamically looks up the `MapVoting` cog and expects a `create_auto_mapvote(event_id, channel, duration_minutes)` coroutine; preserve that contract when modifying either side or short-circuit with a user-facing warning.
- Crew operations favor DM-first messaging with channel fallbacks when `discord.Forbidden` is raised (`CrewManagement.process_crew_invite`); mirror that UX for any feature that pings specific users.

## Workflows & Cross-Cog Practices
- Local loop: run `python setup.py`, edit `.env` with `DISCORD_BOT_TOKEN`, activate `bot_env` (`source bot_env/bin/activate` or `bot_env\Scripts\activate` on Windows), then `python main.py`; `start_bot.sh` is a thin wrapper.
- Railway/Procfile deploys only need `DISCORD_BOT_TOKEN` (and optionally `LOG_LEVEL`), but they still rely on the repo-committed SQLite files, so persist `tank_brawl.db`/`data/votes.db` between releases if you need historical stats.
- Whenever you add admin-facing toggles, update both `EventDatabase.get_guild_settings()` defaults and the UI in `admin_tools.BotSettingsView`, otherwise the buttons will reference missing keys.
- Reminder queues, user stats, and crew records should be updated through `EventDatabase` helpers (`add_reminder`, `update_user_stat`, `get_user_crews`, etc.) so scheduled cleanup jobs (`cleanup_old_data`) remain accurate.
- Long-running background work belongs in cog-level tasks with explicit startup/shutdown (`MapVoting.dynamic_update_task` / `cleanup_task` in `cog_load`/`cog_unload`); follow that template when adding new periodic jobs.
- Cross-cog calls should go through `self.bot.get_cog('Name')` and guard against `None` (as seen when event scheduling checks for MapVoting) to keep the bot resilient when optional modules are disabled.
