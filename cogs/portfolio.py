import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt

PORTFOLIO_DATA_PATH = "portfolio_data"
PLAYERS_FILE = "players_temp.json"

# Ensure the data folder exists
if not os.path.exists(PORTFOLIO_DATA_PATH):
    os.makedirs(PORTFOLIO_DATA_PATH)

def get_data_path(user_id):
    return os.path.join(PORTFOLIO_DATA_PATH, f"{user_id}.json")

def load_user_data(user_id):
    path = get_data_path(user_id)
    if not os.path.exists(path):
        return {"user_id": user_id, "starting_balance": 0, "trades": []}
    with open(path, "r") as f:
        return json.load(f)

def save_user_data(user_id, data):
    path = get_data_path(user_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_players():
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

class PortfolioSlash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = load_players()

    async def player_autocomplete(self, interaction: discord.Interaction, current: str):
        results = [
            app_commands.Choice(name=f"{p['name']} ({p['rating']})", value=p["name"])
            for p in self.players if current.lower() in p["name"].lower()
        ]
        return results[:25]

    @app_commands.command(name="setcoins", description="