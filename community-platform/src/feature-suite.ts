import {
  ActionRowBuilder, ButtonBuilder, ButtonStyle, ChannelType, Client, ContextMenuCommandBuilder,
  ApplicationCommandType, PermissionFlagsBits, SlashCommandBuilder, TextChannel
} from "discord.js";
import { audit, getFeature, one, query } from "./db.js";
import { config } from "./config.js";
import { grantComp, listPlans, refreshExpiredEntitlements, reconcileActiveEntitlementRoles } from "./billing.js";
import { brandEmbed, BRAND } from "./brand.js";
import { getEconomyProfile, levelFromXp, recordEconomyEvent } from "./economy-core.js";

const fmt=(n:number)=>Math.round(n).toLocaleString("en-GB");
let lastEntitlementRoleSweep=0;

const slash:any[]=[
  new SlashCommandBuilder().setName("rank").setDescription("View community rank").addUserOption(o=>o.setName("member").setDescription("Member")),
  new SlashCommandBuilder().setName("leaderboard").setDescription("View a community leaderboard").addStringOption(o=>o.setName("type").setDescription("Leaderboard").setRequired(true).addChoices(
    {name:"XP",value:"xp"},{name:"Season XP",value:"season"},{name:"Live Coins",value:"coins"},{name:"Kudos",value:"kudos"}
  )),
  new SlashCommandBuilder().setName("referral").setDescription("View or create your Premium referral code"),
  new SlashCommandBuilder().setName("giftpremium").setDescription("Gift Premium access").setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true))
    .addIntegerOption(o=>o.setName("days").setDescription("Days").setRequired(true).setMinValue(1).setMaxValue(365))
    .addStringOption(o=>o.setName("plan").setDescription("Plan slug")),
  new SlashCommandBuilder().setName("giveaway").setDescription("Manage giveaways").setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand(s=>s.setName("start").setDescription("Start a giveaway")
      .addStringOption(o=>o.setName("prize").setDescription("Prize").setRequired(true))
      .addIntegerOption(o=>o.setName("minutes").setDescription("Duration in minutes").setRequired(true).setMinValue(1))
      .addIntegerOption(o=>o.setName("winners").setDescription("Number of winners").setMinValue(1).setMaxValue(20))
      .addRoleOption(o=>o.setName("required_role").setDescription("Required role"))
      .addIntegerOption(o=>o.setName("min_member_days").setDescription("Minimum days in server").setMinValue(0))
      .addIntegerOption(o=>o.setName("min_level").setDescription("Minimum community level").setMinValue(0))
      .addBooleanOption(o=>o.setName("verified_only").setDescription("Require completed verification"))
      .addRoleOption(o=>o.setName("blacklist_role").setDescription("Role excluded from entry"))
      .addUserOption(o=>o.setName("blacklist_user").setDescription("Member excluded from entry"))
      .addIntegerOption(o=>o.setName("premium_bonus").setDescription("Bonus entries for Premium").setMinValue(0).setMaxValue(20))
      .addIntegerOption(o=>o.setName("booster_bonus").setDescription("Bonus entries for server boosters").setMinValue(0).setMaxValue(20))
      .addIntegerOption(o=>o.setName("level_bonus_at").setDescription("Level needed for bonus entries").setMinValue(1))
      .addIntegerOption(o=>o.setName("level_bonus_entries").setDescription("Bonus entries at that level").setMinValue(0).setMaxValue(20))
      .addIntegerOption(o=>o.setName("tenure_bonus_days").setDescription("Server days needed for tenure bonus").setMinValue(1))
      .addIntegerOption(o=>o.setName("tenure_bonus_entries").setDescription("Tenure bonus entries").setMinValue(0).setMaxValue(20)))
    .addSubcommand(s=>s.setName("reroll").setDescription("Reroll a finished giveaway").addIntegerOption(o=>o.setName("id").setDescription("Giveaway ID").setRequired(true))),
  new SlashCommandBuilder().setName("note").setDescription("Add a private staff note").setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addStringOption(o=>o.setName("note").setDescription("Note").setRequired(true)),
  new SlashCommandBuilder().setName("timeout").setDescription("Timeout a member").setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addIntegerOption(o=>o.setName("minutes").setDescription("Minutes").setRequired(true).setMinValue(1).setMaxValue(40320)).addStringOption(o=>o.setName("reason").setDescription("Reason")),
  new SlashCommandBuilder().setName("kick").setDescription("Kick a member").setDefaultMemberPermissions(PermissionFlagsBits.KickMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addStringOption(o=>o.setName("reason").setDescription("Reason")),
  new SlashCommandBuilder().setName("ban").setDescription("Ban a member").setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addStringOption(o=>o.setName("reason").setDescription("Reason")),
  new SlashCommandBuilder().setName("purge").setDescription("Delete recent messages").setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addIntegerOption(o=>o.setName("count").setDescription("Messages").setRequired(true).setMinValue(1).setMaxValue(100)),
  new SlashCommandBuilder().setName("slowmode").setDescription("Set channel slowmode").setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels)
    .addIntegerOption(o=>o.setName("seconds").setDescription("Seconds, 0 disables").setRequired(true).setMinValue(0).setMaxValue(21600)),
  new SlashCommandBuilder().setName("lock").setDescription("Lock this channel").setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),
  new SlashCommandBuilder().setName("unlock").setDescription("Unlock this channel").setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),
  new SlashCommandBuilder().setName("nick").setDescription("Change a member nickname").setDefaultMemberPermissions(PermissionFlagsBits.ManageNicknames)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addStringOption(o=>o.setName("nickname").setDescription("New nickname")),
  new SlashCommandBuilder().setName("role").setDescription("Add or remove a member role").setDefaultMemberPermissions(PermissionFlagsBits.ManageRoles)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)).addRoleOption(o=>o.setName("role").setDescription("Role").setRequired(true))
    .addStringOption(o=>o.setName("action").setDescription("Action").setRequired(true).addChoices({name:"Add",value:"add"},{name:"Remove",value:"remove"})),
  new SlashCommandBuilder().setName("event").setDescription("Create a Discord scheduled event").setDefaultMemberPermissions(PermissionFlagsBits.ManageEvents)
    .addStringOption(o=>o.setName("name").setDescription("Event name").setRequired(true))
    .addIntegerOption(o=>o.setName("minutes_from_now").setDescription("Starts in minutes").setRequired(true).setMinValue(1))
    .addIntegerOption(o=>o.setName("duration_minutes").setDescription("Duration").setMinValue(15))
    .addStringOption(o=>o.setName("description").setDescription("Description")),
  new SlashCommandBuilder().setName("achievements").setDescription("View a member's achievements").addUserOption(o=>o.setName("member").setDescription("Member"))
];

