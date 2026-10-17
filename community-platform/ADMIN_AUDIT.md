# Community Platform admin audit

Reviewed against the checked-out source on 17 October 2026. Route handlers, EJS forms, feature configuration, persistence, and the runtime workers were traced. This is an implementation audit; a Discord server and production database were not available in this checkout, so external delivery cannot be claimed as live-tested.

## Current product map

| Owner task | Admin surface | Data/actions | Baseline findings before this redesign |
|---|---|---|---|
| Sign in and choose a server | Discord OAuth, server selector | OAuth identity and manageable guilds; selected guild in session | Access depends on bot being present. Most errors are plain text. Server selector auto-submits. |
| See what needs attention | `/control` | Counts from member, ticket, moderation, economy, growth, security, usage tables; audit events | Counts with no underlying tracking can look like real zeroes. Attention list only appears for nonzero counts. |
| Set up new members | `/control/onboarding` | Welcome/onboarding panel, platform/interest/notification roles, birthdays, counting, channel counters | Several independent saves on one page; missing validation; onboarding publish failure returns raw text. |
| Configure community interactions | `/control/community`, `/modules/*` | Welcome, role menus, suggestions, tickets, starboard, custom replies, sticky messages | Duplicate configuration homes; status shows enabled by default when unset; publication errors can follow persisted settings. |
| Configure engagement | `/control/kudos`, `/control/engagement`, `/economy`, `/control/rewards`, `/modules/*` | Kudos, XP, roles, quests, achievements, giveaways, store, seasons, drops, ledger, redemption queue | Multiple overlapping pages; some actions report generic “Saved”; feature pages can imply tracking or enabled state without setup. |
| Publish server content | `/control/studio`, `/control/automation`, `/social`, `/modules/*` | Message templates, role panels, reaction roles, scheduled posts, social feeds/webhooks | Duplicate feeds and feature settings; schedule times are stored as cron without visible timezone handling; errors/success often lack context. |
| Manage server growth | `/control/growth`, `/billing` | Invite milestones, partnerships, boosters, plans, subscriptions, referral codes | Several writes have no field validation; duplicate form handling in legacy billing routes. |
| Keep members safe | `/control/safety`, `/control/security`, `/moderation`, `/modules/*` | Warnings, scam reports, tickets, automod, join/security suite, permission inspection, health fixes | Multiple overlapping safety pages; some destructive actions return plain text; status/readiness not consistent. |
| Find members | `/control/members`, `/members`, `/members/:id` | Discord roster plus stats, XP, economy, trades, warnings, tickets, billing, referrals, achievements, quests, ledger | Two directory implementations. Untracked values and real zeroes are not consistently distinguished. |
| Review feature use | `/control/insights`, `/analytics`, `/commands` | Funnel, retention, usage events, premium, referrals, leaderboards, command permissions, widgets | Analytics use zero for missing instrumentation; dead-feature list can mistake untracked features for unused ones. |
| Configure native Discord tools | `/discord` | Create forum, poll, event; sync native onboarding | Discord API errors are surfaced through redirects; no broad success/failure consistency. |
| Manage active support | `/tickets` | Ticket ledger, transcript, force close and delete Discord channel | Force-close has a confirmation but route treats channel deletion errors as success and closes DB row regardless. |
| Review admin changes | `/audit`, `/moderation` | Audit records and warnings | Audit is bounded to latest 250; sparse labels and no search/filter. |
| Configure command access | `/commands` | Per-command enabled state and role restrictions | Command inventory is deduplicated, but behavior/settings need server-side validation. |
| Remove the bot | `/control/settings` | Confirm server name, leave guild, audit action | Exact-name confirmation and guild id guard exist. Failure is raw text. This is destructive but appropriately confirmed. |

## Feature-by-feature configuration inventory

