import discord, aiohttp, asyncio, json, os, re
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup

from sbc_core import build_indexes, map_player
from price_fetch_futbin import futbin_price_by_id

PLAYERS_JSON = os.getenv("PLAYERS_JSON", "players_temp.json")
BASE_URL = "https://www.futbin.com"

class SBCSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(PLAYERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.players = data if isinstance(data, list) else list(data.values())
        self.indexes = build_indexes(self.players)

    async def fetch_html(self, session, url):
        async with session.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20) as r:
            return await r.text()

    @app_commands.command(name="sbcsolve", description="List SBCs or solve by name")
    @app_commands.describe(sbcname="Name of the SBC (leave empty to list)", platform="ps/xbox/pc")
    async def sbcsolve(self, interaction: discord.Interaction, sbcname: str=None, platform: str="ps"):
        await interaction.response.defer(thinking=True)
        plat = platform.lower()
        async with aiohttp.ClientSession() as session:
            # If no sbcname, just list
            if not sbcname:
                html = await self.fetch_html(session, f"{BASE_URL}/squad-building-challenges")
                soup = BeautifulSoup(html, "html.parser")
                embed = discord.Embed(title="Current SBCs", colour=discord.Colour.green())
                for row in soup.select("a.sbc_title")[:15]:
                    title = row.get_text(strip=True)
                    url = BASE_URL + row["href"]
                    embed.add_field(name=title, value=f"[Open]({url})", inline=False)
                await interaction.followup.send(embed=embed)
                return

            # find SBC page by name
            html = await self.fetch_html(session, f"{BASE_URL}/squad-building-challenges")
            soup = BeautifulSoup(html, "html.parser")
            link = None
            for a in soup.select("a.sbc_title"):
                if sbcname.lower() in a.get_text(strip=True).lower():
                    link = BASE_URL + a["href"]
                    break
            if not link:
                await interaction.followup.send(f"No SBC found matching “{sbcname}”")
                return

            # parse SBC page, find first community solution table
            html = await self.fetch_html(session, link)
            soup = BeautifulSoup(html, "html.parser")
            players = []
            for row in soup.select("table tbody tr")[:11]:
                cols = [c.get_text(" ", strip=True) for c in row.select("td")]
                if not cols or len(cols) < 2: continue
                name = cols[1]
                rating = int(re.search(r"\d{2,3}", cols[0]).group()) if re.search(r"\d{2,3}", cols[0]) else 0
                players.append({"name": name, "rating": rating})

            # map names to your JSON
            for p in players:
                cands = self.indexes["by_name"].get(p["name"].lower(), [])
                if cands:
                    best = cands[0]
                    p["pid"] = best["pid"]

            # fetch live FUTBIN prices
            price_map = {}
            for p in players:
                if not p.get("pid"): continue
                price_map[p["pid"]] = await futbin_price_by_id(session, str(p["pid"]), plat)

        total = sum(price_map.get(p.get("pid"),0) for p in players if p.get("pid"))
        embed = discord.Embed(
            title=f"SBC: {sbcname}",
            description=f"Platform: {plat.upper()}",
            colour=discord.Colour.green()
        )
        embed.add_field(name="Estimated Total", value=f"{total:,} coins", inline=False)
        lines = []
        for p in players:
            price = price_map.get(p.get("pid"),0)
            lines.append(f"{p['rating']} — {p['name']} • {price:,}")
        embed.add_field(name="XI", value="\n".join(lines)[:1024] or "—", inline=False)
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SBCSolver(bot))
