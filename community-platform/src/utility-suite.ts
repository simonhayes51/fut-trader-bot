import {
  Attachment, ChannelType, ChatInputCommandInteraction, Client, EmbedBuilder, Guild, GuildMember,
  GuildTextBasedChannel, PermissionFlagsBits, SlashCommandBuilder, TextChannel
} from "discord.js";
import { audit, one, query } from "./db.js";
import { BRAND, compactNumber, guildEmbed, guildSystemEmbed } from "./brand.js";

const notifyCooldownMs = 30 * 60_000;

export const utilityCommandData = [
  new SlashCommandBuilder().setName("avatar").setDescription("Show a member avatar")
    .addUserOption(o => o.setName("member").setDescription("Member")),
  new SlashCommandBuilder().setName("userinfo").setDescription("Show useful member information")
    .addUserOption(o => o.setName("member").setDescription("Member")),
  new SlashCommandBuilder().setName("serverinfo").setDescription("Show server information"),
  new SlashCommandBuilder().setName("roleinfo").setDescription("Show role information")
    .addRoleOption(o => o.setName("role").setDescription("Role").setRequired(true)),
  new SlashCommandBuilder().setName("poll").setDescription("Create a native Discord poll")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addStringOption(o => o.setName("question").setDescription("Poll question").setRequired(true).setMaxLength(300))
    .addStringOption(o => o.setName("answers").setDescription("Answers separated with |").setRequired(true).setMaxLength(600))
    .addIntegerOption(o => o.setName("hours").setDescription("Duration in hours").setMinValue(1).setMaxValue(168))
    .addBooleanOption(o => o.setName("multiple").setDescription("Allow multiple answers")),
  new SlashCommandBuilder().setName("emoji").setDescription("Manage server emojis")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuildExpressions)
    .addSubcommand(s => s.setName("add").setDescription("Add an emoji from an uploaded image")
      .addStringOption(o => o.setName("name").setDescription("Emoji name").setRequired(true).setMaxLength(32))
      .addAttachmentOption(o => o.setName("image").setDescription("PNG/JPG/GIF image").setRequired(true)))
    .addSubcommand(s => s.setName("remove").setDescription("Remove a server emoji")
      .addStringOption(o => o.setName("emoji").setDescription("Emoji name or ID").setRequired(true)))
    .addSubcommand(s => s.setName("list").setDescription("List server emojis")),
  new SlashCommandBuilder().setName("notify").setDescription("DM you when keywords are mentioned")
    .addSubcommand(s => s.setName("add").setDescription("Add a keyword alert")
      .addStringOption(o => o.setName("keyword").setDescription("Keyword or phrase").setRequired(true).setMaxLength(80)))
    .addSubcommand(s => s.setName("remove").setDescription("Remove a keyword alert")
      .addStringOption(o => o.setName("keyword").setDescription("Keyword or phrase").setRequired(true).setMaxLength(80)))
    .addSubcommand(s => s.setName("list").setDescription("List your keyword alerts")),
  new SlashCommandBuilder().setName("bumpreminder").setDescription("Manage DISBOARD-style bump reminders")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand(s => s.setName("set").setDescription("Post recurring bump reminders")
      .addChannelOption(o => o.setName("channel").setDescription("Reminder channel").addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement).setRequired(true))
      .addIntegerOption(o => o.setName("minutes").setDescription("Reminder interval").setMinValue(60).setMaxValue(1440))
      .addStringOption(o => o.setName("message").setDescription("Reminder message").setMaxLength(500)))
    .addSubcommand(s => s.setName("off").setDescription("Disable bump reminders"))
    .addSubcommand(s => s.setName("status").setDescription("Show bump reminder status")),
  new SlashCommandBuilder().setName("serverbackup").setDescription("Create lightweight server snapshots")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand(s => s.setName("create").setDescription("Snapshot roles, channels and core settings")
      .addStringOption(o => o.setName("name").setDescription("Snapshot name").setMaxLength(80)))
    .addSubcommand(s => s.setName("list").setDescription("List snapshots"))
    .addSubcommand(s => s.setName("inspect").setDescription("Inspect a snapshot")
      .addIntegerOption(o => o.setName("id").setDescription("Snapshot ID").setRequired(true)))
].map(c => c.toJSON());

function cleanKeyword(value: string) {
  return value.trim().replace(/\s+/g, " ").slice(0, 80);
}

function timestamp(date?: Date | number | string | null) {
  if (!date) return "Unknown";
  const ms = new Date(date).getTime();
  return Number.isFinite(ms) ? `<t:${Math.floor(ms / 1000)}:R>` : "Unknown";
}