| Feature | Purpose and users | Settings / saved data | Baseline runtime and readiness concerns (see work completed below) |
|---|---|---|---|
| Server branding | Owner controls bot/embeds | Brand name, nickname, URL, footer, logo/banner, colours in `guild_settings.settings.brand` | Nickname is applied to Discord after saving; nickname failure is only a query error. URL/colour values were not validated. |
| Welcome | Owner welcomes members | Channel, auto role, message, DM flag in `feature_settings` | Missing channel can still show On. Channel permissions and role assignability are not validated before save. |
| Roles & interests | Owner lets members self-assign roles | Channel and groups/role IDs in feature config | Save also publishes messages; failed publication leaves config saved, stale/unpublished groups possible. Role hierarchy can make selected roles unusable. |
| Kudos / reputation | Members recognise helpful contributions | Daily limit, account age, leaderboard size | Numeric bounds are UI-only; no setup channel needed. Unset values silently inherit defaults. |
| Levels & progression | Members earn XP and role milestones | XP, cooldown, ignored channels, level rewards | Repeater values have weak validation; duplicate/invalid XP thresholds and roles can be saved. |
| Suggestions | Members submit/vote; staff review | Channel, thread toggle, statuses | Channel and allowed status list are not validated; no publish/test step. |
| Tickets & reports | Members contact staff privately | Ticket panels, channels/categories, staff roles, log channel, types | Publishing can partially post multiple panels; settings are saved before publication. Some ticket closes delete channel but swallow Discord errors. |
| Giveaways | Staff run prizes | Channel, age minimum, booster entries | Configuration is separate from giveaway create/close commands; numeric constraints only client-side. |
| Starboard | Members surface popular posts | Channel, emoji, threshold, self-reaction, ignored channels | Emoji/channel validity and threshold not checked server-side. |
| Automod & anti-scam | Protect chat | Invite policy, bypass roles, mention/repeat limits, terms/domains, action, timeout, log channel | All input is accepted as JSON. Config is not checked against runtime semantics/Discord permission before save. |
| Staff moderation | Staff roles and log destination | Staff role IDs and log channel | Readiness checks roles/channel, but the editor does not verify roles or channel remain available. |
| Join security | Owner receives suspicious-join alerts | Account-age limit, alert channel, raid threshold | Threshold accepts any numeric value through direct POST; no bot permission test. |
| Scheduled messages | Owner schedules recurring content | Timezone in feature config; schedule CRUD stores cron/content/channel | Scheduled-message form does not persist/use selected timezone; blank fields may be saved. Cron is opaque in list. |
| Social feeds | Owner routes content into Discord | Provider/source/channel/filters/mention/secret in `social_feeds` | Provider/source/channel/URL not validated; webhook secret is only shown by existing implementation path (must verify); feeds have duplicate UI surfaces. |
| Premium billing | Owner configures memberships | Retry grace, role removal, promo codes, referrals in feature config | Stripe availability and missing roles are not reflected in readiness status. |

## Other individually traced admin tools (baseline findings)