const contexts=[
  new ContextMenuCommandBuilder().setName("View member profile").setType(ApplicationCommandType.User),
  new ContextMenuCommandBuilder().setName("Open staff history").setType(ApplicationCommandType.User).setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
  new ContextMenuCommandBuilder().setName("Give kudos").setType(ApplicationCommandType.Message),
  new ContextMenuCommandBuilder().setName("Report message").setType(ApplicationCommandType.Message)
];
export const featureCommandData=[...slash,...contexts].map(c=>c.toJSON());

async function commandAllowed(i:any){
  const row=await one<any>(`SELECT * FROM command_settings WHERE guild_id=$1 AND command_name=$2`,[i.guildId,i.commandName]);
  if(!row)return true;
  if(!row.enabled){await i.reply({content:"That command is currently disabled.",ephemeral:true});return false;}
  if(row.channel_ids?.length&&!row.channel_ids.includes(i.channelId)){await i.reply({content:"That command isn't enabled in this channel.",ephemeral:true});return false;}
  if(row.role_ids?.length){const m=await i.guild.members.fetch(i.user.id);if(!m.roles.cache.some((r:any)=>row.role_ids.includes(r.id))){await i.reply({content:"You don't have a role allowed to use that command.",ephemeral:true});return false;}}
  if(row.premium_only){const e=await one<any>(`SELECT 1 FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND active=true AND (expires_at IS NULL OR expires_at>now())`,[i.guildId,i.user.id]);if(!e){await i.reply({content:"💎 This is a Premium feature. Use `/premium` to see access options.",ephemeral:true});return false;}}
  return true;
}

