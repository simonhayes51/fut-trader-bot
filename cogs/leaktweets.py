import discord
from discord.ext import commands, tasks
from discord import app_commands
import feedparser
import asyncio
import os
import json
from datetime import datetime

FEED_FILE = "twitter_feeds.json"
SEEN_FILE = "tweet_leak_storage.json"
CHANNEL_FILE = "leak_channel_config.json"
CONFIG_FILE = "leak_config.json"
KEYWORDS = ["leak", "sbc", "stats", "dynamic", "promo"]
CHECK_INTERVAL = 180


def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


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
        self.config = load_json(CONFIG_FILE)
        self.posted_links = {}
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_tweets(self):
        now = datetime.now().strftime("%H:%M")
        print(f"🔄 [leaktweets] Checking feeds... [{now}]")

        for username, feed_url in self.feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    tweet_link = entry.link
                    tweet_title = entry.title
                    content = tweet_title.lower()

                    if not any(kw in content for kw in KEYWORDS):
                        continue

                    if tweet_link in self.posted_links.get(username, []):
                        continue

                    self.posted_links.setdefault(username, []).append(tweet_link)
                    if len(self.posted_links[username]) > 10:
                        self.posted_links[username] = self.posted_links[username][-10:]

                    for guild in self.bot.guilds:
                        guild_id = str(guild.id)
                        config = self.config.get(guild_id, [])
                        for source in config:
                            if source["username"].lower() == username.lower():
                                channel = self.bot.get_channel(source["channel_id"])
                                role_mention = f"<@&{source['role_id']}> " if source.get("role_id") else ""
                                if channel:
                                    await channel.send(content=f"{role_mention}{tweet_link}")
                                    print(f"✅ Posted: {tweet_link}")
            except Exception as e:
                print(f"❌ Error checking {username}: {e}")

    @check_tweets.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="addfeed", description="➕ Add a Twitter RSS feed to track.")
    @app_commands.describe(username="Twitter handle (no @)", feed_url="RSS feed URL for the account")
    async def addfeed(self, interaction: discord.Interaction, username: str, feed_url: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can use this command.", ephemeral=True)
            return
        self.feeds[username] = feed_url
        save_json(FEED_FILE, self.feeds)
        await interaction.response.send_message(f"✅ Now tracking tweets from @{username}", ephemeral=True)

    @app_commands.command(name="removefeed", description="❌ Remove a tracked Twitter account.")
    @app_commands.describe(username="Twitter handle to stop tracking")
    async def removefeed(self, interaction: discord.Interaction, username: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can use this command.", ephemeral=True)
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

    @app_commands.command(name="preloadfeeds", description="⚡ Preload FUT leak feeds")
    @app_commands.describe(channel="Channel to post tweets in", role="Optional role to ping")
    async def preloadfeeds(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can preload feeds.", ephemeral=True)
            return
        default_feeds = {
            "FUTDonk": "https://rss.app/feeds/NApsCGtBTG9hATPI.xml",
            "FutSheriff": "https://rss.app/feeds/CZnnYcKF0mmAX51f.xml",
            "FUTTradersHub": "https://rss.app/feeds/moWaqUszS3v67GmW.xml"
        }
        self.feeds.update(default_feeds)
        save_json(FEED_FILE, self.feeds)

        guild_id = str(interaction.guild.id)
        self.config[guild_id] = []
        for username in default_feeds:
            self.config[guild_id].append({
                "username": username,
                "channel_id": channel.id,
                "role_id": role.id if role else None
            })
        save_json(CONFIG_FILE, self.config)

        await interaction.response.send_message("✅ Default feeds loaded and configured.", ephemeral=True)

    @app_commands.command(name="setleakchannel", description="📍 Set the channel for FUT leak tweet alerts.")
    @app_commands.describe(channel="Channel to send leaks to", role="Optional role to ping")
    async def setleakchannel(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can use this command.", ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        sources = self.config.get(guild_id, [])
        for source in sources:
            source["channel_id"] = channel.id
            source["role_id"] = role.id if role else None
        self.config[guild_id] = sources
        save_json(CONFIG_FILE, self.config)
        await interaction.response.send_message(f"✅ Leak tweets will now be posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="testleakpost", description="🧪 Send a test tweet link to your configured leak channel.")
    async def testleakpost(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        if guild_id not in self.config or not self.config[guild_id]:
            await interaction.response.send_message("⚠️ No configured leak sources to test with.", ephemeral=True)
            return

        source = self.config[guild_id][0]
        channel = self.bot.get_channel(source["channel_id"])
        role_mention = f"<@&{source['role_id']}> " if source.get("role_id") else ""
        test_link = "https://x.com/FutSheriff/status/1790304106826404043"
        if channel:
            await channel.send(content=f"{role_mention}{test_link}")
            await interaction.response.send_message("✅ Test tweet sent.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Could not find the configured channel.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LeakTweets(bot))
