import discord
from discord.ext import commands, tasks
from discord import app_commands
import feedparser
import asyncio
import os
import json
from datetime import datetime

# Config constants
FEED_FILE = "twitter_feeds.json"
SEEN_FILE = "tweet_leak_storage.json"
CHANNEL_FILE = "leak_channel_config.json"
KEYWORDS = ["leak", "sbc", "stats", "dynamic", "promo"]
CHECK_INTERVAL = 180  # seconds

# Utility functions
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"💾 Saved data to {filename}")

def is_admin_or_owner(member: discord.Member) -> bool:
    if member.guild and member.id == member.guild.owner_id:
        return True
    allowed_roles = ["admin", "owner"]
    return any(role.name.lower() in allowed_roles for role in member.roles)

class LeakTweets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feeds = load_json(FEED_FILE)
        self.seen = load_json(SEEN_FILE)
        self.channel_config = load_json(CHANNEL_FILE)
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_tweets(self):
        print("🔄 Checking tweet feeds...")
        for username, feed_url in self.feeds.items():
            try:
                parsed = feedparser.parse(feed_url)
                if not parsed.entries:
                    continue

                for entry in parsed.entries:
                    tweet_id = entry.id
                    content = entry.title.lower()

                    if tweet_id in self.seen.get(username, []):
                        continue
                    if not any(kw in content for kw in KEYWORDS):
                        continue

                    self.seen.setdefault(username, []).append(tweet_id)
                    save_json(SEEN_FILE, self.seen)

                    embed = discord.Embed(
                        title=f"📢 New tweet from @{username}",
                        description=f"> {entry.title}",
                        url=entry.link,
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(text="Filtered by: leak, sbc, stats, dynamic, promo")

                    for guild in self.bot.guilds:
                        channel_id = self.channel_config.get(str(guild.id))
                        if not channel_id:
                            continue
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(embed=embed)
                            print(f"✅ Posted tweet from @{username} in {channel.name}")

            except Exception as e:
                print(f"❌ Error checking @{username}: {e}")

    @check_tweets.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setleakchannel", description="📍 Set the channel for FUT leak tweet alerts.")
    @app_commands.describe(channel="Channel to send leaks to")
    async def setleakchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can set the leak channel.", ephemeral=True)
            return
        guild_id = str(interaction.guild_id)
        self.channel_config[guild_id] = channel.id
        save_json(CHANNEL_FILE, self.channel_config)
        await interaction.response.send_message(f"✅ Leak tweets will now be posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="addfeed", description="➕ Add a Twitter RSS feed to track.")
    @app_commands.describe(username="Twitter handle (no @)", feed_url="RSS feed URL for the account")
    async def addfeed(self, interaction: discord.Interaction, username: str, feed_url: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can add feeds.", ephemeral=True)
            return
        self.feeds[username] = feed_url
        save_json(FEED_FILE, self.feeds)
        await interaction.response.send_message(f"✅ Now tracking tweets from @{username}", ephemeral=True)

    @app_commands.command(name="removefeed", description="❌ Remove a tracked Twitter account.")
    @app_commands.describe(username="Twitter handle to stop tracking")
    async def removefeed(self, interaction: discord.Interaction, username: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can remove feeds.", ephemeral=True)
            return
        if username not in self.feeds:
            await interaction.response.send_message(f"⚠️ @{username} is not currently tracked.", ephemeral=True)
            return
        del self.feeds[username]
        save_json(FEED_FILE, self.feeds)
        await interaction.response.send_message(f"✅ Stopped tracking @{username}.", ephemeral=True)

    @app_commands.command(name="listfeeds", description="📃 Show currently tracked Twitter accounts.")
    async def listfeeds(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can view feeds.", ephemeral=True)
            return
        if not self.feeds:
            await interaction.response.send_message("❌ No Twitter feeds are currently being tracked.", ephemeral=True)
            return
        feed_list = "\n".join([f"**@{k}** → {v}" for k, v in self.feeds.items()])
        await interaction.response.send_message(f"🔍 Currently tracking:\n{feed_list}", ephemeral=True)

    @app_commands.command(name="preloadfeeds", description="📦 Load default FUT leak accounts (Donk, Sheriff, FUTTradersHub).")
    @app_commands.describe(channel="Channel to post in", role="Optional role to ping on each tweet")
    async def preloadfeeds(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can use this command.", ephemeral=True)
            return

        default_feeds = {
            "FUTDonk": "https://rss.app/feeds/NApsCGtBTG9hATPI.xml",
            "FutSheriff": "https://rss.app/feeds/CZnnYcKF0mmAX51f.xml",
            "FUTTradersHub": "https://rss.app/feeds/moWaqUszS3v67GmW.xml"
        }

        guild_id = str(interaction.guild_id)
        self.channel_config[guild_id] = channel.id

        for username, url in default_feeds.items():
            self.feeds[username] = url
            self.seen.setdefault(username, [])

        save_json(FEED_FILE, self.feeds)
        save_json(CHANNEL_FILE, self.channel_config)
        save_json(SEEN_FILE, self.seen)

        await interaction.response.send_message(
            f"✅ Loaded Donk, Sheriff, and FUTTradersHub.\nTweets will be posted in {channel.mention}" +
            (f" and will ping {role.mention}" if role else ""),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(LeakTweets(bot))
