import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import feedparser
import logging
import re

log = logging.getLogger("rssleaks")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

CONFIG_FILE = "global_rssleak_config.json"

class RssLeakTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.last_seen = {}  # feed_url -> last post link
        self.check_rss.start()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {"leaks": []}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)
        log.info(f"📏 Saved config with {len(self.config['leaks'])} accounts.")

    @tasks.loop(seconds=120)
    async def check_rss(self):
        for acc in self.config.get("leaks", []):
            username = acc['username']
            feed_url = acc['rss']
            channel_id = acc['channel_id']
            ping = acc.get('ping')
            include_keywords = acc.get('include_keywords', [])
            exclude_keywords = acc.get('exclude_keywords', [])

            feed = feedparser.parse(feed_url)
            if not feed.entries:
                continue

            latest = feed.entries[0]
            title = latest.title
            link = latest.link

            if feed_url in self.last_seen and self.last_seen[feed_url] == link:
                continue

            self.last_seen[feed_url] = link

            if include_keywords and not any(k.lower() in title.lower() for k in include_keywords):
                continue
            if exclude_keywords and any(k.lower() in title.lower() for k in exclude_keywords):
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            # Post embed and message
            embed = discord.Embed(title=f"📢 New post from @{username}", color=0x2F3136)
            await channel.send(embed=embed)

            msg = f"{f'<@&{ping}>' if ping else ''}\n{link}\n\n{title}"
            await channel.send(msg)
            log.info(f"✅ Posted new RSS from @{username} to {channel.name}")

    @app_commands.command(name="addleak", description="🔔 Track a Twitter/X account via RSS")
    @app_commands.describe(
        username="Twitter/X username",
        rss="RSS feed URL (from rss.app or similar)",
        include_keywords="Comma-separated keywords to include",
        exclude_keywords="Comma-separated keywords to exclude",
        channel="Channel to post updates in",
        ping="Optional role ID to ping"
    )
    async def addleak(self, interaction: discord.Interaction, username: str, rss: str, include_keywords: str, exclude_keywords: str, channel: discord.TextChannel, ping: str = None):
        self.config["leaks"].append({
            "username": username,
            "rss": rss,
            "channel_id": channel.id,
            "ping": ping,
            "include_keywords": [k.strip() for k in include_keywords.split(",") if k.strip()],
            "exclude_keywords": [k.strip() for k in exclude_keywords.split(",") if k.strip()]
        })
        self.save_config()
        await interaction.response.send_message(f"✅ Now tracking @{username} in {channel.mention}", ephemeral=True)

    @app_commands.command(name="removeleak", description="❌ Stop tracking an X account via RSS")
    @app_commands.describe(username="Twitter/X username")
    async def removeleak(self, interaction: discord.Interaction, username: str):
        self.config["leaks"] = [acc for acc in self.config["leaks"] if acc['username'].lower() != username.lower()]
        self.save_config()
        await interaction.response.send_message(f"✅ Stopped tracking @{username}", ephemeral=True)

    @app_commands.command(name="listleaks", description="📄 List tracked accounts")
    async def listleaks(self, interaction: discord.Interaction):
        accounts = self.config.get("leaks", [])
        if not accounts:
            await interaction.response.send_message("ℹ️ No accounts tracked.", ephemeral=True)
            return
        msg = "**Tracked Accounts:**\n"
        for acc in accounts:
            msg += f"- @{acc['username']} → <#{acc['channel_id']}>\n"
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RssLeakTracker(bot))