async function memberProfile(guildId:string,user:any){
  const [profile,stats,premium]=await Promise.all([
    getEconomyProfile(guildId,user.id),
    one<any>(`SELECT * FROM member_stats WHERE guild_id=$1 AND user_id=$2`,[guildId,user.id]),
    one<any>(`SELECT 1 FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND active=true AND (expires_at IS NULL OR expires_at>now())`,[guildId,user.id])
  ]);
  return brandEmbed(`${user.username} • Community profile`,undefined,premium?BRAND.colours.premium:BRAND.colours.primary).setThumbnail(user.displayAvatarURL()).addFields(
    {name:"Level",value:`${profile.level} • ${fmt(Number(profile.eco.xp_total||0))} XP`,inline:true},
    {name:"Live Coins",value:`${fmt(Number(profile.eco.coins_balance||0))} 🪙`,inline:true},
    {name:"Server rank",value:`#${profile.rank}`,inline:true},
    {name:"Kudos",value:fmt(Number(stats?.thanks_received||0)),inline:true},
    {name:"Streak",value:`${Number(profile.streak.current_streak||0)} days`,inline:true},
    {name:"Achievements",value:String(profile.achievements.length),inline:true}
  );
}

export async function handleFeatureAutocomplete(_i:any){return false;}

export async function handleFeatureCommand(client:Client,i:any){
  const names=new Set(slash.map(c=>c.name));if(!names.has(i.commandName)||!i.guildId||!i.guild)return false;
  if(!await commandAllowed(i))return true;
  const gid=i.guildId,uid=i.user.id;

  if(i.commandName==="rank"){
    const u=i.options.getUser("member")||i.user,p=await getEconomyProfile(gid,u.id);
    const stats=await one<any>(`SELECT thanks_received FROM member_stats WHERE guild_id=$1 AND user_id=$2`,[gid,u.id]);
    await i.reply({embeds:[brandEmbed(`${u.username}'s community rank`,`**#${p.rank}** • ${fmt(Number(p.eco.xp_total||0))} XP • ${fmt(Number(p.eco.coins_balance||0))} Live Coins • ${fmt(Number(stats?.thanks_received||0))} kudos`,BRAND.colours.primary).setThumbnail(u.displayAvatarURL())]});return true;
  }

  if(i.commandName==="leaderboard"){
    const type=i.options.getString("type",true);let rows:any[]=[];
    if(type==="kudos")rows=await query<any>(`SELECT user_id,thanks_received value FROM member_stats WHERE guild_id=$1 ORDER BY thanks_received DESC LIMIT 10`,[gid]);
    else if(type==="coins")rows=await query<any>(`SELECT user_id,coins_balance value FROM member_economy WHERE guild_id=$1 ORDER BY coins_balance DESC LIMIT 10`,[gid]);
    else if(type==="season")rows=await query<any>(`SELECT m.user_id,m.xp_earned value FROM season_member_stats m JOIN economy_seasons s ON s.id=m.season_id WHERE s.guild_id=$1 AND s.active=true ORDER BY m.xp_earned DESC LIMIT 10`,[gid]);
    else rows=await query<any>(`SELECT user_id,xp_total value FROM member_economy WHERE guild_id=$1 ORDER BY xp_total DESC LIMIT 10`,[gid]);
    const label=type==="kudos"?"Kudos":type==="coins"?"Live Coins":type==="season"?"Season XP":"XP",suffix=type==="coins"?" 🪙":type==="kudos"?" kudos":" XP";
    await i.reply({embeds:[brandEmbed(`🏆 ${label} leaderboard`,rows.map((r,n)=>`**${n+1}.** <@${r.user_id}> • ${fmt(Number(r.value||0))}${suffix}`).join("\n")||"No data yet.",BRAND.colours.premium)]});return true;
  }

  if(i.commandName==="referral"){
    const enabled=(await getFeature(gid,"premium_billing",{referralsEnabled:true})).config.referralsEnabled!==false;
    if(!enabled){await i.reply({content:"Referrals are disabled.",ephemeral:true});return true;}
    let ref=await one<any>(`SELECT * FROM referral_codes WHERE guild_id=$1 AND owner_discord_user_id=$2 AND active=true ORDER BY created_at LIMIT 1`,[gid,uid]);
    if(!ref){
      const base=i.user.username.toUpperCase().replace(/[^A-Z0-9]/g,"").slice(0,10)||"MEMBER";let code=base,n=1;
      while(await one(`SELECT 1 FROM referral_codes WHERE guild_id=$1 AND code=$2`,[gid,code]))code=`${base}${++n}`;
      ref=(await query<any>(`INSERT INTO referral_codes(guild_id,code,owner_discord_user_id,reward_type,reward_value) VALUES($1,$2,$3,'none',0) RETURNING *`,[gid,code,uid]))[0];
    }
    await i.reply({embeds:[brandEmbed("🔗 Your referral code",`Code: **${ref.code}**\nCheckout starts: **${ref.clicks||0}**\nConversions: **${ref.conversions||0}**`,BRAND.colours.primary)],ephemeral:true});return true;
  }

  if(i.commandName==="giftpremium"){
    const u=i.options.getUser("member",true),days=i.options.getInteger("days",true),slug=i.options.getString("plan");
    const plans=await listPlans(gid,true),plan=slug?plans.find(p=>p.slug===slug):plans[0];
    if(!plan){await i.reply({content:"No Premium plan is configured.",ephemeral:true});return true;}
    await grantComp(gid,u.id,plan.id,days,i.user.id);
    await i.reply({content:`💎 ${u} has ${days} days of ${plan.name}.`,ephemeral:true});return true;
  }

  if(i.commandName==="giveaway"){
    const sub=i.options.getSubcommand();
    if(sub==="start"){
      const feature=await getFeature(gid,"giveaways",{channelId:"",minAccountAgeDays:3});
      const prize=i.options.getString("prize",true),minutes=i.options.getInteger("minutes",true),winnerCount=i.options.getInteger("winners")||1,required=i.options.getRole("required_role"),blacklist=i.options.getRole("blacklist_role"),blacklistUser=i.options.getUser("blacklist_user");
      const minMemberDays=i.options.getInteger("min_member_days")||0,minLevel=i.options.getInteger("min_level")||0,verifiedOnly=i.options.getBoolean("verified_only")||false;
      const bonusRules={premium:Number(i.options.getInteger("premium_bonus")||0),booster:Number(i.options.getInteger("booster_bonus")||0),levelAt:Number(i.options.getInteger("level_bonus_at")||0),levelEntries:Number(i.options.getInteger("level_bonus_entries")||0),tenureDays:Number(i.options.getInteger("tenure_bonus_days")||0),tenureEntries:Number(i.options.getInteger("tenure_bonus_entries")||0)};
      const channelId=String(feature.config.channelId||i.channelId),ends=new Date(Date.now()+minutes*60000);
      const row=(await query<any>(`INSERT INTO giveaways(guild_id,channel_id,prize,winner_count,required_role_id,min_account_age_days,min_member_days,min_level,verified_only,blacklist_user_ids,blacklist_role_ids,bonus_rules,reroll_exclude_previous,ends_at,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,true,$13,$14) RETURNING *`,[gid,channelId,prize,winnerCount,required?.id||null,Number(feature.config.minAccountAgeDays||0),minMemberDays,minLevel,verifiedOnly,blacklistUser?[blacklistUser.id]:[],blacklist?[blacklist.id]:[],JSON.stringify(bonusRules),ends,i.user.id]))[0];
      const button=new ActionRowBuilder<ButtonBuilder>().addComponents(new ButtonBuilder().setCustomId(`giveaway:${row.id}`).setLabel("Enter giveaway").setStyle(ButtonStyle.Success));
      const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased()){await i.reply({content:"Giveaway channel isn't available.",ephemeral:true});return true;}
      const requirements=[required?`Role: ${required}`:"",minMemberDays?`${minMemberDays}+ days in server`:"",minLevel?`Level ${minLevel}+`:"",verifiedOnly?"Verified members only":""].filter(Boolean);
      const msg=await (ch as TextChannel).send({embeds:[brandEmbed(`🎉 ${prize}`,`Ends <t:${Math.floor(ends.getTime()/1000)}:R>\nWinners: **${winnerCount}**${requirements.length?`\nRequirements: ${requirements.join(" • ")}`:""}`,BRAND.colours.premium)],components:[button]});
      await query(`UPDATE giveaways SET message_id=$1 WHERE id=$2`,[msg.id,row.id]);await i.reply({content:`Giveaway posted in ${ch}.`,ephemeral:true});return true;
    }
    const id=i.options.getInteger("id",true),g=await one<any>(`SELECT * FROM giveaways WHERE id=$1 AND guild_id=$2`,[id,gid]);
    if(!g){await i.reply({content:"Giveaway not found.",ephemeral:true});return true;}
    const previous=new Set<string>((g.winners||[]).map(String)),entries=await query<any>(`SELECT user_id,entries FROM giveaway_entries WHERE giveaway_id=$1 ORDER BY random()`,[id]);
    const pool:string[]=[];for(const e of entries){if(g.reroll_exclude_previous&&previous.has(String(e.user_id)))continue;for(let n=0;n<Math.max(1,Number(e.entries||1));n++)pool.push(String(e.user_id));}
    const winners:string[]=[];for(const userId of pool.sort(()=>Math.random()-.5)){if(!winners.includes(userId))winners.push(userId);if(winners.length>=Math.max(1,Number(g.winner_count||1)))break;}
    await i.reply({content:winners.length?`🎉 Reroll: ${winners.map(x=>`<@${x}>`).join(", ")}`:"No eligible entries.",ephemeral:false});return true;
  }

  if(i.commandName==="note"){
    const u=i.options.getUser("member",true),note=i.options.getString("note",true);
    await query(`INSERT INTO staff_notes(guild_id,user_id,staff_id,note) VALUES($1,$2,$3,$4)`,[gid,u.id,uid,note]);await audit(gid,uid,"moderation.note",{userId:u.id,note});await i.reply({content:"Staff note saved.",ephemeral:true});return true;
  }

  if(i.commandName==="timeout"){
    const u=i.options.getUser("member",true),minutes=i.options.getInteger("minutes",true),reason=i.options.getString("reason")||"Moderator action";const m=await i.guild.members.fetch(u.id);
    await m.timeout(minutes*60000,reason);await audit(gid,uid,"moderation.timeout",{userId:u.id,minutes,reason});await i.reply({content:`${u} timed out for ${minutes} minutes.`,ephemeral:true});return true;
  }

  if(i.commandName==="kick"){const u=i.options.getUser("member",true),reason=i.options.getString("reason")||"Moderator action";const m=await i.guild.members.fetch(u.id);await m.kick(reason);await audit(gid,uid,"moderation.kick",{userId:u.id,reason});await i.reply({content:`${u.username} kicked.`,ephemeral:true});return true;}
  if(i.commandName==="ban"){const u=i.options.getUser("member",true),reason=i.options.getString("reason")||"Moderator action";await i.guild.members.ban(u.id,{reason});await audit(gid,uid,"moderation.ban",{userId:u.id,reason});await i.reply({content:`${u.username} banned.`,ephemeral:true});return true;}

  if(i.commandName==="purge"){const count=i.options.getInteger("count",true);if(!i.channel||!("bulkDelete" in i.channel)){await i.reply({content:"This channel doesn't support bulk delete.",ephemeral:true});return true;}const deleted=await (i.channel as any).bulkDelete(count,true);await audit(gid,uid,"moderation.purge",{channelId:i.channelId,count:deleted.size});await i.reply({content:`Deleted ${deleted.size} messages.`,ephemeral:true});return true;}
  if(i.commandName==="slowmode"){const seconds=i.options.getInteger("seconds",true);if(!i.channel||!("setRateLimitPerUser" in i.channel)){await i.reply({content:"This channel doesn't support slowmode.",ephemeral:true});return true;}await (i.channel as any).setRateLimitPerUser(seconds);await audit(gid,uid,"moderation.slowmode",{channelId:i.channelId,seconds});await i.reply({content:`Slowmode set to ${seconds}s.`,ephemeral:true});return true;}
  if(i.commandName==="lock"||i.commandName==="unlock"){if(!i.channel||!("permissionOverwrites" in i.channel)){await i.reply({content:"This channel can't be locked.",ephemeral:true});return true;}const lock=i.commandName==="lock";await (i.channel as any).permissionOverwrites.edit(i.guild.roles.everyone,{SendMessages:lock?false:null});await audit(gid,uid,`moderation.${i.commandName}`,{channelId:i.channelId});await i.reply({content:lock?"🔒 Channel locked.":"🔓 Channel unlocked.",ephemeral:true});return true;}
  if(i.commandName==="nick"){const u=i.options.getUser("member",true),nickname=i.options.getString("nickname");const m=await i.guild.members.fetch(u.id);await m.setNickname(nickname||null);await audit(gid,uid,"moderation.nick",{userId:u.id,nickname});await i.reply({content:"Nickname updated.",ephemeral:true});return true;}
  if(i.commandName==="role"){const u=i.options.getUser("member",true),role=i.options.getRole("role",true),action=i.options.getString("action",true),m=await i.guild.members.fetch(u.id);if(action==="add")await m.roles.add(role.id);else await m.roles.remove(role.id);await audit(gid,uid,"moderation.role",{userId:u.id,roleId:role.id,action});await i.reply({content:`${action==="add"?"Added":"Removed"} @${role.name} ${action==="add"?"to":"from"} ${u.username}.`,ephemeral:true});return true;}

  if(i.commandName==="event"){
    const name=i.options.getString("name",true),starts=i.options.getInteger("minutes_from_now",true),duration=i.options.getInteger("duration_minutes")||60,description=i.options.getString("description")||"";
    const start=new Date(Date.now()+starts*60000),end=new Date(start.getTime()+duration*60000);
    await i.guild.scheduledEvents.create({name,description,scheduledStartTime:start,scheduledEndTime:end,privacyLevel:2,entityType:3,entityMetadata:{location:"Discord"}});
    await i.reply({content:`📅 Event **${name}** created.`,ephemeral:true});return true;
  }

  if(i.commandName==="achievements"){
    const u=i.options.getUser("member")||i.user;
    const rows=await query<any>(`SELECT a.achievement_key,d.name,d.description,d.icon FROM achievements a LEFT JOIN achievement_definitions d ON d.guild_id=a.guild_id AND d.achievement_key=a.achievement_key WHERE a.guild_id=$1 AND a.user_id=$2 ORDER BY a.awarded_at DESC`,[gid,u.id]);
    const body=rows.length?rows.slice(0,20).map(x=>`${x.icon||"🏅"} **${x.name||x.achievement_key.replaceAll("_"," ")}**${x.description?`\n↳ ${x.description}`:""}`).join("\n"):`${u.username} hasn't unlocked an achievement yet.`;
    await i.reply({embeds:[brandEmbed(`${u.username}'s achievements`,body,BRAND.colours.premium).setThumbnail(u.displayAvatarURL())],ephemeral:true});return true;
  }

  return false;
}

