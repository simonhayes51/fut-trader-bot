import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import feedparser
from datetime import datetime

CONFIG_FILE = "leak_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

class LeakTweets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.posted_links = {}  # memory cache to avoid dupes
        self.check_tweets.start()

    def get_feed_url(self, username):
        return f"https://rss.app/feeds/twitter/user/{username}.rss"

    @app_commands.command(name="addleaksource", description="➕ Track a Twitter user and post to a channel.")
    @app_commands.describe(username="Twitter username (without @)", channel="Channel to post in", role="Optional role to ping")
    async def addleaksource(self, interaction: discord.Interaction, username: str, channel: discord.TextChannel, role: discord.Role = None):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need Manage Server permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = []

        self.config[guild_id].append({
            "username": username,
            "channel_id": channel.id,
            "role_id": role.id if role else None
        })
        save_config(self.config)
        await interaction.response.send_message(f"✅ Now tracking tweets from @{username} in {channel.mention}", ephemeral=True)

    @app_commands.command(name="removeleaksource", description="🗑 Remove all leak tweet trackers for this server.")
    async def removeleaksource(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need Manage Server permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        self.config.pop(guild_id, None)
        save_config(self.config)
        await interaction.response.send_message("✅ Removed all tracked leak sources for this server.", ephemeral=True)

    @app_commands.command(name="listleakfeeds", description="📃 List all tracked Twitter usernames for this server.")
    async def listleakfeeds(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        feeds = self.config.get(guild_id, [])
        if not feeds:
            await interaction.response.send_message("ℹ️ No leak sources tracked.", ephemeral=True)
            return

        desc = "\n".join([f"- @{f['username']} → <#{f['channel_id']}>" for f in feeds])
        await interaction.response.send_message(f"📡 Tracking:\n{desc}", ephemeral=True)

    @tasks.loop(minutes=2)
    async def check_tweets(self):
        now = datetime.now().strftime("%H:%M")
        print(f"🔄 [leaktweets] Checking feeds... [{now}]")

        for guild_id, sources in self.config.items():
            for source in sources:
                username = source["username"]
                channel = self.bot.get_channel(source["channel_id"])
                role_mention = f"<@&{source['role_id']}>" if source.get("role_id") else ""

                if not channel:
                    print(f"⚠️ Channel ID {source['channel_id']} not found.")
                    continue

                feed_url = self.get_feed_url(username)
                try:
                    feed = feedparser.parse(feed_url)
                    if not feed.entries:
                        continue

                    latest = feed.entries[0]
                    tweet_link = latest.link
                    tweet_title = latest.title
                    if tweet_link in self.posted_links.get(username, []):
                        continue

                    embed = discord.Embed(
                        title=f"New Tweet from @{username}",
                        description=tweet_title,
                        url=tweet_link,
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text="Twitter Leak Monitor")

                    await channel.send(content=role_mention, embed=embed)
                    print(f"✅ Posted: {tweet_link}")

                    self.posted_links.setdefault(username, []).append(tweet_link)
                    if len(self.posted_links[username]) > 10:
                        self.posted_links[username] = self.posted_links[username][-10:]

                except Exception as e:
                    print(f"❌ Error checking {username}: {e}")

    @check_tweets.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(LeakTweets(bot))
