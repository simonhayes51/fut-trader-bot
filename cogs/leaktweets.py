import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import requests
from bs4 import BeautifulSoup
import logging
import re

log = logging.getLogger("leaktweets")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

CONFIG_FILE = "global_leak_config.json"

class LeakTweets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.last_seen = {}
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
        try:
            url = f"https://x.com/{username}"
            headers = {
                "User-Agent": "Mozilla/5.0",
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")

            tweet_blocks = soup.find_all("div", {"data-testid": "tweet"})
            if not tweet_blocks:
                return None

            tweet = tweet_blocks[0]
            tweet_text = tweet.get_text(separator=" ").strip()
            tweet_link = tweet.find("a", href=re.compile(r"/{}/status/\d+".format(username)))
            if not tweet_link:
                return None

            tweet_id = tweet_link["href"].split("/")[-1]
            return tweet_id, tweet_text

        except Exception as e:
            log.error(f"\u274c Error scraping tweet from @{username}: {e}")
            return None

    @tasks.loop(seconds=60)
    async def check_tweets(self):
        for acc in self.config.get("leaks", []):
            username = acc['username']
            channel_id = acc['channel_id']
            ping = acc.get('ping')
            include_keywords = acc.get('include_keywords', [])
            exclude_keywords = acc.get('exclude_keywords', [])

            result = self.get_latest_tweet(username)
            if not result:
                continue

            tweet_id, tweet_text = result

            if tweet_id == self.last_seen.get(username):
                continue

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
            log.info(f"\u2705 Posted tweet from @{username} to {channel.name}")

    @app_commands.command(name="addleak", description="\ud83d\udd14 Track an X account for leak tweets")
    @app_commands.describe(username="Twitter/X username", channel="Channel to post in", ping="Optional role ID to ping")
    async def addleak(self, interaction: discord.Interaction, username: str, channel: discord.TextChannel, ping: str = None):
        if "leaks" not in self.config:
            self.config["leaks"] = []

        self.config["leaks"].append({
            "username": username,
            "channel_id": channel.id,
            "ping": ping,
            "include_keywords": ["sbc", "leak", "objective"],
            "exclude_keywords": ["test", "promo"]
        })
        self.save_config()
        await interaction.response.send_message(f"\u2705 Now tracking @{username} in {channel.mention}", ephemeral=True)

    @app_commands.command(name="removeleak", description="\u274c Stop tracking an X account")
    @app_commands.describe(username="Twitter/X username")
    async def removeleak(self, interaction: discord.Interaction, username: str):
        if "leaks" in self.config:
            self.config["leaks"] = [acc for acc in self.config["leaks"] if acc['username'].lower() != username.lower()]
            self.save_config()
        await interaction.response.send_message(f"\u2705 Stopped tracking @{username}", ephemeral=True)

    @app_commands.command(name="listleaks", description="\ud83d\udcc4 List tracked accounts")
    async def listleaks(self, interaction: discord.Interaction):
        accounts = self.config.get("leaks", [])
        if not accounts:
            await interaction.response.send_message("\u2139\ufe0f No accounts tracked.", ephemeral=True)
            return
        msg = "**Tracked Accounts:**\n"
        for acc in accounts:
            msg += f"- @{acc['username']} → <#{acc['channel_id']}>\n"
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LeakTweets(bot))