function snapshotGuild(guild: Guild) {
  const roles = [...guild.roles.cache.values()]
    .filter(r => r.name !== "@everyone")
    .sort((a, b) => b.position - a.position)
    .map(r => ({
      id: r.id, name: r.name, colour: r.color, hoist: r.hoist, mentionable: r.mentionable,
      permissions: r.permissions.bitfield.toString(), position: r.position
    }));
  const channels = [...guild.channels.cache.values()]
    .sort((a, b) => (("position" in a ? a.position : 0) - ("position" in b ? b.position : 0)))
    .map(c => ({
      id: c.id, name: c.name, type: c.type, parentId: "parentId" in c ? c.parentId : null,
      position: "position" in c ? c.position : 0, topic: "topic" in c ? c.topic : null, nsfw: "nsfw" in c ? c.nsfw : false
    }));
  return {
    guild: { id: guild.id, name: guild.name, icon: guild.iconURL(), memberCount: guild.memberCount },
    roles,
    channels,
    createdAt: new Date().toISOString()
  };
}

async function addEmoji(i: ChatInputCommandInteraction, image: Attachment, name: string) {
  if (!i.guild) return;
  if (!/^[-_a-z0-9]{2,32}$/i.test(name)) throw new Error("Emoji names can only use letters, numbers, underscores or hyphens.");
  if (!image.contentType?.startsWith("image/")) throw new Error("Upload an image file.");
  const emoji = await i.guild.emojis.create({ attachment: image.url, name, reason: `Added by ${i.user.tag}` });
  await audit(i.guild.id, i.user.id, "utility.emoji.add", { emojiId: emoji.id, name });
  await i.reply({ embeds: [await guildEmbed(i.guild.id, "Emoji added", `${emoji} \`:${emoji.name}:\``, BRAND.colours.success)], ephemeral: true });
}

