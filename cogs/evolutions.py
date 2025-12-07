import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional
from datetime import datetime

class Evolutions(commands.Cog):
    """FC26 Evolution tracker and calculator"""

    def __init__(self, bot):
        self.bot = bot

        # FC26 Evolution Requirements (examples - update with actual evos)
        self.evolutions = {
            "Meta Evolution I": {
                "description": "Upgrade low-rated cards to usable meta cards",
                "requirements": {
                    "max_rating": 79,
                    "min_pace": 70,
                    "positions": ["ST", "CF", "LW", "RW", "CAM"]
                },
                "upgrades": {
                    "rating": "+5",
                    "pace": "+10",
                    "shooting": "+15",
                    "dribbling": "+12"
                },
                "objectives": [
                    "Score 15 goals in Squad Battles (Min. Semi-Pro)",
                    "Play 10 matches in Rivals",
                    "Score 5 finesse goals",
                    "Assist 8 goals"
                ]
            },
            "Defensive Wall": {
                "description": "Turn defenders into elite stoppers",
                "requirements": {
                    "max_rating": 82,
                    "min_defending": 75,
                    "positions": ["CB", "LB", "RB", "CDM"]
                },
                "upgrades": {
                    "rating": "+4",
                    "defending": "+12",
                    "physical": "+10",
                    "pace": "+8"
                },
                "objectives": [
                    "Play 12 matches with clean sheets",
                    "Win 8 tackles in a match (3 times)",
                    "Block 15 shots",
                    "Make 20 interceptions"
                ]
            },
            "Playmaker Pro": {
                "description": "Create elite playmakers from mid-tier cards",
                "requirements": {
                    "max_rating": 80,
                    "min_passing": 72,
                    "positions": ["CM", "CAM", "CDM", "CF"]
                },
                "upgrades": {
                    "rating": "+6",
                    "passing": "+14",
                    "dribbling": "+10",
                    "vision": "+15"
                },
                "objectives": [
                    "Assist 20 goals",
                    "Complete 150 passes in Rivals",
                    "Play 8 through balls",
                    "Score 5 long shots"
                ]
            },
            "Pace Demon": {
                "description": "Max out pace for rapid wingers",
                "requirements": {
                    "max_rating": 78,
                    "min_pace": 80,
                    "positions": ["LM", "RM", "LW", "RW", "ST"]
                },
                "upgrades": {
                    "rating": "+5",
                    "pace": "+15",
                    "acceleration": "+18",
                    "agility": "+12"
                },
                "objectives": [
                    "Sprint 50km total",
                    "Score 10 goals on counter attacks",
                    "Beat defenders 30 times",
                    "Play 15 matches"
                ]
            }
        }

    @app_commands.command(name="evolutions", description="🔄 View available FC26 Evolutions")
    async def evolutions_list(self, interaction: discord.Interaction):
        """List all available evolutions"""
        embed = discord.Embed(
            title="🔄 FC26 Evolutions",
            description="Available player evolution paths",
            color=discord.Color.purple()
        )

        for evo_name, evo_data in self.evolutions.items():
            reqs = evo_data["requirements"]
            upgrades = evo_data["upgrades"]

            req_text = f"Max Rating: {reqs.get('max_rating', 'N/A')}\n"
            if "positions" in reqs:
                req_text += f"Positions: {', '.join(reqs['positions'][:3])}"

            upgrade_text = "\n".join([f"{k.title()}: {v}" for k, v in list(upgrades.items())[:4]])

            embed.add_field(
                name=f"⚡ {evo_name}",
                value=f"*{evo_data['description']}*\n\n**Requirements:**\n{req_text}\n\n**Upgrades:**\n{upgrade_text}",
                inline=False
            )

        embed.set_footer(text="FC26 • Evolutions • Use /evodetails for full requirements")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="evodetails", description="📋 Get detailed evolution requirements")
    @app_commands.describe(evolution="Evolution name")
    async def evodetails(self, interaction: discord.Interaction, evolution: str):
        """Show detailed evolution requirements"""
        # Find evolution (case insensitive)
        evo_data = None
        evo_name = None

        for name, data in self.evolutions.items():
            if name.lower() == evolution.lower():
                evo_data = data
                evo_name = name
                break

        if not evo_data:
            await interaction.response.send_message(
                f"❌ Evolution '{evolution}' not found. Use /evolutions to see available evolutions.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔄 {evo_name}",
            description=evo_data["description"],
            color=discord.Color.gold()
        )

        # Requirements
        reqs = evo_data["requirements"]
        req_lines = []
        if "max_rating" in reqs:
            req_lines.append(f"• Max Rating: **{reqs['max_rating']}**")
        if "min_pace" in reqs:
            req_lines.append(f"• Min Pace: **{reqs['min_pace']}**")
        if "min_defending" in reqs:
            req_lines.append(f"• Min Defending: **{reqs['min_defending']}**")
        if "min_passing" in reqs:
            req_lines.append(f"• Min Passing: **{reqs['min_passing']}**")
        if "positions" in reqs:
            req_lines.append(f"• Positions: **{', '.join(reqs['positions'])}**")

        embed.add_field(name="📋 Requirements", value="\n".join(req_lines), inline=False)

        # Upgrades
        upgrades = evo_data["upgrades"]
        upgrade_lines = [f"• {k.title()}: **{v}**" for k, v in upgrades.items()]
        embed.add_field(name="📈 Stat Upgrades", value="\n".join(upgrade_lines), inline=False)

        # Objectives
        objectives = evo_data["objectives"]
        obj_text = "\n".join([f"{i+1}. {obj}" for i, obj in enumerate(objectives)])
        embed.add_field(name="🎯 Objectives to Complete", value=obj_text, inline=False)

        # Tips
        tips = """
        **💡 Evolution Tips:**
        • Complete in Squad Battles first (easier)
        • Use Loan version to test if you like the upgrade
        • Check Futbin for best evolution candidates
        • Some objectives can overlap (multitasking)
        • Don't start if you can't finish (wastes XP)
        """
        embed.add_field(name="⚠️ Pro Tips", value=tips, inline=False)

        embed.set_footer(text="FC26 • Evolution Guide")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="evocalc", description="🧮 Calculate if a player can be evolved")
    @app_commands.describe(
        current_rating="Player's current rating",
        current_pace="Player's pace stat",
        position="Player's position"
    )
    async def evocalc(self, interaction: discord.Interaction, current_rating: int, current_pace: int, position: str):
        """Check which evolutions a player qualifies for"""
        position = position.upper()

        eligible = []

        for evo_name, evo_data in self.evolutions.items():
            reqs = evo_data["requirements"]

            # Check rating
            if "max_rating" in reqs and current_rating > reqs["max_rating"]:
                continue

            # Check pace
            if "min_pace" in reqs and current_pace < reqs["min_pace"]:
                continue

            # Check position
            if "positions" in reqs and position not in reqs["positions"]:
                continue

            # Check other stats (would need to be passed in for full check)
            # For now, assume eligible if passed basic checks

            eligible.append((evo_name, evo_data))

        embed = discord.Embed(
            title="🧮 Evolution Calculator",
            description=f"Evolutions for: **{current_rating} OVR {position}** (Pace: {current_pace})",
            color=discord.Color.green() if eligible else discord.Color.red()
        )

        if not eligible:
            embed.add_field(
                name="❌ No Eligible Evolutions",
                value="This player doesn't meet requirements for any current evolutions.\n\nTry a different player or wait for new evolutions!",
                inline=False
            )
        else:
            for evo_name, evo_data in eligible:
                upgrades = evo_data["upgrades"]
                final_rating = current_rating + int(upgrades.get("rating", "+0").replace("+", ""))

                value = f"*{evo_data['description']}*\n\n"
                value += f"**After Evolution:** {final_rating} OVR\n"
                value += f"**Key Upgrades:** {upgrades.get('pace', 'N/A')} Pace, "
                value += f"{list(upgrades.values())[1] if len(upgrades) > 1 else 'N/A'}\n"
                value += f"**Objectives:** {len(evo_data['objectives'])} to complete"

                embed.add_field(name=f"✅ {evo_name}", value=value, inline=False)

        embed.set_footer(text="FC26 • Evolution Calculator • Use /evodetails for full requirements")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bestevo", description="💎 Find best evolution candidates")
    @app_commands.describe(evolution="Evolution name")
    async def bestevo(self, interaction: discord.Interaction, evolution: str):
        """Suggest best players for specific evolution"""
        # Find evolution
        evo_data = None
        evo_name = None

        for name, data in self.evolutions.items():
            if name.lower() == evolution.lower():
                evo_data = data
                evo_name = name
                break

        if not evo_data:
            await interaction.response.send_message(
                f"❌ Evolution '{evolution}' not found.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"💎 Best Players for {evo_name}",
            description="Top candidates for this evolution path",
            color=discord.Color.gold()
        )

        # Example recommendations (in production, would query database)
        if "meta" in evo_name.lower():
            suggestions = [
                {"name": "Adama Traore", "rating": 79, "reason": "99 Pace → Elite winger"},
                {"name": "Hwang Hee-chan", "rating": 78, "reason": "Great links, clinical"},
                {"name": "Inaki Williams", "rating": 79, "reason": "Meta body type, pace"},
            ]
        elif "defensive" in evo_name.lower():
            suggestions = [
                {"name": "Sergio Ramos", "rating": 82, "reason": "Icon, perfect stats"},
                {"name": "Joel Matip", "rating": 81, "reason": "Height + pace combo"},
                {"name": "Reece James", "rating": 82, "reason": "Fullback → CB flex"},
            ]
        elif "playmaker" in evo_name.lower():
            suggestions = [
                {"name": "Bruno Fernandes", "rating": 80, "reason": "5* WF, clinical"},
                {"name": "Fabian Ruiz", "rating": 80, "reason": "Body type, links"},
                {"name": "Dani Olmo", "rating": 80, "reason": "Agile dribbler"},
            ]
        else:
            suggestions = [
                {"name": "Check Futbin", "rating": 0, "reason": "Search for players meeting requirements"},
            ]

        for player in suggestions:
            if player["rating"] > 0:
                embed.add_field(
                    name=f"⭐ {player['name']} ({player['rating']} OVR)",
                    value=f"**Why:** {player['reason']}",
                    inline=False
                )

        tips = f"""
        **🔍 How to Find More:**
        • Use Futbin evolution tool
        • Filter by max rating: {evo_data['requirements'].get('max_rating', 'N/A')}
        • Check required positions
        • Look for high pace + weak foot
        • Consider body type (Lengthy/Controlled)
        • Check club/nation for links
        """
        embed.add_field(name="💡 Search Tips", value=tips, inline=False)

        embed.set_footer(text="FC26 • Evolution Candidates")

        await interaction.response.send_message(embed=embed)

    @evodetails.autocomplete("evolution")
    @bestevo.autocomplete("evolution")
    async def _evo_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for evolution names"""
        choices = [
            app_commands.Choice(name=name, value=name)
            for name in self.evolutions.keys()
            if current.lower() in name.lower()
        ]
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Evolutions(bot))
