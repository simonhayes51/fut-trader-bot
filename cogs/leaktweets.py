import os
import json
import discord
import snscrape.modules.twitter as sntwitter
from discord.ext import commands, tasks

CONFIG_FILE = "leak_config.json"
SEEN_FILE = "tweet_seen.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

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
        print("🔄 Checking Twitter accounts...")
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            sources = self.config.get(guild_id, [])
            for source in sources:
                username = source["username"]
                include = [kw.lower() for kw in source.get("include_keywords", [])]
                exclude = [kw.lower() for kw in source.get("exclude_keywords", [])]
                channel = self.bot.get_channel(source["channel_id"])
                role_mention = source.get("ping", "")
                last_seen = self.seen.get(guild_id, {}).get(username)

                try:
                    for tweet in sntwitter.TwitterUserScraper(username).get_items():
                        tweet_id = str(tweet.id)
                        if tweet_id == last_seen:
                            break

                        text = tweet.content.lower()
                        if include and not any(kw in text for kw in include):
                            continue
                        if exclude and any(kw in text for kw in exclude):
                            continue

                        embed = discord.Embed(
                            title=f"📢 New tweet from @{username}",
                            url=f"https://x.com/{username}/status/{tweet.id}",
                            color=discord.Color.blue()
                        )

                        tweet_link = f"https://x.com/{username}/status/{tweet.id}"
                        full_text = f"{role_mention}\n{tweet.content}\n{tweet_link}"

                        if channel:
                            await channel.send(embed=embed)
                            await channel.send(full_text)
                            print(f"✅ Posted tweet from @{username}")

                        self.seen.setdefault(guild_id, {})[username] = tweet_id
                        save_json(SEEN_FILE, self.seen)
                        break
                except Exception as e:
                    print(f"❌ Error scraping @{username}: {e}")

    @scrape_tweets.before_loop
    async def before_scrape(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(LeakTweets(bot))