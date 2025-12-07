import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import math

class SquadRating(commands.Cog):
    """Calculate FC26 squad ratings and chemistry"""

    def __init__(self, bot):
        self.bot = bot

    def _calculate_squad_rating(self, player_ratings: List[int]) -> int:
        """
        Calculate squad rating using FC26 formula
        EA uses a weighted average system
        """
        if not player_ratings or len(player_ratings) != 11:
            return 0

        # Sort ratings in descending order
        sorted_ratings = sorted(player_ratings, reverse=True)

        # FC26 uses sum of all ratings with rounding
        total = sum(sorted_ratings)
        average = total / 11

        # Round down, then apply EA's rounding rules
        squad_rating = math.floor(average)

        # EA rounds up if decimal is >= 0.5
        if (average - squad_rating) >= 0.5:
            squad_rating += 1

        return squad_rating

    def _calculate_chemistry_boost(self, base_rating: int, chemistry: int) -> int:
        """
        Calculate chemistry boost for FC26
        Max chemistry is 3 per player, 33 total for squad
        """
        if chemistry <= 0:
            return base_rating

        # Chemistry gives +1 to all stats per level (max +3)
        # This roughly translates to +1 overall per 3 chemistry
        boost = min(chemistry, 3)  # Max 3 chemistry per player
        boosted_rating = base_rating + boost

        # Cap at 99
        return min(boosted_rating, 99)

    @app_commands.command(name="squadrating", description="⚽ Calculate your FC26 squad rating")
    @app_commands.describe(
        r1="Player 1 rating", r2="Player 2 rating", r3="Player 3 rating",
        r4="Player 4 rating", r5="Player 5 rating", r6="Player 6 rating",
        r7="Player 7 rating", r8="Player 8 rating", r9="Player 9 rating",
        r10="Player 10 rating", r11="Player 11 rating"
    )
    async def squadrating(
        self, interaction: discord.Interaction,
        r1: int, r2: int, r3: int, r4: int, r5: int, r6: int,
        r7: int, r8: int, r9: int, r10: int, r11: int
    ):
        """Calculate squad rating from 11 player ratings"""
        ratings = [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11]

        # Validate ratings
        for i, r in enumerate(ratings, 1):
            if r < 1 or r > 99:
                await interaction.response.send_message(
                    f"❌ Player {i} rating must be between 1-99",
                    ephemeral=True
                )
                return

        squad_rating = self._calculate_squad_rating(ratings)

        # Calculate stats
        highest = max(ratings)
        lowest = min(ratings)
        average = sum(ratings) / len(ratings)
        total = sum(ratings)

        # Count ratings by tier
        meta_cards = len([r for r in ratings if r >= 85])
        high_rated = len([r for r in ratings if 80 <= r < 85])
        mid_rated = len([r for r in ratings if 75 <= r < 80])
        low_rated = len([r for r in ratings if r < 75])

        embed = discord.Embed(
            title="⚽ FC26 Squad Rating Calculator",
            description=f"Your squad rating: **{squad_rating}** 🌟",
            color=discord.Color.green() if squad_rating >= 85 else discord.Color.gold() if squad_rating >= 80 else discord.Color.orange()
        )

        # Player ratings breakdown
        sorted_ratings = sorted(ratings, reverse=True)
        ratings_display = " • ".join([f"**{r}**" if r == highest else f"{r}" for r in sorted_ratings])
        embed.add_field(name="📊 Player Ratings (Sorted)", value=ratings_display, inline=False)

        # Stats
        embed.add_field(name="📈 Highest", value=f"{highest}", inline=True)
        embed.add_field(name="📉 Lowest", value=f"{lowest}", inline=True)
        embed.add_field(name="📊 Average", value=f"{average:.1f}", inline=True)

        # Distribution
        distribution = f"🔥 85+: {meta_cards}\n⭐ 80-84: {high_rated}\n📘 75-79: {mid_rated}\n📗 <75: {low_rated}"
        embed.add_field(name="🎯 Rating Distribution", value=distribution, inline=True)

        # Total rating points
        embed.add_field(name="💯 Total Points", value=f"{total}", inline=True)

        # SBC Value estimate
        if squad_rating >= 87:
            sbc_value = "🔥 High-value SBC fodder"
        elif squad_rating >= 84:
            sbc_value = "✅ Good SBC fodder"
        elif squad_rating >= 82:
            sbc_value = "👍 Decent SBC fodder"
        else:
            sbc_value = "⚠️ Low SBC value"

        embed.add_field(name="🎁 SBC Fodder Value", value=sbc_value, inline=True)

        embed.set_footer(text="FC26 • Squad Rating Calculator • Use for SBCs & Squad Building")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sbcrating", description="🎯 Calculate rating needed to reach target squad rating")
    @app_commands.describe(
        target_rating="Target squad rating (e.g. 84)",
        current_players="Current player ratings (comma separated, e.g. '85,84,83,82,81,80,79,78,77,76')"
    )
    async def sbcrating(self, interaction: discord.Interaction, target_rating: int, current_players: str):
        """Calculate what rating is needed for the 11th player"""
        if target_rating < 1 or target_rating > 99:
            await interaction.response.send_message("❌ Target rating must be 1-99", ephemeral=True)
            return

        try:
            ratings = [int(r.strip()) for r in current_players.split(",")]
        except:
            await interaction.response.send_message(
                "❌ Invalid format. Use comma-separated numbers (e.g. '85,84,83,82,81,80,79,78,77,76')",
                ephemeral=True
            )
            return

        if len(ratings) < 1 or len(ratings) > 10:
            await interaction.response.send_message(
                "❌ Please provide 1-10 player ratings",
                ephemeral=True
            )
            return

        # Validate ratings
        for r in ratings:
            if r < 1 or r > 99:
                await interaction.response.send_message(
                    f"❌ All ratings must be between 1-99",
                    ephemeral=True
                )
                return

        needed = 11 - len(ratings)

        # Calculate minimum rating needed
        current_sum = sum(ratings)
        target_sum = target_rating * 11

        # For exact calculation
        if needed == 1:
            required_rating = target_sum - current_sum
            required_rating = max(1, min(99, required_rating))  # Clamp to 1-99

            embed = discord.Embed(
                title="🎯 SBC Rating Calculator",
                description=f"To reach **{target_rating}** squad rating",
                color=discord.Color.blue()
            )

            current_display = ", ".join(str(r) for r in sorted(ratings, reverse=True))
            embed.add_field(name="📋 Current Players", value=current_display, inline=False)
            embed.add_field(name="🎯 Target Rating", value=f"{target_rating}", inline=True)
            embed.add_field(name="📊 Current Sum", value=f"{current_sum}", inline=True)
            embed.add_field(name="🔢 Need to Add", value=f"{needed} player(s)", inline=True)

            if required_rating > 99:
                embed.add_field(
                    name="❌ Result",
                    value=f"Impossible! Even a 99-rated player won't reach {target_rating}",
                    inline=False
                )
                embed.color = discord.Color.red()
            elif required_rating < 1:
                embed.add_field(
                    name="✅ Result",
                    value=f"Already above target! Any player works",
                    inline=False
                )
                embed.color = discord.Color.green()
            else:
                embed.add_field(
                    name="✅ Required Rating",
                    value=f"**{required_rating}** rated player needed",
                    inline=False
                )

                # Suggest some players
                if required_rating >= 90:
                    suggestion = "🔥 Icon/Hero or Top TOTW needed"
                elif required_rating >= 85:
                    suggestion = "⭐ High-rated meta player"
                elif required_rating >= 80:
                    suggestion = "📘 Solid gold card"
                else:
                    suggestion = "📗 Common gold card will do"

                embed.add_field(name="💡 Suggestion", value=suggestion, inline=False)

        else:
            # Multiple players needed - calculate average
            remaining_sum = target_sum - current_sum
            avg_needed = remaining_sum / needed

            embed = discord.Embed(
                title="🎯 SBC Rating Calculator",
                description=f"To reach **{target_rating}** squad rating",
                color=discord.Color.blue()
            )

            current_display = ", ".join(str(r) for r in sorted(ratings, reverse=True))
            embed.add_field(name="📋 Current Players", value=f"{len(ratings)}: {current_display}", inline=False)
            embed.add_field(name="🎯 Target Rating", value=f"{target_rating}", inline=True)
            embed.add_field(name="🔢 Players Needed", value=f"{needed}", inline=True)
            embed.add_field(name="📊 Average Needed", value=f"**{avg_needed:.1f}** per player", inline=True)

            # Example combinations
            examples = []
            if needed == 2:
                # Show some combos
                for r1 in range(99, 74, -5):
                    r2 = (remaining_sum - r1)
                    if 1 <= r2 <= 99:
                        examples.append(f"• {r1} + {r2}")
                        if len(examples) >= 3:
                            break

            if examples:
                embed.add_field(name="💡 Example Combinations", value="\n".join(examples), inline=False)

        embed.set_footer(text="FC26 • SBC Helper • Plan your squad submissions")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="chemboost", description="⚡ Calculate rating boost from chemistry")
    @app_commands.describe(
        base_rating="Player's base rating",
        chemistry="Player chemistry (0-3)"
    )
    async def chemboost(self, interaction: discord.Interaction, base_rating: int, chemistry: int):
        """Calculate chemistry boost"""
        if base_rating < 1 or base_rating > 99:
            await interaction.response.send_message("❌ Rating must be 1-99", ephemeral=True)
            return

        if chemistry < 0 or chemistry > 3:
            await interaction.response.send_message("❌ Chemistry must be 0-3", ephemeral=True)
            return

        boosted = self._calculate_chemistry_boost(base_rating, chemistry)
        boost = boosted - base_rating

        embed = discord.Embed(
            title="⚡ FC26 Chemistry Boost Calculator",
            description="Individual player chemistry effects",
            color=discord.Color.green() if chemistry >= 3 else discord.Color.orange()
        )

        embed.add_field(name="📊 Base Rating", value=f"{base_rating}", inline=True)
        embed.add_field(name="🔗 Chemistry", value=f"{chemistry}/3", inline=True)
        embed.add_field(name="✨ Boosted Rating", value=f"**{boosted}**", inline=True)

        embed.add_field(name="📈 Total Boost", value=f"+{boost} OVR", inline=True)

        # Explain chemistry levels
        chem_explanation = {
            0: "❌ No boost - off-chem player",
            1: "⚠️ +1 to all stats - minimal boost",
            2: "👍 +2 to all stats - decent boost",
            3: "✅ +3 to all stats - max boost!"
        }

        embed.add_field(
            name="💡 What This Means",
            value=chem_explanation.get(chemistry, "Unknown"),
            inline=False
        )

        embed.set_footer(text="FC26 • Chemistry System • Each point gives +1 to all face stats")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SquadRating(bot))