export async function handleContextCommand(i:any){
  if(!i.guildId)return false;
  if(i.commandName==="View member profile"&&i.isUserContextMenuCommand()){await i.reply({embeds:[await memberProfile(i.guildId,i.targetUser)],ephemeral:true});return true;}
  if(i.commandName==="Open staff history"&&i.isUserContextMenuCommand()){
    const [warnings,notes]=await Promise.all([query<any>(`SELECT * FROM warnings WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC LIMIT 8`,[i.guildId,i.targetUser.id]),query<any>(`SELECT * FROM staff_notes WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC LIMIT 8`,[i.guildId,i.targetUser.id])]);
    const body=[...warnings.map(x=>`⚠ ${x.reason}`),...notes.map(x=>`📝 ${x.note}`)].slice(0,12).join("\n")||"No staff history.";
    await i.reply({embeds:[brandEmbed(`Staff history • ${i.targetUser.username}`,body,BRAND.colours.neutral)],ephemeral:true});return true;
  }
  if(i.commandName==="Give kudos"&&i.isMessageContextMenuCommand()){
    if(i.targetMessage.author.bot||i.targetMessage.author.id===i.user.id){await i.reply({content:"Choose a message from another member.",ephemeral:true});return true;}
    const feature=await getFeature(i.guildId,"reputation",{dailyLimit:5});if(!feature.enabled){await i.reply({content:"Kudos are disabled.",ephemeral:true});return true;}
    const duplicate=await one<any>(`SELECT 1 FROM reputation_events WHERE guild_id=$1 AND giver_id=$2 AND source_message_id=$3`,[i.guildId,i.user.id,i.targetMessage.id]);
    if(duplicate){await i.reply({content:"You've already given kudos for that message.",ephemeral:true});return true;}
    const count=await one<any>(`SELECT count(*) c FROM reputation_events WHERE guild_id=$1 AND giver_id=$2 AND created_at>now()-interval '24 hours'`,[i.guildId,i.user.id]);
    if(Number(count?.c||0)>=Number(feature.config.dailyLimit||5)){await i.reply({content:"You've reached today's kudos limit.",ephemeral:true});return true;}
    await query(`INSERT INTO reputation_events(guild_id,giver_id,receiver_id,reason,category,comment,source_message_id) VALUES($1,$2,$3,'Message kudos','Helpful',NULL,$4)`,[i.guildId,i.user.id,i.targetMessage.author.id,i.targetMessage.id]);
    await query(`INSERT INTO member_stats(guild_id,user_id,thanks_received,helpful_actions) VALUES($1,$2,1,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET thanks_received=member_stats.thanks_received+1,helpful_actions=member_stats.helpful_actions+1`,[i.guildId,i.targetMessage.author.id]);
    await recordEconomyEvent(i.guildId,i.user.id,"kudos_given",{sourceType:"message_kudos",sourceId:i.targetMessage.id,idempotencyBase:`message-kudos:${i.targetMessage.id}:${i.user.id}`});
    await i.reply({content:`👏 Kudos given to ${i.targetMessage.author}.`,ephemeral:true});return true;
  }
  if(i.commandName==="Report message"&&i.isMessageContextMenuCommand()){
    const evidence=`Message by ${i.targetMessage.author.username}: ${i.targetMessage.content.slice(0,800)}\n${i.targetMessage.url}`;
    await query(`INSERT INTO scam_cases(guild_id,reporter_id,accused_id,evidence) VALUES($1,$2,$3,$4)`,[i.guildId,i.user.id,i.targetMessage.author.id,evidence]);
    await i.reply({content:"Report sent to staff.",ephemeral:true});return true;
  }
  return false;
}