| Tool | Purpose / data | Issues found |
|---|---|---|
Onboarding wizard, birthday rewards, counting, server counters | Configure new-member flow and utility counters | Independent persistence tables; direct POST accepts values without robust range/Discord object checks; a save can reset counting progress. |
Security suite, health scan, permission inspector, health fixes | Detect server risks and remediate known findings | Security config and scans are distinct; health score is heuristic; fixes need careful stale-record handling. |
Message templates, role panels, reaction roles | Build/publish Discord messages and role controls | Names, URLs, colors, channel IDs, role IDs need server-side validation; publish-now can save before publishing. |
Kudos milestones, recognition roles, weekly/monthly recaps, level workflows | Reward recognition and automate recaps | Writes lack consistent bounds, feedback and audit coverage. |
Invite milestones, partnerships, booster milestones | Retained growth and partner tracking | Names and dates are weakly validated; duplicate partner records allowed. |
Insights widgets | Personal dashboard composition | Arbitrary widget names accepted; missing instrumentation shown as zero uses. |
Rewards store, flash drops, daily panel | Reward members and manage redemptions | Numeric coercion can convert blank to zero; stock/limits/date relationships need validation; publish errors are raw text. |
Economy controls | Coins, quests, seasons, shop, redemptions, ledger | Large multifunction surface; needs stronger task separation and clear irreversible action feedback. |
Command access | Toggle commands and permissions | POST validation and role availability need review against Discord permission requirements. |
Member detail and directory | Staff review of a member's activity and access | Search/filter and pagination are inconsistent between old and new directories; tracked-data availability is unclear. |
Trade call status | Staff updates a call | Status whitelist exists; nonexistent ID still redirects as if changed; legacy route redirects back to `/trading`, which redirects to engagement. |
Social feed webhook delivery | External systems post content | Secret route and delivery are implemented; malformed payload/error detail not visible to admin. |
Discord native setup | Forums, polls, events and onboarding sync | Needs per-action input validation and consistent error messages; exact API success requires live Discord to verify. |

## Redesign and verification priorities

1. Use one visible task-based navigation and remove duplicate routes from the everyday journey while retaining working legacy URLs.
2. Make feature readiness depend on persisted configuration and required Discord resources, not default enabled flags.
3. Validate configuration on the server before writing; show save and publish outcomes separately when Discord delivery is a second step.
4. Keep metrics honest when instrumentation or source records are absent.
5. Standardise page framing, form hierarchy, feedback, mobile navigation, focus states, and empty/error/loading language.
6. Build and run route/template checks locally. Live Discord permissions, bot delivery, OAuth, Stripe and database-backed scenarios remain external dependencies unless configured in the environment.

## Work completed in this checkout

- Replaced the collapsed/overlapping everyday navigation with persistent task groups and one canonical automation destination. Legacy paths still redirect to their canonical pages.
- Added server-side validation for module configuration, feature readiness gaps, role hierarchy checks, and clear distinction between Off, Needs setup and On. Turning off scheduled messages or social feeds now stops their respective worker delivery.
- Applied timezone-aware scheduled-message matching, clearer schedule/feed setup and result states, and server-side validation to those workflows. Ticket panel selection now chooses a complete enabled panel; force close reports Discord deletion failures without falsely marking the ticket closed.
- Added per-source tracked-data states for member and overview metrics so unavailable or uncollected values appear as “Not tracked”/“—” rather than zero. Insights now distinguish absent events from uninstrumented tools.
- Staff moderation roles and the master switch are now enforced when moderation commands run. Those role-gated commands are visible to configured staff even when they do not have Discord's built-in moderator permission; Discord still enforces the bot's own action permissions. Successful actions are written to the selected moderation log channel and the database audit.
- Updated page framing, forms, feedback, and mobile navigation across the redesigned control surfaces.

## Remaining verified limitations

- This is not a claim that every mutation endpoint has been hardened. Several older admin writers remain outside the new feature-config validator, including economy/shop/quest/season, invite/partnership, insight-widget, onboarding/counter, and some native Discord tools. The audit tables above preserve these issues as work remaining.
- Discord API execution, OAuth, Stripe, database persistence, bot role hierarchy, and actual post delivery could not be exercised because this checkout has no service credentials or configured database/server.
- Desktop/mobile rendering could not be visually inspected in this environment. Chromium was unavailable and its attempted download failed integrity checks; the cloud browser could not reach a local preview server. CSS breakpoints and all EJS templates were checked in source, but a screenshot-based visual pass remains outstanding.
- The updated Discord command visibility takes effect when the bot next registers commands. This checkout has not been deployed or restarted against a live server.

## Local verification

- `npm test`: TypeScript build and six focused tests pass (feature setup validation, bounds, role hierarchy, disabled incomplete setup, and timezone/DST schedule matching).
- Compiled all 34 EJS templates successfully.
- `git diff --check` passes.
