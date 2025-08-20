import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import requests
from bs4 import BeautifulSoup
import logging
import re
import time

log = logging.getLogger("leaktweets")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

CONFIG_FILE = "leak_config.json"

class LeakTweets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.last_seen = {}  # Keep track of last tweet per user
        self.check_tweets.start()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_latest_tweet(self, username):
        url = f"https://x.com/{username}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            scripts = soup.find_all("script")
            
            for script in scripts:
                if "\"tweet\"" in script.text:
                    match = re.search(r'\"id_str\":\"(\d+)\".*?\"full_text\":\"(.*?)\"', script.text)
                    if match:
                        tweet_id, tweet_text = match.groups()
                        tweet_text = tweet_text.encode().decode('unicode_escape')
                        return tweet_id, tweet_text
        except Exception as e:
            log.warning(f"Failed to fetch tweet from @{username}: {e}")
            return None, None

    @tasks.loop(seconds=60)
    async def check_tweets(self):
        for guild_id, accounts in self.config.items():
            for acc in accounts:
                username = acc['username']
                channel_id = acc['channel_id']
                ping = acc.get('ping')
                include_keywords = acc.get('include_keywords', [])
                exclude_keywords = acc.get('exclude_keywords', [])

                tweet_id, tweet_text = self.get_latest_tweet(username)
                if not tweet_id or not tweet_text:
                    continue

                if tweet_id == self.last_seen.get(username):
                    continue  # Already posted

                if include_keywords and not any(k.lower() in tweet_text.lower() for k in include_keywords):
                    continue

                if exclude_keywords and any(k.lower() in tweet_text.lower() for k in exclude_keywords):
                    continue

                self.last_seen[username] = tweet_id
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue

                msg = f"https://x.com/{username}/status/{tweet_id}\n\n{tweet_text}"
                if ping:
                    msg = f"<@&{ping}>\n{msg}"
                await channel.send(msg)

    @app_commands.command(name="addleak", description="🔔 Track an X account for leak tweets")
    @app_commands.describe(username="Twitter/X username", channel="Channel to post in", ping="Optional role ID to ping")
    async def addleak(self, interaction: discord.Interaction, username: str, channel: discord.TextChannel, ping: str = None):
        guild_id = str(interaction.guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = []

        self.config[guild_id].append({
            "username": username,
            "channel_id": channel.id,
            "ping": ping,
            "include_keywords": ["sbc", "leak", "objective"],
            "exclude_keywords": ["test", "promo"]
        })
        self.save_config()
        await interaction.response.send_message(f"✅ Now tracking @{username} in {channel.mention}", ephemeral=True)

    @app_commands.command(name="removeleak", description="❌ Stop tracking an X account")
    @app_commands.describe(username="Twitter/X username")
    async def removeleak(self, interaction: discord.Interaction, username: str):
        guild_id = str(interaction.guild_id)
        if guild_id in self.config:
            self.config[guild_id] = [acc for acc in self.config[guild_id] if acc['username'].lower() != username.lower()]
            self.save_config()
        await interaction.response.send_message(f"✅ Stopped tracking @{username}", ephemeral=True)

    @app_commands.command(name="listleaks", description="📄 List tracked accounts")
    async def listleaks(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        accounts = self.config.get(guild_id, [])
        if not accounts:
            await interaction.response.send_message("ℹ️ No accounts tracked.", ephemeral=True)
            return
        msg = "**Tracked Accounts:**\n"
        for acc in accounts:
            msg += f"- @{acc['username']} → <#{acc['channel_id']}>\n"
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LeakTweets(bot))