export async function handleComponent(client:Client,i:any){
  if(!i.guildId||!i.isButton())return false;
  if(i.customId.startsWith("giveaway:")){
    const id=Number(i.customId.split(":")[1]),g=await one<any>(`SELECT * FROM giveaways WHERE id=$1 AND guild_id=$2 AND status='LIVE' AND ends_at>now()`,[id,i.guildId]);
    if(!g){await i.reply({content:"This giveaway has ended.",ephemeral:true});return true;}
    const member=await i.guild.members.fetch(i.user.id);
    if((g.blacklist_user_ids||[]).includes(i.user.id)||member.roles.cache.some((r:any)=>(g.blacklist_role_ids||[]).includes(r.id))){await i.reply({content:"You're not eligible for this giveaway.",ephemeral:true});return true;}
    if(g.required_role_id&&!member.roles.cache.has(g.required_role_id)){await i.reply({content:"You don't have the required role.",ephemeral:true});return true;}
    const ageDays=(Date.now()-i.user.createdTimestamp)/86400000;if(ageDays<Number(g.min_account_age_days||0)){await i.reply({content:"Your Discord account is too new for this giveaway.",ephemeral:true});return true;}
    const memberDays=member.joinedTimestamp?(Date.now()-member.joinedTimestamp)/86400000:0;if(memberDays<Number(g.min_member_days||0)){await i.reply({content:`You need to have been in the server for ${g.min_member_days} days.`,ephemeral:true});return true;}
    const eco=await one<any>(`SELECT xp_total FROM member_economy WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]),level=levelFromXp(Number(eco?.xp_total||0));if(level<Number(g.min_level||0)){await i.reply({content:`You need to be level ${g.min_level} to enter.`,ephemeral:true});return true;}
    if(g.verified_only){const verified=await one<any>(`SELECT 1 FROM onboarding_answers WHERE guild_id=$1 AND user_id=$2 AND verified=true`,[i.guildId,i.user.id]);if(!verified){await i.reply({content:"Complete server verification before entering.",ephemeral:true});return true;}}
    const rules=g.bonus_rules||{};let entries=1;
    if(Number(rules.premium||0)>0){const premium=await one<any>(`SELECT 1 FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND active=true AND (expires_at IS NULL OR expires_at>now())`,[i.guildId,i.user.id]);if(premium)entries+=Number(rules.premium);}
    if(Number(rules.booster||0)>0&&member.premiumSinceTimestamp)entries+=Number(rules.booster);
    if(Number(rules.levelAt||0)>0&&level>=Number(rules.levelAt))entries+=Number(rules.levelEntries||0);
    if(Number(rules.tenureDays||0)>0&&memberDays>=Number(rules.tenureDays))entries+=Number(rules.tenureEntries||0);
    const inserted=await query<any>(`INSERT INTO giveaway_entries(giveaway_id,user_id,entries) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING user_id`,[id,i.user.id,Math.max(1,entries)]);
    await i.reply({content:inserted.length?`🎟️ You're entered with **${Math.max(1,entries)}** entr${entries===1?"y":"ies"}.`:"You're already entered.",ephemeral:true});return true;
  }
  if(i.customId.startsWith("role:")){
    const roleId=i.customId.slice(5),member=await i.guild.members.fetch(i.user.id),role=i.guild.roles.cache.get(roleId);if(!role){await i.reply({content:"That role is no longer available.",ephemeral:true});return true;}
    if(member.roles.cache.has(roleId)){await member.roles.remove(roleId);await i.reply({content:`Removed @${role.name}.`,ephemeral:true});}else{await member.roles.add(roleId);await i.reply({content:`Added @${role.name}.`,ephemeral:true});}return true;
  }
  return false;
}

export async function onMemberActivity(message:any){
  if(!message.guildId||message.author?.bot)return;
  await query(`INSERT INTO member_stats(guild_id,user_id,messages,last_message_at,last_active_date) VALUES($1,$2,1,now(),current_date)
    ON CONFLICT(guild_id,user_id) DO UPDATE SET messages=member_stats.messages+1,last_message_at=now(),last_active_date=current_date`,[message.guildId,message.author.id]);
  await query(`INSERT INTO activity_daily(guild_id,user_id,activity_date,messages) VALUES($1,$2,current_date,1) ON CONFLICT(guild_id,user_id,activity_date) DO UPDATE SET messages=activity_daily.messages+1`,[message.guildId,message.author.id]);
  await query(`INSERT INTO server_metrics_daily(guild_id,metric_date,messages) VALUES($1,current_date,1) ON CONFLICT(guild_id,metric_date) DO UPDATE SET messages=server_metrics_daily.messages+1`,[message.guildId]);
}

export async function onMemberJoinLeave(guildId:string,type:"joins"|"leaves"){
  await query(`INSERT INTO server_metrics_daily(guild_id,metric_date,${type}) VALUES($1,current_date,1) ON CONFLICT(guild_id,metric_date) DO UPDATE SET ${type}=server_metrics_daily.${type}+1`,[guildId]);
}

function cronMatches(expr:string,d=new Date()){
  const parts=expr.split(" ");const min=parts[0]||"*",hour=parts[1]||"*",dow=parts[4]||"*";const check=(part:string,value:number)=>part==="*"||part.split(",").map(Number).includes(value);
  return check(min,d.getMinutes())&&check(hour,d.getHours())&&check(dow,d.getDay());
}

export async function runAutomationTick(client:Client){
  const scheduled=await query<any>(`SELECT * FROM scheduled_messages WHERE enabled=true`);
  const minuteKey=new Date().toISOString().slice(0,16);
  for(const s of scheduled){
    if(!cronMatches(s.cron_expression))continue;
    const key=`schedule:${s.id}:${minuteKey}`;const seen=await one<any>(`SELECT 1 FROM audit_log WHERE guild_id=$1 AND action='automation.schedule.sent' AND details->>'key'=$2 LIMIT 1`,[s.guild_id,key]);if(seen)continue;
    const ch=await client.channels.fetch(s.channel_id).catch(()=>null);if(ch?.isTextBased()){await (ch as TextChannel).send(s.content).catch(console.error);await audit(s.guild_id,"system","automation.schedule.sent",{key,scheduleId:s.id});}
  }

  const due=await query<any>(`SELECT * FROM giveaways WHERE status='LIVE' AND ends_at<=now() ORDER BY ends_at LIMIT 20`);
  for(const g of due){
    const entries=await query<any>(`SELECT user_id,entries FROM giveaway_entries WHERE giveaway_id=$1`,[g.id]),pool:string[]=[];
    for(const e of entries)for(let n=0;n<Math.max(1,Number(e.entries||1));n++)pool.push(String(e.user_id));
    for(let n=pool.length-1;n>0;n--){const j=Math.floor(Math.random()*(n+1));[pool[n],pool[j]]=[pool[j]!,pool[n]!];}
    const winners:string[]=[];for(const userId of pool){if(!winners.includes(userId))winners.push(userId);if(winners.length>=Math.max(1,Number(g.winner_count||1)))break;}
    await query(`UPDATE giveaways SET status='ENDED',winners=$2 WHERE id=$1 AND status='LIVE'`,[g.id,winners]);
    const ch=await client.channels.fetch(g.channel_id).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send(winners.length?`🎉 **${g.prize}** winner${winners.length===1?"":"s"}: ${winners.map(x=>`<@${x}>`).join(", ")}`:`Giveaway **${g.prize}** ended with no eligible entries.`).catch(()=>{});
  }

  await refreshExpiredEntitlements();
  if(Date.now()-lastEntitlementRoleSweep>5*60_000){lastEntitlementRoleSweep=Date.now();await reconcileActiveEntitlementRoles(config.targetGuildId);}
}
