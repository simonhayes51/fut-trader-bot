# Fut Trader Bot and EAFC.Live Community Platform

This repository contains two Discord applications:

1. **Fut Trader Bot** — a Python slash-command bot for FC Ultimate Team prices, trading calculations, market signals, leaks, alerts and SBCs.
2. **EAFC.Live Community Platform** — a separate TypeScript Discord bot, PostgreSQL-backed community system and web dashboard.

They have separate dependencies, environment variables and deployment steps. The community platform is in [`community-platform/`](community-platform/README.md).

> This README describes functionality present in the source. It does not promise that an external data provider, API token, or optional feature is available in every deployment. In particular, price and leak commands depend on their configured data sources.

## Fut Trader Bot (Python)

### Features

- FUTBIN and FUT.GG player price lookups.
- Flip opportunity listings and quick-flip views.
- EA tax, profit, ROI, break-even, bulk-trade, target-profit and investment calculations.
- Player comparison and FUT.GG trending risers/fallers.
- Fodder prices, market overview, content calendar and SBC trading tips.
- Leak feed, source and history views, manual leak submissions, and on-demand scans.
- Price alerts managed by each member.
- SBC lookup and solution details from FUT.GG.
- Trade-tip and sniping-filter sharing.

The main Python entry point loads these cogs: `pricecheck`, `taxcalc`, `playercompare`, `trending`, `leakmonitor`, `flipfinder`, `smartalerts`, `marketintel`, `postatrade`, and `sbcsolve`. A cog that is not loaded by `bot.py` does not become available just because its file exists.

### Commands

| Command | What it does |
| --- | --- |
| `/ping` | Reports the bot's Discord gateway latency. |
| `/reload cog` | Reloads a Python cog; restricted to the server owner or an administrator. |
| `/pricecheck player` | Looks up a player's current FUTBIN price. |
| `/taxcalc buy_price sell_price` | Calculates EA's 5% sale tax, net profit, ROI and break-even. |
| `/bulktax buy_price sell_price quantity` | Calculates after-tax return for multiple copies. |
| `/profitscenarios buy_price sell_prices` | Compares profit at several possible sale prices. |
| `/targetprofit buy_price target_profit` | Calculates the sale price needed for a target profit. |
| `/compare player1 player2` | Compares two players' stats and market details. |
| `/trending` | Shows FUT.GG market risers and fallers. |
| `/flips [budget]` | Finds available trade opportunities, optionally within a budget. |
| `/quickflip` | Shows opportunities aimed at faster resale. |
| `/flipcalc buy_price sell_price` | Calculates profit and return for a single flip. |
| `/investcalc amount return_percent` | Estimates investment growth from an amount and return percentage. |
| `/alert player direction price` | Creates a personal price alert for a player. |
| `/myalerts` | Lists your active price alerts. |
| `/removealert player` | Removes an alert for a player. |
| `/clearalerts` | Removes all of your alerts. |
| `/fodder` | Shows fodder price information and buy/sell signals. |
| `/market` | Gives a short market overview. |
| `/calendar` | Shows the FC content calendar. |
| `/sbctips` | Shows SBC-focused trading guidance. |
| `/leaks` | Shows recent leak entries. |
| `/leaksources` | Shows tracked leak sources and reliability information. |
| `/leakhistory` | Shows historical leak outcomes. |
| `/scannow` | Requests an immediate leak scan. |
| `/submitleak` | Submits a leak for the community feed. |
| `/leakaccounts` | Shows monitored X/Twitter accounts. |
| `/sbcsolve name` | Finds an SBC on FUT.GG and displays requirements and solution information. |
| `/postatrade` | Posts a trade tip with tracker buttons so members can mark `I bought this`, `Watching`, `Passed` or `Sold`; the trader and staff can view who is tracking it. |

