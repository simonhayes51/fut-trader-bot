import os
import discord
import logging
import asyncpg
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # Optional: for uptime pings

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

# Database connection pools (shared with main app)
pool = None
player_pool = None

class FUTBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        """Initialize database connections and sync commands"""
        global pool, player_pool
        
        # Database setup - same as main app
        DATABASE_URL = os.getenv("DATABASE_URL")
        PLAYER_DATABASE_URL = os.getenv("PLAYER_DATABASE_URL", DATABASE_URL)
        
        if not DATABASE_URL:
            logging.error("❌ DATABASE_URL environment variable is missing!")
            return
            
        try:
            # Create connection pools
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            player_pool = await asyncpg.create_pool(PLAYER_DATABASE_URL, min_size=1, max_size=5) if PLAYER_DATABASE_URL != DATABASE_URL else pool
            
            # Store pools on bot for cog access
            self.pool = pool
            self.player_pool = player_pool
            
            logging.info("✅ Database connections established")
            
        except Exception as e:
            logging.error(f"❌ Failed to setup database connections: {e}")
            return
            
        # Load cogs
        await self.load_cogs()
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logging.info(f"🔁 Globally synced {len(synced)} slash command(s)")
        except Exception as e:
            logging.error(f"❌ Failed to sync slash commands: {e}")
    
    async def close(self):
        """Clean up connections on shutdown"""
        global pool, player_pool
        
        if pool:
            await pool.close()
        if player_pool and player_pool != pool:
            await player_pool.close()
            
        await super().close()
    
    async def load_cogs(self):
        """Load all cogs with better error handling"""
        cogs = [
            "cogs.pricecheck",
            "cogs.trending",
            "cogs.taxcalc",
            "cogs.setupsniping", 
            "cogs.submitfilter",
            "cogs.postatrade",
            "cogs.portfolio",
            "cogs.sbcsolve",
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logging.info(f"📦 Loaded {cog}")
            except Exception as e:
                logging.error(f"❌ Failed to load {cog}: {e}")

# Set up the bot
bot = FUTBot()

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user.name} (ID: {bot.user.id})")
    logging.info(f"🌐 Connected to {len(bot.guilds)} guilds")

# Global error handler for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.", 
            ephemeral=True
        )
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", 
            ephemeral=True
        )
    else:
        logging.error(f"Slash command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while processing your command.", 
                ephemeral=True
            )

# Global error handler for regular commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    else:
        logging.error(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing your command.")

# Test command
@bot.tree.command(name="ping", description="Replies with pong!")
async def ping(interaction: discord.Interaction):
    logging.info(f"✅ /ping command used by {interaction.user} in {interaction.guild}")
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")

# Admin command to reload cogs
@bot.tree.command(name="reload", description="🔄 Reload a specific cog (Admin only)")
@app_commands.describe(cog="Name of the cog to reload (e.g., pricecheck)")
async def reload_cog(interaction: discord.Interaction, cog: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return

    try:
        await bot.reload_extension(f"cogs.{cog}")
        await interaction.response.send_message(f"✅ Reloaded `{cog}` cog successfully!")
        logging.info(f"🔄 Reloaded {cog} cog by {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to reload `{cog}`: {str(e)}")
        logging.error(f"❌ Failed to reload {cog}: {e}")

# Database health check command
@bot.tree.command(name="dbstatus", description="Check database connection status (Admin only)")
async def db_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return
    
    try:
        # Test main database
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
        
        # Test player database
        async with player_pool.acquire() as conn:
            player_count = await conn.fetchval("SELECT COUNT(*) FROM fut_players")
        
        embed = discord.Embed(
            title="🗄️ Database Status",
            color=discord.Color.green(),
            description="All database connections are healthy"
        )
        embed.add_field(name="Main DB", value="✅ Connected", inline=True)
        embed.add_field(name="Player DB", value="✅ Connected", inline=True)
        embed.add_field(name="Players in DB", value=f"{player_count:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="🗄️ Database Status",
            color=discord.Color.red(),
            description=f"Database connection error: {str(e)}"
        )
        await interaction.response.send_message(embed=embed)

# Graceful shutdown handlers
@bot.event
async def on_disconnect():
    logging.info("🔌 Bot disconnected")

@bot.event
async def on_connect():
    logging.info("🔗 Bot connected to Discord")

# Keep alive server (optional)
if os.getenv("KEEP_ALIVE", "false").lower() == "true":
    keep_alive()

# Run the bot
def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logging.error("❌ DISCORD_TOKEN environment variable is missing!")
        return

    try:
        bot.run(token)
    except discord.LoginFailure:
        logging.error("❌ Invalid bot token!")
    except Exception as e:
        logging.error(f"❌ Bot failed to start: {e}")

if __name__ == "__main__":
    main()
