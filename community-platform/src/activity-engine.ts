import {
  ActionRowBuilder, ButtonBuilder, ButtonStyle, ChannelType, ChatInputCommandInteraction,
  Client, PermissionFlagsBits, SlashCommandBuilder, TextChannel
} from "discord.js";
import { audit, getFeature, one, query } from "./db.js";
import { awardCurrency } from "./economy-core.js";
import { BRAND, compactNumber, guildEmbed, guildSystemEmbed } from "./brand.js";

type ActivitySettings = {
  guild_id: string;
  enabled: boolean;
  timezone: string;
  primary_channel_id: string | null;
  staff_channel_id: string | null;
  leaderboard_channel_id: string | null;
};

type ActivitySlot = {
  id: number;
  guild_id: string;
  slot_key: string;
  prompt_type: string;
  title: string;
  hour: number;
  minute: number;
  channel_id: string | null;
  enabled: boolean;
  sort_order: number;
  last_post_key: string | null;
};

const defaultTimezone = "Europe/London";

const defaultSlots = [
  { key: "morning-market", type: "market_watch", title: "Morning Market Watch", hour: 9, minute: 0, channel: "primary", order: 10 },
  { key: "lunch-price-check", type: "price_check", title: "Lunchtime Price Check", hour: 12, minute: 0, channel: "primary", order: 20 },
  { key: "afternoon-flip", type: "flip_of_day", title: "Flip of the Day", hour: 15, minute: 0, channel: "primary", order: 30 },
  { key: "evening-discussion", type: "discussion", title: "Tonight's Trading Question", hour: 18, minute: 0, channel: "primary", order: 40 },
  { key: "trade-proof", type: "trade_proof", title: "Trade Proof Check-in", hour: 20, minute: 30, channel: "primary", order: 50 },
  { key: "daily-leaderboard", type: "leaderboard", title: "Daily Leaderboard", hour: 22, minute: 0, channel: "leaderboard", order: 60 },
  { key: "staff-pulse", type: "staff_pulse", title: "Staff Pulse", hour: 22, minute: 5, channel: "staff", order: 70 }
] as const;

const actionLabels: Record<string, string> = {
  watch: "Watching",
  risky: "Too risky",
  similar: "Wants similar",
  dropped_player: "Dropped a player",
  staff_ping: "Needs staff help",
  buying: "Buying",
  holding: "Holding",
  selling: "Selling",
  agree: "Agrees",
  posted_proof: "Posted proof",
  need_help: "Needs help"
};

function optionChannelId(channel: any) {
  return channel?.id ? String(channel.id) : null;
}

