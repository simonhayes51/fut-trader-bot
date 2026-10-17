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
- Staff-focused activity pulse with `/activity setup`, `/today`, `/pulse`, button rewards, leaderboards and staff summaries
- FUTBank staff payment reports with `/staffpay report`
- Counting game support

### Trading
- `/tradetip` freeform trader-tip posts with bought/watching/passed/sold buttons
- Trader-tip posting and tracking XP for staff payment reports
- Dashboard trade-call history and status correction
- Trade calculators and structured trade-call slash commands are not currently registered in this TypeScript app

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

Use the task pages in the sidebar as the normal way into the control panel:

| Owner task | Page | What it manages |
| --- | --- | --- |
| See server status and what needs attention | `/control` | Overview, recent activity and next steps |
| Set up new members | `/control/onboarding` | Verification, member roles, birthdays, counting and live counters |
| Configure member-facing community tools | `/control/community` | Welcome tools, suggestions, tickets, starboard, custom replies and sticky reminders |
| Build Discord messages and role menus | `/control/studio` | Message templates, interactive role panels and reaction roles |
| Schedule posts and connect content feeds | `/control/automation` | Recurring messages, RSS/social/webhook feeds and giveaways |
| Find a specific member | `/control/members` | Searchable server directory and member profile |
| Configure individual bot features | `/control/settings` → select a feature | Feature status, setup gaps and settings |
| Manage kudos and progression | `/control/kudos` | Recognition, levels, milestones and recaps |
| Manage coins and rewards | `/economy` | Economy settings, shop, seasons, quests and redemptions |
| Review tickets and moderation | `/control/safety` | Support queue, warnings, reports and safety tools |
| Protect the server | `/control/security` | Security policy, health findings and permission inspection |
| Manage invitations and partners | `/control/growth` | Invite and booster rewards, partners and milestones |
| Configure memberships | `/billing` | Stripe plans, subscriptions, referrals and complimentary access |
| Review activity and metrics | `/control/insights` | Funnel, engagement, feature use and dashboard widgets |
| Review administrator changes | `/audit` | Server audit history |
| Create Discord-native tools | `/discord` | Forums, polls, events and Discord onboarding sync |
| Restrict bot commands | `/commands` | Command access by role and channel |

`/modules/:key` opens a feature’s focused setup editor. Older bookmarks such as `/dashboard`, `/social`, `/trading`, `/analytics` and `/members` remain supported as redirects to their current task page.

## Daily activity engine

The activity engine gives staff a repeatable daily pulse without forcing public prompt spam. By default, only the staff pulse is enabled; the public prompts can still be posted manually or enabled later.

Default schedule:

| Time | Prompt | Default |
| --- | --- | --- |
| 09:00 | Morning Market Watch | Off by default |
| 12:00 | Lunchtime Price Check | Off by default |
| 15:00 | Flip of the Day | Off by default |
| 18:00 | Tonight's Trading Question | Off by default |
| 20:30 | Trade Proof Check-in | Off by default |
| 22:00 | Daily Activity Leaderboard | Off by default |
| 22:05 | Staff Pulse | On by default |

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
- Role menus
- Trader tips
- XP, levels and leaderboards
- Simple rewards shop for point redemption
- Premium billing
- Counting
- Suggestions
- Tickets
- Automod & anti-scam
- Staff moderation
- Join security
- Staff pulse
- Staff pay reports
- Giveaways
- Bump reminders
- Server backup
- Social feeds

Then open each module in the dashboard and map the relevant Discord channel/role IDs.

Leave off unless the server asks for them:
- Public daily activity posts
- Birthdays
- AFK
- Starboard

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