Some source files contain additional commands, including FUT.GG price lookup (`/pricecheckgg`), X account feed management (`/addleak`, `/removeleak`, `/listleaks`), snipe tracking (`/addsnipe`, `/removesnipe`, `/snipelist`), `/setupsniping`, and `/submitfilter`. Those cogs are **not loaded by the current `bot.py`**, so those commands are not registered by the default Python bot. Similarly, the source tree contains duplicate/old price-check and trending copies; only the cogs listed above are loaded.

### Python setup

Requirements and dependencies are defined by the Python deployment files in the repository. At minimum, the bot needs Python, the packages imported by its cogs, and a Discord bot token.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set `DISCORD_TOKEN` in the environment or a local `.env` file, then run:

```bash
python bot.py
```

The bot uses Discord slash commands. No message-content intent is enabled by default. Price and market commands also rely on external FUTBIN/FUT.GG access as implemented by the corresponding cog and utility modules.

## EAFC.Live Community Platform (TypeScript)

This is an independent community management and engagement bot with an Express dashboard and PostgreSQL. It is not the Python trading bot. See [`community-platform/README.md`](community-platform/README.md) for deployment and dashboard details.

### Features

- Discord OAuth dashboard, per-guild feature switches, configuration and audit history.
- Welcome messages, auto-role, onboarding verification, self-serve role menus, invite attribution, join/leave tracking and account-age/raid security.
- Reputation kudos, kudos boards, XP/levels, leaderboards, Live Coins, daily rewards, streaks, quests, seasons, achievements, profiles and rewards shop.
- Daily activity engine with a week-one posting rhythm, interactive prompts, button rewards, activity leaderboards and staff pulse summaries.
- Suggestions with voting, private ticket panels, staff ticket assignment/notes/closure and transcripts.
- Giveaways with eligibility conditions, entry bonuses, rerolls and scheduled drawing.
- Staff warnings, history and notes; timeout, kick, ban, purge, slowmode, lock/unlock, nickname and role tools.
- Automod for configured blocked terms/domains, repeated messages, mention spam and invite links; configurable timeout actions.
- Starboard, member birthdays, AFK status, scheduled events/messages, server counters, recaps, booster rewards, counting game and message/report context actions.
- Social feeds from RSS/Atom, Reddit RSS, YouTube RSS, optional official X API polling and authenticated incoming webhooks.
- Premium plans, subscription management, referrals and staff-granted premium access (Stripe configuration required for paid billing).
- Utility commands for polls, emoji management, keyword DMs, bump reminders, server snapshots and Discord member/server/role information.
- Trade-call records and moderation/review controls in the dashboard. The current TypeScript app does not register trade-calculation or trade-call slash commands.

### Slash commands

`[staff]` means Discord permissions are required. Dashboard feature switches may also disable commands or related features for a guild.

#### Community, profile and engagement

| Command | What it does |
| --- | --- |
| `/kudos member type [reason]` | Recognises a member for a trade, helpful answer, contribution or community support. Includes anti-farming limits. |
| `/kudosboard [period] [category]` | Shows kudos rankings by period and category. |
| `/rank [member]` | Shows a member's rank, XP, Live Coins and kudos. |
| `/leaderboard type` | Shows XP, kudos, coins or current-season rankings. |
| `/profile [member]` | Displays a member's community profile. |
| `/achievements [member]` | Shows achievements earned by a member. |
| `/showcase add achievement` | Adds an achievement to your profile showcase. |
| `/showcase remove achievement` | Removes an achievement from your showcase. |
| `/showcase clear` | Clears your achievement showcase. |
| `/wallet` | Shows your Live Coins balance and recent activity. |
| `/daily` | Claims daily Live Coins and streak rewards. |
| `/quests` | Shows daily and weekly quests. |
| `/shop` | Browses available community rewards. |
| `/redeem item` | Spends Live Coins on a shop item. |
| `/season` | Shows the current community season. |
| `/today` | Shows today's automated activity schedule for the server. |
| `/pulse [public]` | Shows today's server pulse: joins, active chatters, messages, activity responses, trade posts, tickets and top contributors. |
| `/birthday set day month [public]` | Saves your birthday and whether it can be announced publicly. |
| `/birthday clear` | Removes your saved birthday. |
| `/afk [reason]` | Sets or clears your AFK status. |
| `/verify` | Starts or completes configured server verification. |
| `/suggest suggestion` | Submits a suggestion to the configured suggestions area for voting. |

