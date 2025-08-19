import discord
from discord.ext import commands, tasks
from utils.futbin_api import get_player_price

players_to_track = {
    "Mbappe": 231,
    "Haaland": 276,
    "Vini Jr": 225,
    "Bellingham": 30150
}

class SnipingFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sniping_loop.start()

    def cog_unload(self):
        self.sniping_loop.cancel()

    @tasks.loop(minutes=5)
    async def sniping_loop(self):
        channel = discord.utils.get(self.bot.get_all_channels(), name="sniping-feed")
        if not channel:
            print("No #sniping-feed channel found.")
            return

        for name, pid in players_to_track.items():
            prices = get_player_price(pid)
            if not prices:
                continue
            try:
                ps_price = int(prices["ps"]["LCPrice"].replace(',', ''))
                xbox_price = int(prices["xbox"]["LCPrice"].replace(',', ''))
                avg_price = (ps_price + xbox_price) // 2
                threshold = int(avg_price * 0.92)

                if ps_price < threshold or xbox_price < threshold:
                    embed = discord.Embed(title=f"💸 Snipe Alert: {name}", color=discord.Color.red())
                    embed.add_field(name="PS BIN", value=f"{ps_price:,} coins")
                    embed.add_field(name="Xbox BIN", value=f"{xbox_price:,} coins")
                    embed.set_footer(text="Live data from Futbin")
                    await channel.send(embed=embed)
            except Exception as e:
                print("Sniping error:", e)

async def setup(bot):
    await bot.add_cog(SnipingFeed(bot))