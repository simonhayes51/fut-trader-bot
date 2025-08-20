import os
import json
import discord
import snscrape.modules.twitter as sntwitter
from discord.ext import commands, tasks
from discord import app_commands

CONFIG_FILE = "global_leak_config.json"
SEEN_FILE = "tweet_seen.json"


def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return [] if filename == CONFIG_FILE else {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def is_admin_or_owner(member: discord.Member) -> bool:
    return member.guild and (member.guild.owner_id == member.id or any(role.permissions.administrator for role in member.roles))


class LeakTweets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_json(CONFIG_FILE)
        self.seen = load_json(SEEN_FILE)
        self.scrape_tweets.start()

    def cog_unload(self):
        self.scrape_tweets.cancel()

    @tasks.loop(minutes=3)
    async def scrape_tweets(self):
        print("🔄 Scraping tweets...")
        for entry in self.config:
            username = entry["username"]
            last_seen = self.seen.get(username)
            try:
                for tweet in sntwitter.TwitterUserScraper(username).get_items():
                    tweet_id = str(tweet.id)
                    if tweet_id == last_seen:
                        break

                    for listener in entry["listeners"]:
                        text = tweet.content.lower()
                        include = [kw.lower() for kw in listener.get("include_keywords", [])]
                        exclude = [kw.lower() for kw in listener.get("exclude_keywords", [])]
                        if include and not any(kw in text for kw in include):
                            continue
                        if exclude and any(kw in text for kw in exclude):
                            continue

                        channel = self.bot.get_channel(int(listener["channel_id"]))
                        ping = listener.get("ping", "")
                        embed = discord.Embed(
                            title=f"📢 New tweet from @{username}",
                            url=f"https://x.com/{username}/status/{tweet.id}",
                            color=discord.Color.blue()
                        )
                        tweet_link = f"https://x.com/{username}/status/{tweet.id}"
                        full_text = f"{ping}\n{tweet.content}\n{tweet_link}"

                        if channel:
                            await channel.send(embed=embed)
                            await channel.send(full_text)
                            print(f"✅ Posted tweet from @{username} to {listener['guild_id']}")

                    self.seen[username] = tweet_id
                    save_json(SEEN_FILE, self.seen)
                    break
            except Exception as e:
                print(f"❌ Error scraping @{username}: {e}")

    @scrape_tweets.before_loop
    async def before_scrape(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="addleak", description="➕ Subscribe to tweet alerts from a Twitter account.")
    @app_commands.describe(
        username="Twitter username (no @)",
        channel="Channel to post in",
        ping="Optional ping (@here, @everyone, or role mention)",
        include_keywords="Comma-separated words to include (optional)",
        exclude_keywords="Comma-separated words to exclude (optional)"
    )
    async def addleak(self, interaction: discord.Interaction, username: str, channel: discord.TextChannel, ping: str = "", include_keywords: str = "", exclude_keywords: str = ""):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only server admins can use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        listener = {
            "guild_id": guild_id,
            "channel_id": str(channel.id),
            "ping": ping.strip(),
            "include_keywords": [kw.strip().lower() for kw in include_keywords.split(",") if kw.strip()] if include_keywords else [],
            "exclude_keywords": [kw.strip().lower() for kw in exclude_keywords.split(",") if kw.strip()] if exclude_keywords else []
        }

        for entry in self.config:
            if entry["username"].lower() == username.lower():
                entry["listeners"] = [l for l in entry["listeners"] if l["guild_id"] != guild_id]
                entry["listeners"].append(listener)
                break
        else:
            self.config.append({
                "username": username,
                "listeners": [listener]
            })

        save_json(CONFIG_FILE, self.config)
        await interaction.response.send_message(f"✅ Now tracking @{username} for this server!", ephemeral=True)

    @app_commands.command(name="removeleak", description="❌ Stop receiving tweets from a tracked Twitter account.")
    @app_commands.describe(username="Twitter username to remove (no @)")
    async def removeleak(self, interaction: discord.Interaction, username: str):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only server admins can use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        removed = False

        for entry in self.config:
            if entry["username"].lower() == username.lower():
                before = len(entry["listeners"])
                entry["listeners"] = [l for l in entry["listeners"] if l["guild_id"] != guild_id]
                removed = before != len(entry["listeners"])

        self.config = [entry for entry in self.config if entry["listeners"]]
        save_json(CONFIG_FILE, self.config)

        if removed:
            await interaction.response.send_message(f"✅ Stopped tracking @{username} for this server.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ @{username} wasn't tracked in this server.", ephemeral=True)

    @app_commands.command(name="listleaks", description="📃 View all Twitter accounts your server is tracking.")
    async def listleaks(self, interaction: discord.Interaction):
        if not is_admin_or_owner(interaction.user):
            await interaction.response.send_message("❌ Only server admins can use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        tracked = [entry["username"] for entry in self.config if any(l["guild_id"] == guild_id for l in entry["listeners"])]

        if not tracked:
            await interaction.response.send_message("❌ This server isn't tracking any accounts.", ephemeral=True)
        else:
            await interaction.response.send_message(f"🔍 This server is tracking:\n• " + "\n• ".join(f"@{u}" for u in tracked), ephemeral=True)


async def setup(bot):
    await bot.add_cog(LeakTweets(bot))