export const activityCommandData = [
  new SlashCommandBuilder().setName("activity").setDescription("Run the daily Discord activity engine")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand(s => s.setName("setup").setDescription("Install the week-one daily activity schedule")
      .addChannelOption(o => o.setName("channel").setDescription("Main activity channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))
      .addChannelOption(o => o.setName("staff_channel").setDescription("Private staff pulse channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))
      .addChannelOption(o => o.setName("leaderboard_channel").setDescription("Daily leaderboard channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))
      .addBooleanOption(o => o.setName("create_channels").setDescription("Create sensible activity channels automatically")))
    .addSubcommand(s => s.setName("schedule").setDescription("Show today's activity schedule"))
    .addSubcommand(s => s.setName("pause").setDescription("Pause automated activity posts"))
    .addSubcommand(s => s.setName("resume").setDescription("Resume automated activity posts"))
    .addSubcommand(s => s.setName("postnow").setDescription("Post an activity prompt now")
      .addStringOption(o => o.setName("type").setDescription("Prompt type").setRequired(true).addChoices(
        { name: "Market watch", value: "market_watch" },
        { name: "Price check", value: "price_check" },
        { name: "Flip of the day", value: "flip_of_day" },
        { name: "Discussion", value: "discussion" },
        { name: "Trade proof", value: "trade_proof" },
        { name: "Leaderboard", value: "leaderboard" },
        { name: "Staff pulse", value: "staff_pulse" }
      ))
      .addChannelOption(o => o.setName("channel").setDescription("Override destination").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement)))
    .addSubcommand(s => s.setName("settings").setDescription("Update activity engine channels")
      .addChannelOption(o => o.setName("channel").setDescription("Main activity channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))
      .addChannelOption(o => o.setName("staff_channel").setDescription("Private staff pulse channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))
      .addChannelOption(o => o.setName("leaderboard_channel").setDescription("Daily leaderboard channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement))),
  new SlashCommandBuilder().setName("today").setDescription("See today's server activity plan"),
  new SlashCommandBuilder().setName("pulse").setDescription("View today's community pulse")
    .addBooleanOption(o => o.setName("public").setDescription("Post visibly instead of privately"))
].map(c => c.toJSON());

function localParts(timezone: string, date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone || defaultTimezone,
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false
  }).formatToParts(date).reduce<Record<string, string>>((acc, part) => {
    if (part.type !== "literal") acc[part.type] = part.value;
    return acc;
  }, {});
  return {
    key: `${parts.year}-${parts.month}-${parts.day}`,
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    label: `${parts.day}/${parts.month}/${parts.year}`
  };
}

function unixTodayAt(timezone: string, hour: number, minute: number) {
  const now = new Date();
  const local = localParts(timezone, now);
  const utcGuess = new Date(`${local.key}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00.000Z`);
  return Math.floor(utcGuess.getTime() / 1000);
}

async function ensureActivityDefaults(guildId: string) {
  await query(`INSERT INTO activity_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING`, [guildId]);
  for (const slot of defaultSlots) {
    await query(`INSERT INTO activity_slots(guild_id,slot_key,prompt_type,title,hour,minute,sort_order)
      VALUES($1,$2,$3,$4,$5,$6,$7)
      ON CONFLICT(guild_id,slot_key) DO NOTHING`, [guildId, slot.key, slot.type, slot.title, slot.hour, slot.minute, slot.order]);
  }
}

export async function ensureActivityEngineDefaults(guildId: string) {
  await ensureActivityDefaults(guildId);
  await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config) VALUES($1,'activity_engine',true,$2::jsonb) ON CONFLICT DO NOTHING`,
    [guildId, JSON.stringify({ timezone: defaultTimezone, threadPrompts: true, rewardButtons: true })]);
}

async function getSettings(guildId: string): Promise<ActivitySettings> {
  await ensureActivityDefaults(guildId);
  const row = await one<ActivitySettings>(`SELECT * FROM activity_settings WHERE guild_id=$1`, [guildId]);
  return row || { guild_id: guildId, enabled: true, timezone: defaultTimezone, primary_channel_id: null, staff_channel_id: null, leaderboard_channel_id: null };
}

async function getSlots(guildId: string) {
  await ensureActivityDefaults(guildId);
  return query<ActivitySlot>(`SELECT * FROM activity_slots WHERE guild_id=$1 ORDER BY sort_order,hour,minute`, [guildId]);
}

function slotChannelId(slot: ActivitySlot, settings: ActivitySettings) {
  if (slot.channel_id) return slot.channel_id;
  if (slot.prompt_type === "staff_pulse") return settings.staff_channel_id || settings.primary_channel_id;
  if (slot.prompt_type === "leaderboard") return settings.leaderboard_channel_id || settings.primary_channel_id;
  return settings.primary_channel_id;
}

async function createActivityChannels(i: ChatInputCommandInteraction) {
  if (!i.guild) return {};
  const category = await i.guild.channels.create({ name: "EAFC.Live Activity", type: ChannelType.GuildCategory }).catch(() => null);
  const main = await i.guild.channels.create({ name: "daily-trading", type: ChannelType.GuildText, parent: category?.id }).catch(() => null);
  const leaderboard = await i.guild.channels.create({ name: "leaderboard", type: ChannelType.GuildText, parent: category?.id }).catch(() => null);
  const staff = await i.guild.channels.create({
    name: "staff-pulse",
    type: ChannelType.GuildText,
    parent: category?.id,
    permissionOverwrites: [
      { id: i.guild.roles.everyone.id, deny: [PermissionFlagsBits.ViewChannel] },
      { id: i.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory] },
      { id: i.guild.members.me?.id || i.client.user.id, allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory] }
    ]
  }).catch(() => null);
  return { main, leaderboard, staff };
}

function scheduleLines(slots: ActivitySlot[], settings: ActivitySettings) {
  return slots.filter(s => s.enabled).map(s => {
    const channelId = slotChannelId(s, settings);
    return `**${String(s.hour).padStart(2, "0")}:${String(s.minute).padStart(2, "0")}** ${s.title} ${channelId ? `<#${channelId}>` : "`no channel set`"}`;
  }).join("\n");
}

async function topActivity(guildId: string, limit = 5) {
  return query<any>(`SELECT user_id,(messages*2+helpful*8) score,messages,helpful FROM activity_daily WHERE guild_id=$1 AND activity_date=current_date ORDER BY score DESC,messages DESC LIMIT $2`, [guildId, limit]);
}

async function pulseStats(guildId: string) {
  const [metrics, active, responses, tickets, trades, top, joinsByInvite] = await Promise.all([
    one<any>(`SELECT * FROM server_metrics_daily WHERE guild_id=$1 AND metric_date=current_date`, [guildId]),
    one<any>(`SELECT count(DISTINCT user_id)::int active FROM activity_daily WHERE guild_id=$1 AND activity_date=current_date AND messages>0`, [guildId]),
    one<any>(`SELECT count(*)::int total FROM activity_responses WHERE guild_id=$1 AND created_at>=current_date`, [guildId]),
    one<any>(`SELECT count(*)::int total FROM tickets WHERE guild_id=$1 AND created_at>=current_date`, [guildId]),
    one<any>(`SELECT (SELECT count(*) FROM trade_calls WHERE guild_id=$1 AND created_at>=current_date) + (SELECT count(*) FROM trade_journal WHERE guild_id=$1 AND created_at>=current_date) total`, [guildId]),
    topActivity(guildId, 5),
    query<any>(`SELECT inviter_id,count(*)::int joins FROM invite_joins WHERE guild_id=$1 AND joined_at>=current_date AND inviter_id IS NOT NULL GROUP BY inviter_id ORDER BY joins DESC LIMIT 3`, [guildId])
  ]);
  const messageCount = Number(metrics?.messages || 0);
  const activeCount = Number(active?.active || 0);
  const responseCount = Number(responses?.total || 0);
  const suggestion = activeCount < 10 ? "Run a direct question or giveaway tomorrow. The server needs easy replies first." :
    responseCount < 8 ? "Use more button prompts tomorrow. People are reading but not interacting yet." :
    messageCount > 150 ? "Good momentum. Pin the best trade proof and give staff kudos while it is warm." :
    "Keep the rhythm steady. The next useful move is a trade-proof event.";
  return { metrics: metrics || {}, activeCount, responseCount, tickets: Number(tickets?.total || 0), trades: Number(trades?.total || 0), top, joinsByInvite, suggestion };
}

async function pulseEmbed(guildId: string, staff = false) {
  const p = await pulseStats(guildId);
  const top = p.top.length ? p.top.map((r: any, n: number) => `**${n + 1}.** <@${r.user_id}> • ${compactNumber(r.score)} pts • ${compactNumber(r.messages)} msg`).join("\n") : "No activity tracked yet.";
  const invite = p.joinsByInvite.length ? p.joinsByInvite.map((r: any) => `<@${r.inviter_id}> • ${r.joins}`).join("\n") : "No invite joins today.";
  const e = await guildSystemEmbed(guildId, staff ? "Daily Staff Pulse" : "Today's Community Pulse",
    `New members: **${compactNumber(p.metrics.joins || 0)}**\nActive chatters: **${compactNumber(p.activeCount)}**\nMessages: **${compactNumber(p.metrics.messages || 0)}**\nActivity responses: **${compactNumber(p.responseCount)}**\nTrade posts/calls: **${compactNumber(p.trades)}**\nTickets opened: **${compactNumber(p.tickets)}**`,
    staff ? BRAND.colours.premium : BRAND.colours.primary);
  e.addFields({ name: "Top contributors", value: top, inline: false });
  if (staff) e.addFields({ name: "Invite sources", value: invite, inline: true }, { name: "Suggested action", value: p.suggestion, inline: false });
  return e;
}

async function promptPayload(guildId: string, slot: Pick<ActivitySlot, "prompt_type" | "title">, postId?: number) {
  const type = slot.prompt_type;
  const rows = await query<any>(`SELECT player,buy_price,target_price,status,created_at FROM trade_calls WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 3`, [guildId]).catch(() => []);
  const hot = rows.length ? rows.map((r: any) => `**${r.player}**${r.buy_price ? ` buy ${compactNumber(r.buy_price)}` : ""}${r.target_price ? ` -> ${compactNumber(r.target_price)}` : ""}`).join("\n") : "";
  const mk = (action: string, label: string, style = ButtonStyle.Secondary) =>
    new ButtonBuilder().setCustomId(`activity:${action}:${postId || 0}`).setLabel(label).setStyle(style);

  if (type === "market_watch") {
    const e = await guildEmbed(guildId, "Morning Market Watch", hot || "No fresh calls logged yet. Use this as the morning watchlist: who is moving, who looks overbought, and who is worth holding?", BRAND.colours.primary);
    e.addFields({ name: "Question", value: "Which card are you watching today, and why?", inline: false });
    return { embeds: [e], components: [new ActionRowBuilder<ButtonBuilder>().addComponents(mk("watch", "I'm watching", ButtonStyle.Primary), mk("risky", "Too risky"), mk("similar", "Show similar"))] };
  }
  if (type === "price_check") {
    const e = await guildEmbed(guildId, "Lunchtime Price Check", "Drop one player you want checking. Staff can pick the best ones and turn them into calls, warnings or watchlist notes.", BRAND.colours.coins);
    return { embeds: [e], components: [new ActionRowBuilder<ButtonBuilder>().addComponents(mk("dropped_player", "I dropped a player", ButtonStyle.Primary), mk("staff_ping", "Needs staff eyes"))] };
  }
  if (type === "flip_of_day") {
    const e = await guildEmbed(guildId, "Flip of the Day", hot || "Pick one sensible low-risk flip for today. Post buy range, sell range, tax, and why lazy buyers should pay more.", BRAND.colours.success);
    e.addFields({ name: "Reply format", value: "`Player / buy / sell / why`", inline: false });
    return { embeds: [e], components: [new ActionRowBuilder<ButtonBuilder>().addComponents(mk("buying", "I'm buying", ButtonStyle.Success), mk("watch", "Watchlist"), mk("risky", "Too risky", ButtonStyle.Danger))] };
  }
  if (type === "discussion") {
    const e = await guildEmbed(guildId, "Tonight's Trading Question", "What are you doing tonight: buying, holding, selling, or staying liquid? Add your reason so newer members can learn from it.", BRAND.colours.primary);
    return { embeds: [e], components: [new ActionRowBuilder<ButtonBuilder>().addComponents(mk("buying", "Buying", ButtonStyle.Success), mk("holding", "Holding", ButtonStyle.Primary), mk("selling", "Selling", ButtonStyle.Danger))] };
  }
  if (type === "trade_proof") {
    const e = await guildEmbed(guildId, "Trade Proof Check-in", "Post your best trade, best snipe, or best save from today. Staff can award kudos and feature the best one tomorrow.", BRAND.colours.premium);
    return { embeds: [e], components: [new ActionRowBuilder<ButtonBuilder>().addComponents(mk("posted_proof", "I posted proof", ButtonStyle.Success), mk("need_help", "Need help improving"))] };
  }
  if (type === "leaderboard") {
    const top = await topActivity(guildId, 10);
    const body = top.length ? top.map((r: any, n: number) => `**${n + 1}.** <@${r.user_id}> • **${compactNumber(r.score)}** pts • ${compactNumber(r.messages)} messages`).join("\n") : "No leaderboard activity yet today.";
    return { embeds: [await guildEmbed(guildId, "Daily Activity Leaderboard", body, BRAND.colours.premium)], components: [] };
  }
  return { embeds: [await pulseEmbed(guildId, true)], components: [] };
}

async function sendActivityPost(client: Client, guildId: string, slot: ActivitySlot, channelId: string) {
  const channel = await client.channels.fetch(channelId).catch(() => null);
  if (!channel?.isTextBased()) throw new Error("Activity channel is not available.");

  const placeholder = (await query<any>(`INSERT INTO activity_posts(guild_id,slot_id,prompt_type,channel_id,title,metadata) VALUES($1,$2,$3,$4,$5,'{}'::jsonb) RETURNING id`,
    [guildId, slot.id, slot.prompt_type, channelId, slot.title]))[0];
  const payload = await promptPayload(guildId, slot, Number(placeholder.id));
  const msg = await (channel as TextChannel).send(payload);
  await query(`UPDATE activity_posts SET message_id=$2 WHERE id=$1`, [placeholder.id, msg.id]);

  const feature = await getFeature(guildId, "activity_engine", { threadPrompts: true });
  if (feature.config.threadPrompts && !["leaderboard", "staff_pulse"].includes(slot.prompt_type)) {
    await msg.startThread({ name: slot.title.slice(0, 90), autoArchiveDuration: 1440 }).catch(() => {});
  }
  await audit(guildId, "system", "activity.post.sent", { slotId: slot.id, promptType: slot.prompt_type, messageId: msg.id });
  return msg;
}

export async function runActivityEngineTick(client: Client) {
  const guilds = await query<ActivitySettings>(`SELECT * FROM activity_settings WHERE enabled=true`);
  for (const settings of guilds) {
    const parts = localParts(settings.timezone || defaultTimezone);
    const slots = await query<ActivitySlot>(`SELECT * FROM activity_slots WHERE guild_id=$1 AND enabled=true AND hour=$2 AND minute=$3 ORDER BY sort_order`,
      [settings.guild_id, parts.hour, parts.minute]);
    for (const slot of slots) {
      const postKey = `${slot.slot_key}:${parts.key}`;
      if (slot.last_post_key === postKey) continue;
      const channelId = slotChannelId(slot, settings);
      if (!channelId) continue;
      const changed = await query<any>(`UPDATE activity_slots SET last_post_key=$3 WHERE id=$1 AND guild_id=$2 AND COALESCE(last_post_key,'')<>$3 RETURNING id`,
        [slot.id, settings.guild_id, postKey]);
      if (!changed.length) continue;
      await sendActivityPost(client, settings.guild_id, slot, channelId).catch(async err => {
        await audit(settings.guild_id, "system", "activity.post.failed", { slotId: slot.id, error: String(err?.message || err).slice(0, 500) }).catch(() => {});
      });
    }
  }
}

export async function handleActivityComponent(i: any) {
  if (!i.guildId || !i.isButton?.() || !String(i.customId || "").startsWith("activity:")) return false;
  const [, action, rawPostId] = String(i.customId).split(":");
  const actionKey = String(action || "");
  const postId = Number(rawPostId || 0);
  if (!postId || !actionLabels[actionKey]) {
    await i.reply({ content: "That activity prompt is no longer tracked.", ephemeral: true });
    return true;
  }
  const post = await one<any>(`SELECT * FROM activity_posts WHERE id=$1 AND guild_id=$2`, [postId, i.guildId]);
  if (!post) {
    await i.reply({ content: "That activity prompt is no longer tracked.", ephemeral: true });
    return true;
  }
  const inserted = await query<any>(`INSERT INTO activity_responses(post_id,guild_id,user_id,action) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING RETURNING id`,
    [postId, i.guildId, i.user.id, actionKey]);
  if (inserted.length) {
    await query(`INSERT INTO activity_daily(guild_id,user_id,activity_date,helpful) VALUES($1,$2,current_date,1)
      ON CONFLICT(guild_id,user_id,activity_date) DO UPDATE SET helpful=activity_daily.helpful+1`, [i.guildId, i.user.id]);
    const feature = await getFeature(i.guildId, "activity_engine", { rewardButtons: true });
    if (feature.config.rewardButtons !== false) {
      const big = actionKey === "posted_proof";
      await awardCurrency({ guildId: i.guildId, userId: i.user.id, currency: "xp", amount: big ? 25 : 5, reason: `Activity: ${actionLabels[actionKey]}`, sourceType: "activity", sourceId: String(postId), idempotencyKey: `activity:${postId}:${actionKey}:${i.user.id}:xp` }).catch(() => {});
      await awardCurrency({ guildId: i.guildId, userId: i.user.id, currency: "coins", amount: big ? 10 : 2, reason: `Activity: ${actionLabels[actionKey]}`, sourceType: "activity", sourceId: String(postId), idempotencyKey: `activity:${postId}:${actionKey}:${i.user.id}:coins` }).catch(() => {});
    }
  }
  await i.reply({ content: inserted.length ? `Logged: **${actionLabels[actionKey]}**.` : "Already logged for this prompt.", ephemeral: true });
  return true;
}

export async function handleActivityCommand(client: Client, i: ChatInputCommandInteraction) {
  if (!i.guildId || !i.guild || !["activity", "today", "pulse"].includes(i.commandName)) return false;

  if (i.commandName === "today") {
    const settings = await getSettings(i.guildId);
    const slots = await getSlots(i.guildId);
    await i.reply({ embeds: [await guildEmbed(i.guildId, "Today's Activity Plan", scheduleLines(slots, settings) || "No activity slots configured.", BRAND.colours.primary)], ephemeral: true });
    return true;
  }

  if (i.commandName === "pulse") {
    const isPublic = i.options.getBoolean("public") === true;
    await i.reply({ embeds: [await pulseEmbed(i.guildId, false)], ephemeral: !isPublic });
    return true;
  }

  const sub = i.options.getSubcommand();
  if (sub === "setup") {
    await i.deferReply({ ephemeral: true });
    let main = i.options.getChannel("channel");
    let staff = i.options.getChannel("staff_channel");
    let leaderboard = i.options.getChannel("leaderboard_channel");
    if (i.options.getBoolean("create_channels")) {
      const created = await createActivityChannels(i);
      main = created.main || main;
      staff = created.staff || staff;
      leaderboard = created.leaderboard || leaderboard;
    }
    const primary = optionChannelId(main) || i.channelId;
    const staffId = optionChannelId(staff) || primary;
    const leaderboardId = optionChannelId(leaderboard) || primary;
    await ensureActivityDefaults(i.guildId);
    await query(`INSERT INTO activity_settings(guild_id,enabled,timezone,primary_channel_id,staff_channel_id,leaderboard_channel_id,updated_at)
      VALUES($1,true,$2,$3,$4,$5,now())
      ON CONFLICT(guild_id) DO UPDATE SET enabled=true,timezone=$2,primary_channel_id=$3,staff_channel_id=$4,leaderboard_channel_id=$5,updated_at=now()`,
      [i.guildId, defaultTimezone, primary, staffId, leaderboardId]);
    await audit(i.guildId, i.user.id, "activity.setup", { primary, staffId, leaderboardId });
    await i.editReply({ embeds: [await guildEmbed(i.guildId, "Activity engine installed", `Week-one rhythm is live.\n\nMain: <#${primary}>\nLeaderboard: <#${leaderboardId}>\nStaff pulse: <#${staffId}>\n\nUse \`/today\` to view the schedule and \`/activity postnow\` to test a prompt.`, BRAND.colours.success)] });
    return true;
  }

  if (sub === "schedule") {
    const settings = await getSettings(i.guildId);
    const slots = await getSlots(i.guildId);
    await i.reply({ embeds: [await guildEmbed(i.guildId, settings.enabled ? "Activity Schedule" : "Activity Schedule (Paused)", scheduleLines(slots, settings) || "No activity slots configured.", settings.enabled ? BRAND.colours.primary : BRAND.colours.warning)], ephemeral: true });
    return true;
  }

  if (sub === "pause" || sub === "resume") {
    await query(`INSERT INTO activity_settings(guild_id,enabled,updated_at) VALUES($1,$2,now()) ON CONFLICT(guild_id) DO UPDATE SET enabled=$2,updated_at=now()`, [i.guildId, sub === "resume"]);
    await audit(i.guildId, i.user.id, `activity.${sub}`, {});
    await i.reply({ content: sub === "resume" ? "Activity engine resumed." : "Activity engine paused.", ephemeral: true });
    return true;
  }

  if (sub === "settings") {
    const settings = await getSettings(i.guildId);
    const main = i.options.getChannel("channel");
    const staff = i.options.getChannel("staff_channel");
    const leaderboard = i.options.getChannel("leaderboard_channel");
    const primary = optionChannelId(main) || settings.primary_channel_id;
    const staffId = optionChannelId(staff) || settings.staff_channel_id;
    const leaderboardId = optionChannelId(leaderboard) || settings.leaderboard_channel_id;
    await query(`UPDATE activity_settings SET primary_channel_id=$2,staff_channel_id=$3,leaderboard_channel_id=$4,updated_at=now() WHERE guild_id=$1`,
      [i.guildId, primary, staffId, leaderboardId]);
    await i.reply({ content: "Activity engine settings updated.", ephemeral: true });
    return true;
  }

  if (sub === "postnow") {
    await i.deferReply({ ephemeral: true });
    const type = i.options.getString("type", true);
    const settings = await getSettings(i.guildId);
    const override = i.options.getChannel("channel");
    const slot = (await query<ActivitySlot>(`SELECT * FROM activity_slots WHERE guild_id=$1 AND prompt_type=$2 ORDER BY sort_order LIMIT 1`, [i.guildId, type]))[0] ||
      { id: 0, guild_id: i.guildId, slot_key: `manual-${type}`, prompt_type: type, title: type.replaceAll("_", " "), hour: 0, minute: 0, channel_id: null, enabled: true, sort_order: 999, last_post_key: null };
    const channelId = optionChannelId(override) || slotChannelId(slot, settings);
    if (!channelId) {
      await i.editReply("Set an activity channel first with `/activity setup`.");
      return true;
    }
    const msg = await sendActivityPost(client, i.guildId, slot, channelId);
    await i.editReply(`Posted ${slot.title} in <#${channelId}>: ${msg.url}`);
    return true;
  }
  return false;
}
