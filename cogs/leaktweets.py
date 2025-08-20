import discord
from discord.ext import commands, tasks
from discord import app_commands
import feedparser
import asyncio
import os
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup

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


def get_tweet_image(tweet_url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en"
    }
    try:
        response = requests.get(tweet_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        image_tag = soup.find("meta", property="og:image")
        if image_tag and image_tag.get("content"):
            return image_tag["content"]
    except Exception as e:
        print(f"❌ Failed to fetch tweet image: {e}")
    return None


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

                    color_map = {
                        "FUTDonk": 0xFFA500,         # Orange
                        "FutSheriff": 0x800080,      # Purple
                        "FUTTradersHub": 0x32CD32     # Lime Green
                    }
                    color = color_map.get(username, 0x1DA1F2)

                    embed = discord.Embed(
                        description=f"New post by: [@{username}]({entry.link})",
                        url=entry.link,
                        color=color,
                        timestamp=datetime.utcnow()
                    )

                    image_url = get_tweet_image(entry.link)
                    if image_url:
                        embed.set_image(url=image_url)

                    for guild in self.bot.guilds:
                        guild_id = str(guild.id)
                        config = self.config.get(guild_id, [])
                        for source in config:
                            if source["username"].lower() == username.lower():
                                channel = self.bot.get_channel(source["channel_id"])
                                role_mention = f"<@&{source['role_id']}> " if source.get("role_id") else ""
                                if channel:
                                    await channel.send(content=role_mention, embed=embed)
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

    @app_commands.command(name="preloadfeeds", description="⚡ Preload FUT leak feeds into a channel")
    @app_commands.describe(channel="Channel to post in", role="Optional role to ping")
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

        guild_id = str(interaction.guild_id)
        config = []
        for username in default_feeds:
            config.append({
                "username": username,
                "channel_id": channel.id,
                "role_id": role.id if role else None
            })
        self.config[guild_id] = config
        save_json(CONFIG_FILE, self.config)

        await interaction.response.send_message(f"✅ Default feeds loaded and set to post in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="setleakchannel", description="📍 Set the channel and role for FUT leak alerts.")
    @app_commands.describe(channel="Channel to send leaks to", role="Optional role to ping")
    async def setleakchannel(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can set the leak channel.", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        updated_sources = []
        for username in self.feeds:
            updated_sources.append({
                "username": username,
                "channel_id": channel.id,
                "role_id": role.id if role else None
            })
        self.config[guild_id] = updated_sources
        save_json(CONFIG_FILE, self.config)
        await interaction.response.send_message(f"✅ Leak tweets will now be posted in {channel.mention}", ephemeral=True)

    @app_commands.command(name="testleakpost", description="🧪 Test post a FUT leak tweet embed")
    async def testleakpost(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only Admins/Owners can run a test post.", ephemeral=True)
            return

        username = "FUTTradersHub"
        tweet_url = "https://twitter.com/FUTTradersHub/status/123456789"
        test_embed = discord.Embed(
            description=f"New post by: [@{username}]({tweet_url})",
            url=tweet_url,
            color=0x32CD32,
            timestamp=datetime.utcnow()
        )
        test_embed.set_image(url="https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png")
        await interaction.channel.send(embed=test_embed)
        await interaction.response.send_message("✅ Test post sent.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LeakTweets(bot))