export async function handleUtilityCommand(client: Client, i: ChatInputCommandInteraction) {
  if (!i.guildId || !i.guild) return false;
  const gid = i.guildId;

  if (i.commandName === "avatar") {
    const user = i.options.getUser("member") || i.user;
    const url = user.displayAvatarURL({ size: 1024, extension: "png" });
    await i.reply({ embeds: [(await guildEmbed(gid, `${user.username}'s avatar`, undefined, BRAND.colours.primary)).setImage(url)] });
    return true;
  }

  if (i.commandName === "userinfo") {
    const user = i.options.getUser("member") || i.user;
    const member = await i.guild.members.fetch(user.id).catch(() => null) as GuildMember | null;
    const embed = await guildEmbed(gid, user.username, `${user}`, BRAND.colours.primary);
    embed.setThumbnail(user.displayAvatarURL()).addFields(
      { name: "User ID", value: user.id, inline: true },
      { name: "Account created", value: timestamp(user.createdAt), inline: true },
      { name: "Joined server", value: timestamp(member?.joinedAt), inline: true },
      { name: "Roles", value: member ? String(member.roles.cache.filter(r => r.name !== "@everyone").size) : "Unknown", inline: true }
    );
    await i.reply({ embeds: [embed], ephemeral: true });
    return true;
  }

  if (i.commandName === "serverinfo") {
    const owner = await i.guild.fetchOwner().catch(() => null);
    const embed = await guildEmbed(gid, i.guild.name, undefined, BRAND.colours.primary);
    embed.setThumbnail(i.guild.iconURL() || null).addFields(
      { name: "Owner", value: owner ? `${owner.user}` : "Unknown", inline: true },
      { name: "Members", value: compactNumber(i.guild.memberCount), inline: true },
      { name: "Created", value: timestamp(i.guild.createdAt), inline: true },
      { name: "Channels", value: compactNumber(i.guild.channels.cache.size), inline: true },
      { name: "Roles", value: compactNumber(i.guild.roles.cache.size), inline: true },
      { name: "Emojis", value: compactNumber(i.guild.emojis.cache.size), inline: true }
    );
    await i.reply({ embeds: [embed], ephemeral: true });
    return true;
  }

  if (i.commandName === "roleinfo") {
    const role = i.options.getRole("role", true);
    const embed = await guildEmbed(gid, role.name, undefined, role.color || BRAND.colours.primary);
    embed.addFields(
      { name: "Role ID", value: role.id, inline: true },
      { name: "Members", value: "members" in role ? compactNumber(role.members.size) : "Unknown", inline: true },
      { name: "Mentionable", value: role.mentionable ? "Yes" : "No", inline: true },
      { name: "Created", value: timestamp("createdAt" in role ? role.createdAt : null), inline: true }
    );
    await i.reply({ embeds: [embed], ephemeral: true });
    return true;
  }

  if (i.commandName === "poll") {
    const answers = i.options.getString("answers", true).split("|").map(x => x.trim()).filter(Boolean).slice(0, 10);
    if (answers.length < 2) await i.reply({ content: "Add at least two answers separated with `|`.", ephemeral: true });
    else {
      await (i.channel as GuildTextBasedChannel).send({
        poll: {
          question: { text: i.options.getString("question", true).slice(0, 300) },
          answers: answers.map(a => ({ text: a.slice(0, 55) })),
          duration: i.options.getInteger("hours") || 24,
          allowMultiselect: i.options.getBoolean("multiple") || false
        }
      });
      await audit(gid, i.user.id, "utility.poll.create", { channelId: i.channelId });
      await i.reply({ content: "Poll posted.", ephemeral: true });
    }
    return true;
  }

  if (i.commandName === "emoji") {
    const sub = i.options.getSubcommand();
    if (sub === "add") {
      try { await addEmoji(i, i.options.getAttachment("image", true), i.options.getString("name", true)); }
      catch (err: any) { await i.reply({ content: String(err?.message || err), ephemeral: true }); }
      return true;
    }
    if (sub === "remove") {
      const wanted = i.options.getString("emoji", true).replace(/[<:a>]/g, "").split(":").pop() || "";
      const emoji = i.guild.emojis.cache.get(wanted) || i.guild.emojis.cache.find(e => e.name?.toLowerCase() === wanted.toLowerCase());
      if (!emoji) await i.reply({ content: "I couldn't find that emoji.", ephemeral: true });
      else { await emoji.delete(`Removed by ${i.user.tag}`); await audit(gid, i.user.id, "utility.emoji.remove", { emojiId: emoji.id, name: emoji.name }); await i.reply({ content: `Removed \`:${emoji.name}:\`.`, ephemeral: true }); }
      return true;
    }
    const emojis = [...i.guild.emojis.cache.values()].map(e => `${e} \`:${e.name}:\``);
    await i.reply({ embeds: [await guildEmbed(gid, "Server emojis", emojis.slice(0, 50).join("\n") || "No custom emojis.", BRAND.colours.primary)], ephemeral: true });
    return true;
  }

  if (i.commandName === "notify") {
    const sub = i.options.getSubcommand();
    if (sub === "add") {
      const keyword = cleanKeyword(i.options.getString("keyword", true));
      await query(`INSERT INTO notify_keywords(guild_id,user_id,keyword) VALUES($1,$2,$3) ON CONFLICT DO NOTHING`, [gid, i.user.id, keyword]);
      await i.reply({ content: `I'll DM you when **${keyword}** is mentioned.`, ephemeral: true });
      return true;
    }
    if (sub === "remove") {
      const keyword = cleanKeyword(i.options.getString("keyword", true));
      await query(`DELETE FROM notify_keywords WHERE guild_id=$1 AND user_id=$2 AND lower(keyword)=lower($3)`, [gid, i.user.id, keyword]);
      await i.reply({ content: `Removed **${keyword}** from your alerts.`, ephemeral: true });
      return true;
    }
    const rows = await query<any>(`SELECT keyword FROM notify_keywords WHERE guild_id=$1 AND user_id=$2 ORDER BY keyword`, [gid, i.user.id]);
    await i.reply({ content: rows.length ? rows.map(r => `• ${r.keyword}`).join("\n") : "You do not have any keyword alerts.", ephemeral: true });
    return true;
  }

  if (i.commandName === "bumpreminder") {
    const sub = i.options.getSubcommand();
    if (sub === "set") {
      const channel = i.options.getChannel("channel", true);
      const minutes = i.options.getInteger("minutes") || 120;
      const message = i.options.getString("message") || "Time to bump the server. Use `/bump` with DISBOARD.";
      await query(`INSERT INTO bump_reminders(guild_id,channel_id,interval_minutes,message,next_at,enabled,updated_by,updated_at) VALUES($1,$2,$3,$4,now()+($3||' minutes')::interval,true,$5,now()) ON CONFLICT(guild_id) DO UPDATE SET channel_id=$2,interval_minutes=$3,message=$4,next_at=now()+($3||' minutes')::interval,enabled=true,updated_by=$5,updated_at=now()`, [gid, channel.id, minutes, message, i.user.id]);
      await i.reply({ content: `Bump reminders enabled in ${channel} every ${minutes} minutes.`, ephemeral: true });
      return true;
    }
    if (sub === "off") {
      await query(`UPDATE bump_reminders SET enabled=false,updated_by=$2,updated_at=now() WHERE guild_id=$1`, [gid, i.user.id]);
      await i.reply({ content: "Bump reminders disabled.", ephemeral: true });
      return true;
    }
    const row = await one<any>(`SELECT * FROM bump_reminders WHERE guild_id=$1`, [gid]);
    await i.reply({ content: row?.enabled ? `Enabled in <#${row.channel_id}> every ${row.interval_minutes} minutes. Next reminder ${timestamp(row.next_at)}.` : "Bump reminders are off.", ephemeral: true });
    return true;
  }

  if (i.commandName === "serverbackup") {
    const sub = i.options.getSubcommand();
    if (sub === "create") {
      const snap = snapshotGuild(i.guild);
      const name = i.options.getString("name") || `Snapshot ${new Date().toLocaleDateString("en-GB")}`;
      const row = (await query<any>(`INSERT INTO server_snapshots(guild_id,name,created_by,snapshot) VALUES($1,$2,$3,$4::jsonb) RETURNING id`, [gid, name, i.user.id, JSON.stringify(snap)]))[0];
      await audit(gid, i.user.id, "utility.snapshot.create", { id: row.id, name });
      await i.reply({ embeds: [await guildSystemEmbed(gid, "Server snapshot saved", `Snapshot **#${row.id}** captured ${snap.roles.length} roles and ${snap.channels.length} channels.`, BRAND.colours.success)], ephemeral: true });
      return true;
    }
    if (sub === "list") {
      const rows = await query<any>(`SELECT id,name,created_by,created_at FROM server_snapshots WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 10`, [gid]);
      await i.reply({ embeds: [await guildEmbed(gid, "Server snapshots", rows.map(r => `**#${r.id}** ${r.name} • ${timestamp(r.created_at)} • <@${r.created_by}>`).join("\n") || "No snapshots yet.", BRAND.colours.primary)], ephemeral: true });
      return true;
    }
    const id = i.options.getInteger("id", true);
    const row = await one<any>(`SELECT * FROM server_snapshots WHERE guild_id=$1 AND id=$2`, [gid, id]);
    if (!row) await i.reply({ content: "Snapshot not found.", ephemeral: true });
    else {
      const snap = row.snapshot || {};
      await i.reply({ embeds: [await guildEmbed(gid, `Snapshot #${row.id}: ${row.name}`, `Roles: **${snap.roles?.length || 0}**\nChannels: **${snap.channels?.length || 0}**\nCreated: ${timestamp(row.created_at)}\n\nThis is a safety snapshot for rebuild/reference. It intentionally does not mass-restore over a live server.`, BRAND.colours.primary)], ephemeral: true });
    }
    return true;
  }

  return false;
}