#### Tickets, giveaways and server setup

| Command | What it does |
| --- | --- |
| `/ticket type` | Opens a private support, report, appeal, partnership or other ticket. |
| `/ticketstaff claim` `[staff]` | Assigns the current ticket to you. |
| `/ticketstaff note note` `[staff]` | Adds an internal note to the current ticket. |
| `/ticketstaff close reason` `[staff]` | Closes the current ticket and saves a transcript. |
| `/system ticket-panel [channel]` `[staff]` | Publishes the ticket dropdown panel. |
| `/system bot-status [channel]` `[staff]` | Publishes the live bot status panel. |
| `/activity setup [channel] [staff_channel] [leaderboard_channel] [create_channels]` `[staff]` | Installs the week-one daily activity engine. It can use existing channels or create `daily-trading`, `leaderboard` and `staff-pulse`. |
| `/activity schedule` `[staff]` | Shows the configured activity rhythm and destination channels. |
| `/activity pause` `[staff]` | Pauses automated daily activity posts. |
| `/activity resume` `[staff]` | Resumes automated daily activity posts. |
| `/activity postnow type [channel]` `[staff]` | Posts a market watch, price check, flip, discussion, trade-proof, leaderboard or staff-pulse prompt immediately. |
| `/activity settings [channel] [staff_channel] [leaderboard_channel]` `[staff]` | Updates activity engine destinations without recreating the schedule. |
| `/giveaway start prize minutes [options]` `[staff]` | Starts a giveaway. Optional rules include winner count, required/blacklisted roles, blacklisted user, minimum server tenure or level, verification, and premium/booster/level/tenure bonus entries. |
| `/giveaway reroll id` `[staff]` | Selects replacement winner(s) for a completed giveaway. |
| `/serverbrand [name] [logo_url] [banner_url] [footer] [primary_colour] [premium_colour]` `[staff]` | Sets the bot embed branding for this server. |
| `/announce message [tag]` `[staff]` | Posts an announcement as the bot in the current channel, optionally tagging one role. |
| `/post message [tag]` `[staff]` | Posts a regular bot message in the current channel, optionally tagging one role. |
| `/event name minutes_from_now [duration_minutes] [description]` `[staff]` | Creates a Discord scheduled event. |
| `/bumpreminder set channel [minutes] [message]` `[staff]` | Schedules recurring reminders to bump the server directory listing. It posts reminders; a member still performs the directory bump. |
| `/bumpreminder off` `[staff]` | Disables the reminder. |
| `/bumpreminder status` | Shows the current reminder configuration. |
| `/serverbackup create [name]` `[staff]` | Saves a lightweight snapshot of roles, channels and core guild settings. |
| `/serverbackup list` `[staff]` | Lists saved snapshots. |
| `/serverbackup inspect id` `[staff]` | Displays the contents of a saved snapshot. |

#### Moderation and utilities

