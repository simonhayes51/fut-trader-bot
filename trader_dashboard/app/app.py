import os
import json
from flask import Flask, redirect, url_for, session, render_template
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from datetime import datetime
import matplotlib.pyplot as plt

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
oauth = OAuth(app)

discord = oauth.register(
    name='discord',
    client_id=os.getenv("DISCORD_CLIENT_ID"),
    client_secret=os.getenv("DISCORD_CLIENT_SECRET"),
    access_token_url='https://discord.com/api/oauth2/token',
    authorize_url='https://discord.com/api/oauth2/authorize',
    api_base_url='https://discord.com/api/',
    client_kwargs={'scope': 'identify'}
)

PORTFOLIO_PATH = "portfolio_data"

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return discord.authorize_redirect(os.getenv("DISCORD_REDIRECT_URI"))

@app.route('/callback')
def callback():
    token = discord.authorize_access_token()
    user = discord.get('users/@me').json()
    session['user'] = {
        'id': user['id'],
        'username': f"{user['username']}#{user['discriminator']}"
    }
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    user_id = session['user']['id']
    path = f"{PORTFOLIO_PATH}/{user_id}.json"

    if not os.path.exists(path):
        data = {"starting_balance": 0, "trades": []}
    else:
        with open(path) as f:
            data = json.load(f)

    total_profit = sum(t["profit"] for t in data["trades"])
    balance = data["starting_balance"] + total_profit
    trade_count = len(data["trades"])

    # Generate profit graph
    timestamps = []
    values = []
    balance_tracker = data["starting_balance"]

    for t in sorted(data["trades"], key=lambda x: x["timestamp"]):
        balance_tracker += t["profit"]
        timestamps.append(datetime.fromisoformat(t["timestamp"]))
        values.append(balance_tracker)

    graph_path = f"static/{user_id}_graph.png"
    if timestamps:
        fig, ax = plt.subplots()
        ax.plot(timestamps, values, marker='o', color='lime')
        ax.set_title("Coin Balance Over Time")
        ax.set_ylabel("Coins")
        ax.set_xlabel("Time")
        ax.grid(True)
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close(fig)
    else:
        graph_path = None

    return render_template("dashboard.html",
                           user=session['user'],
                           trades=data["trades"][-5:][::-1],
                           total_profit=total_profit,
                           balance=balance,
                           trade_count=trade_count,
                           graph_path=graph_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