export async function onUtilityMessage(message: any) {
  if (!message.guildId || message.author?.bot || !message.content || !message.channelId) return;
  const content = String(message.content).toLowerCase();
  const rows = await query<any>(`SELECT * FROM notify_keywords WHERE guild_id=$1 AND user_id<>$2 AND ($3 LIKE '%' || lower(keyword) || '%') AND (last_triggered_at IS NULL OR last_triggered_at<now()-interval '30 minutes') LIMIT 20`, [message.guildId, message.author.id, content]);
  for (const row of rows) {
    const user = await message.client.users.fetch(row.user_id).catch(() => null);
    if (!user) continue;
    const recently = row.last_triggered_at && Date.now() - new Date(row.last_triggered_at).getTime() < notifyCooldownMs;
    if (recently) continue;
    await user.send(`Keyword alert for **${row.keyword}** in **${message.guild.name}**: ${message.url}`).catch(() => {});
    await query(`UPDATE notify_keywords SET last_triggered_at=now() WHERE guild_id=$1 AND user_id=$2 AND keyword=$3`, [row.guild_id, row.user_id, row.keyword]);
  }
}

export async function runUtilityTick(client: Client) {
  const due = await query<any>(`SELECT * FROM bump_reminders WHERE enabled=true AND next_at<=now()`);
  for (const row of due) {
    const ch = await client.channels.fetch(row.channel_id).catch(() => null);
    if (ch?.isTextBased()) await (ch as TextChannel).send(row.message).catch(() => {});
    await query(`UPDATE bump_reminders SET next_at=now()+(interval_minutes||' minutes')::interval,updated_at=now() WHERE guild_id=$1`, [row.guild_id]);
  }
}
