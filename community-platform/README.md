# EAFC.Live Community Platform

A standalone Discord community bot + web control panel for an FC27 trading server. It is deliberately separate from any EAFC.Live product bot.

## What is included

### Community
- Discord OAuth-protected web dashboard
- Welcome messages and autoroles
- Module-level feature flags
- Reputation / `/thanks`
- Member `/profile`
- Suggestions with voting and optional threads
- Private ticket creation
- W/L community voting
- Activity XP foundation
- Daily activity engine with `/activity setup`, `/today`, `/pulse`, scheduled prompts, button rewards, leaderboards and staff summaries

### Trading
- `/tax`
- `/profit`
- `/roi`
- `/breakeven`
- `/tradetip` freeform trader-tip posts with bought/watching/passed/sold buttons
- Structured `/call` posts with target ROI and optional discussion thread
- `/callclose`
- Dashboard trade-call history and status correction

### Moderation / safety
- `/warn` and `/history`
- Invite blocking
- mention-spam protection
- repeated-message protection
- blocked terms and blocked domains
- optional auto timeout
- join-account-age alerts
- audit log

### Social feeds (TweetShift-style)
- RSS / Atom feeds
- Reddit RSS feeds
- YouTube RSS feeds
- optional official X API polling
- generic authenticated-by-secret incoming webhook feeds
- include/exclude keyword filters
- role pings per feed
- per-feed pause/delete controls from dashboard

The social system is intentionally provider-based so the server is not dependent on one third-party feed bot. X access requires your own X API entitlement/token; the generic webhook and RSS routes work without it.

## Dashboard

Routes:
- `/dashboard` overview + every feature module
- `/modules/:key` enable/disable and edit complete JSON configuration
- `/social` add, filter, pause and delete feeds
- `/trading` review trade calls
- `/tickets` review/close tickets
- `/moderation` warnings and automod activity
- `/audit` configuration/admin history

## Daily activity engine

The activity engine gives a server a repeatable week-one rhythm without staff having to invent posts all day.

Default schedule:

| Time | Prompt |
| --- | --- |
| 09:00 | Morning Market Watch |
| 12:00 | Lunchtime Price Check |
| 15:00 | Flip of the Day |
| 18:00 | Tonight's Trading Question |
| 20:30 | Trade Proof Check-in |
| 22:00 | Daily Activity Leaderboard |
| 22:05 | Staff Pulse |

Commands:

| Command | What it does |
| --- | --- |
| `/activity setup` | Installs the default schedule and channel destinations. |
| `/activity schedule` | Shows the configured rhythm. |
| `/activity pause` / `/activity resume` | Stops or restarts automated posts. |
| `/activity postnow` | Sends a selected prompt immediately. |
| `/activity settings` | Updates the main, staff and leaderboard channels. |
| `/today` | Shows the member-facing schedule. |
| `/pulse` | Shows joins, active chatters, messages, responses, trades, tickets and top contributors. |

Dashboard login requires either:
1. Discord `Manage Server` permission for `TARGET_GUILD_ID`; or
2. the Discord user ID in `DASHBOARD_ADMIN_IDS`.

## Setup

1. Create a Discord application and bot in the Discord Developer Portal.
2. Enable Server Members Intent and Message Content Intent.
3. Add an OAuth redirect matching `DISCORD_REDIRECT_URI`.
4. Invite the bot with the permissions it needs. For the complete feature set this includes Manage Roles, Manage Channels, Manage Messages, Moderate Members, Read Message History, Send Messages, Embed Links, Add Reactions and Create Public Threads.
5. Create PostgreSQL.
6. Copy `.env.example` to `.env` and fill the values.
7. Install and start:

```bash
npm install
npm run dev
```

The app automatically creates its database tables at startup and registers slash commands to `TARGET_GUILD_ID`.

Production:

```bash
npm install
npm run build
npm start
```

or deploy the included Dockerfile.

## Social feed examples

### Reddit
Provider: `reddit`
Source:

```text
https://www.reddit.com/r/EASportsFC/new/.rss
```

### Generic RSS
Provider: `rss`
Source: any valid RSS/Atom URL.

### X
Provider: `x`
Source:

```text
@EASPORTSFC
```

Set `X_BEARER_TOKEN`. The implementation uses X's official API rather than scraping the site.

### Generic webhook
Choose provider `webhook`. The dashboard creates a URL such as:

```text
https://your-dashboard.example/hooks/social/<generated-secret>
```

POST JSON:

```json
{
  "id": "unique-post-id",
  "title": "New FC27 content",
  "text": "Description shown in Discord",
  "url": "https://example.com/post",
  "author": "Source name",
  "image": "https://example.com/image.jpg"
}
```

That makes it easy to connect Make, Zapier, n8n, your own scraper/API, or another internal service without changing the bot.

## Recommended first configuration

Turn on:
- Welcome & onboarding
- Reputation & thanks
- Trading calculators
- Trade calls
- W/L voting
- Suggestions
- Tickets
- Automod & anti-scam
- Staff moderation
- Join security
- Social feeds

Then open each module in the dashboard and map the relevant Discord channel/role IDs.

## Architecture

One deployable Node/TypeScript app runs:
- Discord.js bot
- Express web dashboard
- PostgreSQL persistence
- social-feed scheduler

This keeps configuration and state shared and avoids a separate dashboard service becoming out of sync with the bot.

## Security notes

- Never commit `.env`.
- Keep `SESSION_SECRET` long and random.
- Treat generated webhook URLs as credentials.
- Use the smallest Discord permissions practical for your server.
- The dashboard verifies server administration via Discord OAuth.
- Dashboard changes and moderation actions are written to `audit_log`.