| Command | What it does |
| --- | --- |
| `/warn member reason` `[staff]` | Records a warning for a member. |
| `/history member` `[staff]` | Shows a member's moderation history. |
| `/note member note` `[staff]` | Adds a private staff note to a member's record. |
| `/timeout member minutes [reason]` `[staff]` | Times out a member for up to 28 days. |
| `/kick member [reason]` `[staff]` | Kicks a member. |
| `/ban member [reason]` `[staff]` | Bans a member. |
| `/purge count` `[staff]` | Deletes up to 100 recent messages. |
| `/slowmode seconds` `[staff]` | Sets channel slowmode; zero disables it. |
| `/lock` `[staff]` | Prevents members from sending messages in the current channel. |
| `/unlock` `[staff]` | Restores message sending in the current channel. |
| `/nick member [nickname]` `[staff]` | Changes or clears a member nickname. |
| `/role member role action` `[staff]` | Adds or removes a role from a member. |
| `/avatar [member]` | Shows a member's avatar. |
| `/userinfo [member]` | Shows member/account information. |
| `/serverinfo` | Shows information about the current server. |
| `/roleinfo role` | Shows information about a server role. |
| `/poll question answers [hours] [multiple]` | Creates a native Discord poll. Separate answers with `|`; duration is 1–168 hours. |
| `/emoji add name image` `[staff]` | Adds an uploaded image as a server emoji. |
| `/emoji remove emoji` `[staff]` | Removes a server emoji by name or ID. |
| `/emoji list` | Lists the server's custom emojis. |
| `/notify add keyword` | DMs you when a keyword or phrase is mentioned in the server. |
| `/notify remove keyword` | Removes one of your keyword alerts. |
| `/notify list` | Lists your keyword alerts. |
| `/ping` | Shows bot gateway latency. |

#### Premium and subscriptions

| Command | What it does |
| --- | --- |
| `/premium [plan] [referral]` | Displays premium plans and starts checkout when Stripe is configured. |
| `/subscription` | Views or manages your premium subscription. |
| `/referral` | Views or creates a premium referral code when referrals are enabled. |
| `/giftpremium member days [plan]` `[staff]` | Grants a member complimentary premium access. |

The dashboard's **Trading** page can review trade calls already stored for a guild and correct their status. Trade-call creation and trade calculators are not currently registered as TypeScript slash commands.

Some commands that share a name, such as `/profile`, are routed to the community platform's profile implementation. Commands are registered by the bot when it connects to a guild.

#### Discord context-menu actions

- **View member profile** — opens the selected member's community profile.
- **Open staff history** — opens the selected member's moderation history (staff permission required).
- **Give kudos** — gives recognition for the selected message/member.
- **Report message** — submits the selected message for staff review.
- **Create support ticket** — opens a ticket based on the selected message.
- **Add to starboard** — sends the selected message to the configured starboard (staff permission required).

### Dashboard areas

The Express dashboard includes overview, setup and module configuration, command controls, onboarding, members, growth, community, engagement, rewards/economy, automation, security/safety, moderation, kudos, analytics/insights, social feeds, trade-call review, ticket review, billing and audit history. Dashboard access is authorized through Discord OAuth for members with `Manage Server` or IDs listed in `DASHBOARD_ADMIN_IDS`.

### TypeScript setup

Requirements: Node.js 20+, PostgreSQL, a Discord application/bot and Discord OAuth credentials.

Required environment variables: `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `TARGET_GUILD_ID`, `DATABASE_URL`, and `SESSION_SECRET`. Common optional variables include `DISCORD_REDIRECT_URI`, `BASE_URL`, `PORT`, `DASHBOARD_ADMIN_IDS`, `X_BEARER_TOKEN`, `SOCIAL_POLL_SECONDS`, Stripe credentials, and social webhook settings. See [`community-platform/src/config.ts`](community-platform/src/config.ts) for the full list and defaults.

```bash
cd community-platform
npm install
npm run dev
```

For production:

```bash
npm run build
npm start
```

The app initializes PostgreSQL schemas, starts the Discord bot and serves the dashboard. Invite the bot with the permissions required by the modules you enable, and enable the Server Members and Message Content intents in the Discord Developer Portal.

## Notes on scope

- The Python and TypeScript bots are separate applications and do not share databases or command registrations.
- Source files that are not imported/loaded by an entry point may be experiments, older implementations or dormant features. The Python section calls these out explicitly.
- Social feed providers need reachable feeds or their own credentials. Official X API polling requires an X bearer token.
- Premium checkout requires Stripe credentials and webhook configuration. Premium gift grants can be used independently by staff.
- A server snapshot is an inspectable configuration record; it is not a one-click restore or message backup.
