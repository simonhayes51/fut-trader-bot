import {
  ActionRowBuilder, AuditLogEvent, ButtonBuilder, ButtonStyle, ChannelType, Client, ContextMenuCommandBuilder,
  ApplicationCommandType, GuildMember, ModalBuilder, PermissionFlagsBits, SlashCommandBuilder, StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder, TextChannel, TextInputBuilder, TextInputStyle
} from "discord.js";
import { audit, getFeature, one, query } from "./db.js";
import { config } from "./config.js";
import { awardCurrency, getEconomyProfile, levelFromXp, recordEconomyEvent } from "./economy-core.js";
import { brandEmbed, systemEmbed, BRAND } from "./brand.js";
import { grantComp, listPlans } from "./billing.js";
import { claimDaily } from "./economy.js";

const joinWindows=new Map<string,number[]>();
const healthLastRun=new Map<string,number>();
const statusLastRun=new Map<string,number>();
const startedAt=Date.now();
const fmt=(n:number)=>Math.round(n).toLocaleString("en-GB");

export const v5CommandData=[
  new SlashCommandBuilder().setName("afk").setDescription("Set or clear your AFK status")
    .addStringOption(o=>o.setName("reason").setDescription("Why you're away").setMaxLength(180)),
  new SlashCommandBuilder().setName("birthday").setDescription("Set or clear your birthday")
    .addSubcommand(s=>s.setName("set").setDescription("Set your birthday")
      .addIntegerOption(o=>o.setName("day").setDescription("Day").setRequired(true).setMinValue(1).setMaxValue(31))
      .addIntegerOption(o=>o.setName("month").setDescription("Month").setRequired(true).setMinValue(1).setMaxValue(12))
      .addBooleanOption(o=>o.setName("public").setDescription("Allow public birthday announcements")))
    .addSubcommand(s=>s.setName("clear").setDescription("Remove your saved birthday")),
  new SlashCommandBuilder().setName("kudosboard").setDescription("View the kudos leaderboard")
    .addStringOption(o=>o.setName("period").setDescription("Period").addChoices(
      {name:"This week",value:"week"},{name:"This month",value:"month"},{name:"All time",value:"all"}
    ))
    .addStringOption(o=>o.setName("category").setDescription("Kudos category").addChoices(
      {name:"All categories",value:"all"},{name:"Good Trade / Call",value:"Good trade"},{name:"Helpful",value:"Helpful"},
      {name:"Community",value:"Community"},{name:"Creator",value:"Creator"},{name:"Support",value:"Support"}
    )),
  new SlashCommandBuilder().setName("verify").setDescription("Start or complete server verification"),
  new SlashCommandBuilder().setName("system").setDescription("Publish EAFC.Live system panels").setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand(s=>s.setName("ticket-panel").setDescription("Post the ticket dropdown panel")
      .addChannelOption(o=>o.setName("channel").setDescription("Ticket panel channel").addChannelTypes(ChannelType.GuildText,ChannelType.GuildAnnouncement)))
    .addSubcommand(s=>s.setName("bot-status").setDescription("Post a live bot status panel")
      .addChannelOption(o=>o.setName("channel").setDescription("Status channel").addChannelTypes(ChannelType.GuildText,ChannelType.GuildAnnouncement)))
].map(c=>c.toJSON());

export const v5ContextCommandData=[
  new ContextMenuCommandBuilder().setName("Create support ticket").setType(ApplicationCommandType.Message),
  new ContextMenuCommandBuilder().setName("Add to starboard").setType(ApplicationCommandType.Message).setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
].map(c=>c.toJSON());

export async function recordUsage(guildId:string,userId:string|undefined,eventType:string,featureKey:string,channelId?:string,metadata:any={}){
  await query(`INSERT INTO usage_events(guild_id,user_id,event_type,feature_key,channel_id,metadata) VALUES($1,$2,$3,$4,$5,$6::jsonb)`,
    [guildId,userId||null,eventType,featureKey,channelId||null,JSON.stringify(metadata)]).catch(()=>{});
}

export async function ensureV5Defaults(guildId:string){
  await query(`INSERT INTO onboarding_configs(guild_id) VALUES($1) ON CONFLICT DO NOTHING`,[guildId]);
  await query(`INSERT INTO recap_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING`,[guildId]);
  await query(`INSERT INTO recognition_role_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING`,[guildId]);
  await query(`INSERT INTO counting_configs(guild_id) VALUES($1) ON CONFLICT DO NOTHING`,[guildId]);
  const defaults=[
    ["security_suite",true,{antiAlt:true,minAccountAgeHours:24,antiRaid:true,joinsPerMinute:8,quarantineOnRaid:true,antiNuke:true,actionWindowSeconds:60,maxDestructiveActions:4,trustedRoleIds:[],trustedUserIds:[]}],
    ["birthdays",true,{channelId:"",roleId:"",xpReward:50,coinReward:100}],
    ["server_counters",true,{updateMinutes:10}],
    ["recaps",true,{weekly:true,personalWeekly:true,monthly:true}],
    ["boosters",true,{xpReward:100,coinReward:150}],
    ["onboarding",true,{enabled:true}],
    ["counting",false,{channelId:"",rewardEvery:100}]
  ];
  for(const [key,enabled,cfg] of defaults)await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config) VALUES($1,$2,$3,$4::jsonb) ON CONFLICT DO NOTHING`,
    [guildId,key,enabled,JSON.stringify(cfg)]);
}

async function onboardingConfig(guildId:string){
  return await one<any>(`SELECT * FROM onboarding_configs WHERE guild_id=$1`,[guildId])||{};
}

function onboardingStep(step:number){
  if(step===1){
    const platforms=new StringSelectMenuBuilder().setCustomId("v5:onboard:platform").setPlaceholder("Choose your platform").addOptions(
      new StringSelectMenuOptionBuilder().setLabel("PlayStation").setValue("PlayStation").setEmoji("🎮"),
      new StringSelectMenuOptionBuilder().setLabel("Xbox").setValue("Xbox").setEmoji("🎮"),
      new StringSelectMenuOptionBuilder().setLabel("PC").setValue("PC").setEmoji("🖥️")
    );
    return [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(platforms)];
  }
  if(step===2){
    const interests=new StringSelectMenuBuilder().setCustomId("v5:onboard:interests").setPlaceholder("Choose your interests").setMinValues(1).setMaxValues(4).addOptions(
      new StringSelectMenuOptionBuilder().setLabel("EAFC.Live").setValue("EAFC.Live").setEmoji("⚡"),
      new StringSelectMenuOptionBuilder().setLabel("Ultimate Team").setValue("Ultimate Team").setEmoji("⚽"),
      new StringSelectMenuOptionBuilder().setLabel("SBCs & Objectives").setValue("SBCs & Objectives").setEmoji("🧩"),
      new StringSelectMenuOptionBuilder().setLabel("Gameplay").setValue("Gameplay").setEmoji("🎮"),
      new StringSelectMenuOptionBuilder().setLabel("Community").setValue("Community").setEmoji("💬")
    );
    return [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(interests)];
  }
  if(step===3){
    const notifications=new StringSelectMenuBuilder().setCustomId("v5:onboard:notifications").setPlaceholder("Choose notifications (optional)").setMinValues(0).setMaxValues(4).addOptions(
      new StringSelectMenuOptionBuilder().setLabel("Announcements").setValue("Announcements").setEmoji("📢"),
      new StringSelectMenuOptionBuilder().setLabel("Giveaways").setValue("Giveaways").setEmoji("🎉"),
      new StringSelectMenuOptionBuilder().setLabel("Events").setValue("Events").setEmoji("📅"),
      new StringSelectMenuOptionBuilder().setLabel("Premium").setValue("Premium").setEmoji("💎")
    );
    return [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(notifications)];
  }
  const questions=new ButtonBuilder().setCustomId("v5:onboard:questions").setLabel("Optional questions").setStyle(ButtonStyle.Secondary).setEmoji("📝");
  const finish=new ButtonBuilder().setCustomId("v5:onboard:finish").setLabel("Finish onboarding").setStyle(ButtonStyle.Success).setEmoji("✅");
  return [new ActionRowBuilder<ButtonBuilder>().addComponents(questions,finish)];
}

export async function publishOnboardingPanel(guildId:string,channelId:string){
  const cfg=await onboardingConfig(guildId),channel=await clientChannel(channelId);
  if(!channel?.isTextBased())throw new Error("Onboarding channel is not available.");
  const button=new ActionRowBuilder<ButtonBuilder>().addComponents(new ButtonBuilder().setCustomId("v5:onboard:start").setLabel("Start onboarding").setStyle(ButtonStyle.Primary).setEmoji("👋"));
  const msg=await (channel as TextChannel).send({embeds:[brandEmbed(cfg.welcome_title||"Welcome to EAFC.Live",cfg.welcome_body||"Set up your community profile and unlock the server.",BRAND.colours.primary)],components:[button]});
  await query(`UPDATE onboarding_configs SET channel_id=$2,panel_message_id=$3,updated_at=now() WHERE guild_id=$1`,[guildId,channelId,msg.id]);
  return msg;
}

async function clientChannel(channelId:string){return globalClient?.channels.fetch(channelId).catch(()=>null);}
let globalClient:Client|null=null;

async function finishOnboarding(i:any){
  const cfg=await onboardingConfig(i.guildId);
  const ans=await one<any>(`SELECT * FROM onboarding_answers WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]);
  if(!ans?.platform||!(ans?.interests||[]).length){await i.reply({content:"Choose your platform and at least one interest first.",ephemeral:true});return;}
  const member=await i.guild.members.fetch(i.user.id);
  const roleIds:string[]=[];
  const platformRole=cfg.platform_roles?.[ans.platform];if(platformRole)roleIds.push(String(platformRole));
  for(const interest of ans.interests||[]){const r=cfg.interest_roles?.[interest];if(r)roleIds.push(String(r));}
  for(const n of ans.notification_roles||[]){const r=cfg.notification_roles?.[n];if(r)roleIds.push(String(r));}
  if(cfg.verified_role_id)roleIds.push(String(cfg.verified_role_id));
  for(const roleId of [...new Set(roleIds)])await member.roles.add(roleId,"EAFC.Live onboarding").catch(()=>{});
  if(cfg.quarantine_role_id&&member.roles.cache.has(String(cfg.quarantine_role_id)))await member.roles.remove(String(cfg.quarantine_role_id),"Verification completed").catch(()=>{});
  await query(`UPDATE onboarding_answers SET verified=true,completed_at=now(),updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]);
  await query(`INSERT INTO member_profiles(guild_id,user_id,platform,interests,notification_preferences,metadata) VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb) ON CONFLICT(guild_id,user_id) DO UPDATE SET platform=$3,interests=$4,notification_preferences=$5::jsonb,metadata=member_profiles.metadata||$6::jsonb,updated_at=now()`,[i.guildId,i.user.id,ans.platform,ans.interests||[],JSON.stringify({roles:ans.notification_roles||[]}),JSON.stringify({onboarding_answers:ans.answers||{}})]);
  await query(`INSERT INTO member_stats(guild_id,user_id,verified_at) VALUES($1,$2,now()) ON CONFLICT(guild_id,user_id) DO UPDATE SET verified_at=COALESCE(member_stats.verified_at,now())`,[i.guildId,i.user.id]);
  await query(`INSERT INTO member_funnel(guild_id,user_id,verified_at,roles_selected_at) VALUES($1,$2,now(),now()) ON CONFLICT(guild_id,user_id) DO UPDATE SET verified_at=COALESCE(member_funnel.verified_at,now()),roles_selected_at=COALESCE(member_funnel.roles_selected_at,now())`,[i.guildId,i.user.id]);
  await recordUsage(i.guildId,i.user.id,"complete","onboarding",i.channelId);
  await i.reply({embeds:[brandEmbed("✅ You're all set",`Platform: **${ans.platform}**\nInterests: **${(ans.interests||[]).join(", ")}**\n\nYour roles and profile have been updated.`,BRAND.colours.success)],ephemeral:true});
}

function ticketMenuOptions(types:string[]){
  const source=types.length?types:["General","Support","Question","Other"];
  const emojiFor=(type:string)=>type.toLowerCase().includes("support")?"🛠️":type.toLowerCase().includes("question")?"❓":type.toLowerCase().includes("report")?"🚨":type.toLowerCase().includes("appeal")?"📣":type.toLowerCase().includes("partner")?"🤝":type.toLowerCase().includes("premium")?"⭐":"💬";
  return source.slice(0,25).map(type=>new StringSelectMenuOptionBuilder().setLabel(`${type} Ticket`.replace(/ Ticket Ticket$/," Ticket").slice(0,100)).setValue(type.slice(0,100)).setEmoji(emojiFor(type)));
}

async function createTicketChannel(client:Client,guild:any,user:any,type:string,sourceUrl?:string){
  const feature=await getFeature(guild.id,"tickets",{categoryId:"",staffRoleIds:[],types:["General","Support","Question","Other"]});
  if(!feature.enabled)throw new Error("Tickets are disabled.");
  const row=(await query<any>(`INSERT INTO tickets(guild_id,user_id,ticket_type) VALUES($1,$2,$3) RETURNING id`,[guild.id,user.id,type]))[0];
  const overwrites:any[]=[
    {id:guild.roles.everyone.id,deny:[PermissionFlagsBits.ViewChannel]},
    {id:user.id,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]}
  ];
  for(const roleId of feature.config.staffRoleIds||[])overwrites.push({id:roleId,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]});
  const ch=await guild.channels.create({name:`ticket-${row.id}-${user.username}`.toLowerCase().replace(/[^a-z0-9-]/g,"").slice(0,90),type:ChannelType.GuildText,parent:feature.config.categoryId||undefined,permissionOverwrites:overwrites});
  await query(`UPDATE tickets SET channel_id=$1 WHERE id=$2`,[ch.id,row.id]);
  const body=[`Created by <@${user.id}>.`,sourceUrl?`Source: ${sourceUrl}`:"","Tell us what you need and staff will pick this up."].filter(Boolean).join("\n\n");
  await ch.send({content:`<@${user.id}>`,embeds:[systemEmbed(`🎫 ${type} ticket #${row.id}`,body,BRAND.colours.primary)]});
  return {channel:ch,ticket:row};
}

async function publishTicketPanel(client:Client,guildId:string,channelId:string){
  const feature=await getFeature(guildId,"tickets",{categoryId:"",staffRoleIds:[],types:["General","Support","Question","Other"]});
  const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased())throw new Error("Ticket channel is not available.");
  const menu=new StringSelectMenuBuilder().setCustomId("v5:ticket-menu").setPlaceholder("Choose your options").addOptions(...ticketMenuOptions(feature.config.types||[]));
  return (ch as TextChannel).send({embeds:[systemEmbed("🎫 Ticket Support","If you have a request, click on the menu below.\n\n**Selection options:**\n"+(feature.config.types||["General","Support","Question","Other"]).map((x:string)=>`• ${x} Ticket`).join("\n"),BRAND.colours.primary)],components:[new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)]});
}

function formatDuration(ms:number){
  const total=Math.max(0,Math.floor(ms/1000)),days=Math.floor(total/86400),hours=Math.floor(total%86400/3600),minutes=Math.floor(total%3600/60);
  return [days?`${days}d`:null,hours?`${hours}h`:null,`${minutes}m`].filter(Boolean).join(" ");
}

function botStatusEmbed(client:Client){
  const lastUpdate=Math.floor(Date.now()/1000);
  return systemEmbed(`${BRAND.name} • Bot Status`,`Status: 🟢 Online\nUptime: \`${formatDuration(Date.now()-startedAt)}\`\nPing: \`${Math.round(client.ws.ping)} ms\`\nLast Update: <t:${lastUpdate}:R>\n\n**Status updates automatically every ${config.statusUpdateSeconds} seconds. Check Last Update for freshness.**`,BRAND.colours.success);
}

async function publishBotStatus(client:Client,guildId:string,channelId:string){
  const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased())throw new Error("Status channel is not available.");
  const msg=await (ch as TextChannel).send({embeds:[botStatusEmbed(client)]});
  await query(`INSERT INTO bot_status_panels(guild_id,channel_id,message_id) VALUES($1,$2,$3) ON CONFLICT(guild_id) DO UPDATE SET channel_id=$2,message_id=$3,updated_at=now()`,[guildId,channelId,msg.id]);
  return msg;
}

export async function handleV5Command(i:any){
  if(!i.guildId||!["afk","birthday","kudosboard","verify","system"].includes(i.commandName))return false;
  await recordUsage(i.guildId,i.user.id,"command",i.commandName,i.channelId);

  if(i.commandName==="system"){
    const sub=i.options.getSubcommand(),channel=i.options.getChannel("channel")||i.channel;
    if(!channel?.isTextBased()){await i.reply({content:"Choose a text channel the bot can post in.",ephemeral:true});return true;}
    if(sub==="ticket-panel"){
      const msg=await publishTicketPanel(globalClient||i.client,i.guildId,channel.id);
      await audit(i.guildId,i.user.id,"system.ticket_panel.publish",{channelId:channel.id,messageId:msg.id});
      await i.reply({content:`Ticket panel posted in ${channel}.`,ephemeral:true});return true;
    }
    if(sub==="bot-status"){
      const msg=await publishBotStatus(globalClient||i.client,i.guildId,channel.id);
      await audit(i.guildId,i.user.id,"system.bot_status.publish",{channelId:channel.id,messageId:msg.id});
      await i.reply({content:`Bot status panel posted in ${channel}.`,ephemeral:true});return true;
    }
  }

  if(i.commandName==="afk"){
    const reason=i.options.getString("reason");
    if(!reason){
      const current=await one<any>(`SELECT 1 FROM member_afk WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]);
      if(current){await query(`DELETE FROM member_afk WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]);await i.reply({content:"Welcome back. Your AFK status is cleared.",ephemeral:true});}
      else {await query(`INSERT INTO member_afk(guild_id,user_id,reason) VALUES($1,$2,'AFK') ON CONFLICT(guild_id,user_id) DO UPDATE SET reason='AFK',set_at=now()`,[i.guildId,i.user.id]);await i.reply({content:"You're now marked AFK.",ephemeral:true});}
    }else{
      await query(`INSERT INTO member_afk(guild_id,user_id,reason) VALUES($1,$2,$3) ON CONFLICT(guild_id,user_id) DO UPDATE SET reason=$3,set_at=now()`,[i.guildId,i.user.id,reason]);
      await i.reply({content:`You're now AFK: **${reason}**`,ephemeral:true});
    }
    return true;
  }

  if(i.commandName==="birthday"){
    const sub=i.options.getSubcommand();
    if(sub==="clear"){await query(`UPDATE member_profiles SET birthday_day=NULL,birthday_month=NULL,updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[i.guildId,i.user.id]);await i.reply({content:"Birthday removed.",ephemeral:true});return true;}
    const day=i.options.getInteger("day",true),month=i.options.getInteger("month",true),isPublic=i.options.getBoolean("public")!==false;
    const valid=new Date(2024,month-1,day);if(valid.getMonth()!==month-1||valid.getDate()!==day){await i.reply({content:"That isn't a valid calendar date.",ephemeral:true});return true;}
    await query(`INSERT INTO member_profiles(guild_id,user_id,birthday_day,birthday_month,birthday_public) VALUES($1,$2,$3,$4,$5) ON CONFLICT(guild_id,user_id) DO UPDATE SET birthday_day=$3,birthday_month=$4,birthday_public=$5,updated_at=now()`,[i.guildId,i.user.id,day,month,isPublic]);
    await i.reply({content:`🎂 Birthday saved as **${day}/${month}**.`,ephemeral:true});return true;
  }

  if(i.commandName==="kudosboard"){
    const period=i.options.getString("period")||"week",category=i.options.getString("category")||"all";
    const since=period==="week"?"now()-interval '7 days'":period==="month"?"now()-interval '30 days'":null;
    const params:any[]=[i.guildId];let where="guild_id=$1";if(since)where+=` AND created_at>=${since}`;if(category!=="all"){params.push(category);where+=` AND category=$${params.length}`;}
    const rows=await query<any>(`SELECT receiver_id user_id,count(*)::int value FROM reputation_events WHERE ${where} GROUP BY receiver_id ORDER BY value DESC,receiver_id LIMIT 10`,params);
    const label=period==="all"?"All time":period==="month"?"Last 30 days":"Last 7 days";
    await i.reply({embeds:[brandEmbed(`👏 Kudos leaderboard • ${label}`,rows.map((r,n)=>`**${n+1}.** <@${r.user_id}> • **${r.value}** kudos`).join("\n")||"No kudos yet.",BRAND.colours.premium)]});return true;
  }

  if(i.commandName==="verify"){
    const cfg=await onboardingConfig(i.guildId),ageHours=(Date.now()-i.user.createdTimestamp)/3600000;
    if(ageHours<Number(cfg.min_account_age_hours||0)){await i.reply({content:`Your Discord account must be at least ${cfg.min_account_age_hours} hours old before verification.`,ephemeral:true});return true;}
    await query(`INSERT INTO onboarding_answers(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[i.guildId,i.user.id]);
    await i.reply({embeds:[brandEmbed("👋 Complete onboarding","Choose your platform and interests, then finish onboarding.",BRAND.colours.primary)],components:onboardingStep(1),ephemeral:true});return true;
  }
  return false;
}

export async function handleV5Context(client:Client,i:any){
  if(!i.guildId||!i.isMessageContextMenuCommand())return false;
  if(i.commandName==="Create support ticket"){
    const created=await createTicketChannel(client,i.guild,i.user,"Support",i.targetMessage.url);
    await recordUsage(i.guildId,i.user.id,"context","ticket_from_message",i.channelId);
    await i.reply({content:`Ticket created: ${created.channel}`,ephemeral:true});return true;
  }
  if(i.commandName==="Add to starboard"){
    const feature=await getFeature(i.guildId,"starboard",{channelId:""});
    const dest=feature.config.channelId?await client.channels.fetch(String(feature.config.channelId)).catch(()=>null):null;
    if(!dest?.isTextBased()){await i.reply({content:"No valid starboard channel is configured.",ephemeral:true});return true;}
    const embed=brandEmbed("⭐ Staff pick",i.targetMessage.content?.slice(0,3000)||"*Attachment or embed*",BRAND.colours.premium).setAuthor({name:i.targetMessage.author.username,iconURL:i.targetMessage.author.displayAvatarURL()}).addFields({name:"Source",value:`[Jump to message](${i.targetMessage.url})`});
    const image=[...i.targetMessage.attachments.values()].find((a:any)=>a.contentType?.startsWith("image/"));if(image)embed.setImage(image.url);
    await (dest as TextChannel).send({embeds:[embed]});await i.reply({content:"Added to starboard.",ephemeral:true});return true;
  }
  return false;
}

export async function handleV5Component(client:Client,i:any){
  if(!i.guildId)return false;
  const id=String(i.customId||"");
  if(id==="v5:onboard:start"){
    const cfg=await onboardingConfig(i.guildId),ageHours=(Date.now()-i.user.createdTimestamp)/3600000;
    if(ageHours<Number(cfg.min_account_age_hours||0)){await i.reply({content:`Your Discord account is too new to verify yet. Try again when it is ${cfg.min_account_age_hours} hours old.`,ephemeral:true});return true;}
    await query(`INSERT INTO onboarding_answers(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[i.guildId,i.user.id]);
    await i.reply({embeds:[brandEmbed("Set up your EAFC.Live profile","Choose your platform and interests, then finish onboarding.",BRAND.colours.primary)],components:onboardingStep(1),ephemeral:true});return true;
  }
  if(id==="v5:onboard:platform"&&i.isStringSelectMenu()){
    const platform=String(i.values[0]);await query(`INSERT INTO onboarding_answers(guild_id,user_id,platform) VALUES($1,$2,$3) ON CONFLICT(guild_id,user_id) DO UPDATE SET platform=$3,updated_at=now()`,[i.guildId,i.user.id,platform]);
    await i.reply({content:`Platform saved: **${platform}**`,ephemeral:true});return true;
  }
  if(id==="v5:onboard:interests"&&i.isStringSelectMenu()){
    await query(`INSERT INTO onboarding_answers(guild_id,user_id,interests) VALUES($1,$2,$3) ON CONFLICT(guild_id,user_id) DO UPDATE SET interests=$3,updated_at=now()`,[i.guildId,i.user.id,i.values]);
    await i.update({embeds:[brandEmbed("Step 3 of 4 • Notifications",`Interests: **${i.values.join(", ")}**\nChoose which community notifications you want, or select none.`,BRAND.colours.primary)],components:onboardingStep(3)});return true;
  }
  if(id==="v5:onboard:notifications"&&i.isStringSelectMenu()){
    await query(`INSERT INTO onboarding_answers(guild_id,user_id,notification_roles) VALUES($1,$2,$3) ON CONFLICT(guild_id,user_id) DO UPDATE SET notification_roles=$3,updated_at=now()`,[i.guildId,i.user.id,i.values||[]]);
    await i.update({embeds:[brandEmbed("Step 4 of 4 • Finish",`Notifications: **${(i.values||[]).length?(i.values||[]).join(", "):"None"}**\nYou can answer the optional join questions, or finish now.`,BRAND.colours.success)],components:onboardingStep(4)});return true;
  }
  if(id==="v5:onboard:questions"&&i.isButton()){
    const cfg=await onboardingConfig(i.guildId),questions=(cfg.questions||[]).slice(0,5);
    if(!questions.length){await i.reply({content:"There are no optional questions configured.",ephemeral:true});return true;}
    const modal=new ModalBuilder().setCustomId("v5:onboard:questions-modal").setTitle("A little about you");
    for(let n=0;n<questions.length;n++){const q=questions[n],input=new TextInputBuilder().setCustomId(String(q.key||`q${n+1}`)).setLabel(String(q.label||q.question||`Question ${n+1}`).slice(0,45)).setStyle(TextInputStyle.Short).setRequired(false).setMaxLength(200);modal.addComponents(new ActionRowBuilder<TextInputBuilder>().addComponents(input));}
    await i.showModal(modal);return true;
  }
  if(id==="v5:onboard:questions-modal"&&i.isModalSubmit()){
    const cfg=await onboardingConfig(i.guildId),questions=(cfg.questions||[]).slice(0,5),answers:any={};
    for(let n=0;n<questions.length;n++){const key=String(questions[n].key||`q${n+1}`);answers[key]=i.fields.getTextInputValue(key)||"";}
    await query(`INSERT INTO onboarding_answers(guild_id,user_id,answers) VALUES($1,$2,$3::jsonb) ON CONFLICT(guild_id,user_id) DO UPDATE SET answers=$3::jsonb,updated_at=now()`,[i.guildId,i.user.id,JSON.stringify(answers)]);
    await i.reply({content:"Optional answers saved. Return to the onboarding message and press **Finish onboarding**.",ephemeral:true});return true;
  }
  if(id==="v5:onboard:finish"){await finishOnboarding(i);return true;}

  if(id==="v5:ticket-menu"&&i.isStringSelectMenu()){
    const type=String(i.values?.[0]||"General");
    try{const created=await createTicketChannel(client,i.guild,i.user,type);await recordUsage(i.guildId,i.user.id,"component","ticket_panel",i.channelId,{type});await i.reply({content:`Ticket created: ${created.channel}`,ephemeral:true});}
    catch(err:any){await i.reply({content:String(err?.message||err),ephemeral:true});}
    return true;
  }

  if(id==="v5:daily"){
    try{const r=await claimDaily(i.guildId,i.user.id);await i.reply({embeds:[brandEmbed("🔥 Daily reward claimed",`**+${fmt(r.coins)} Live Coins**\n${r.streak}-day streak${r.bonus?` • +${fmt(r.bonus)} streak bonus`:""}`,BRAND.colours.coins)],ephemeral:true});}
    catch(err:any){await i.reply({content:String(err?.message||err),ephemeral:true});}return true;
  }

  if(id.startsWith("v5:drop:")){
    const dropId=Number(id.split(":")[2]),drop=await one<any>(`SELECT * FROM flash_drops WHERE id=$1 AND guild_id=$2 AND status='LIVE' AND starts_at<=now() AND ends_at>now()`,[dropId,i.guildId]);
    if(!drop){await i.reply({content:"That drop has ended.",ephemeral:true});return true;}
    const count=await one<any>(`SELECT count(*) c FROM flash_drop_claims WHERE drop_id=$1`,[dropId]);
    if(drop.max_claims!==null&&Number(count?.c||0)>=Number(drop.max_claims)){await i.reply({content:"That drop is fully claimed.",ephemeral:true});return true;}
    const inserted=await query<any>(`INSERT INTO flash_drop_claims(drop_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING RETURNING user_id`,[dropId,i.user.id]);
    if(!inserted.length){await i.reply({content:"You've already claimed this drop.",ephemeral:true});return true;}
    if(Number(drop.reward_coins)>0)await awardCurrency({guildId:i.guildId,userId:i.user.id,currency:"coins",amount:Number(drop.reward_coins),reason:`Flash drop: ${drop.name}`,sourceType:"flash_drop",sourceId:String(drop.id),idempotencyKey:`flash:${drop.id}:${i.user.id}:coins`});
    if(Number(drop.reward_xp)>0)await awardCurrency({guildId:i.guildId,userId:i.user.id,currency:"xp",amount:Number(drop.reward_xp),reason:`Flash drop: ${drop.name}`,sourceType:"flash_drop",sourceId:String(drop.id),idempotencyKey:`flash:${drop.id}:${i.user.id}:xp`});
    await i.reply({content:`⚡ Claimed **${fmt(drop.reward_coins)} Live Coins**${Number(drop.reward_xp)?` and **${fmt(drop.reward_xp)} XP**`:""}.`,ephemeral:true});return true;
  }

  if(id.startsWith("v5:role:")){
    const roleId=id.slice("v5:role:".length),member=await i.guild.members.fetch(i.user.id),role=i.guild.roles.cache.get(roleId);
    if(!role){await i.reply({content:"That role no longer exists.",ephemeral:true});return true;}
    if(member.roles.cache.has(roleId)){await member.roles.remove(roleId);await i.reply({content:`Removed @${role.name}.`,ephemeral:true});}
    else {await member.roles.add(roleId);await i.reply({content:`Added @${role.name}.`,ephemeral:true});}
    return true;
  }
  if(id.startsWith("v5:panel:")&&i.isStringSelectMenu()){
    const panelId=Number(id.split(":")[2]),panel=await one<any>(`SELECT * FROM role_panels WHERE id=$1 AND guild_id=$2 AND enabled=true`,[panelId,i.guildId]);
    if(!panel){await i.reply({content:"That role panel is no longer active.",ephemeral:true});return true;}
    const allowed=new Set<string>((panel.roles||[]).map((x:any)=>String(x.roleId))),selected=new Set<string>((i.values||[]).filter((x:string)=>allowed.has(x))),member=await i.guild.members.fetch(i.user.id);
    for(const roleId of allowed){if(selected.has(roleId)&&!member.roles.cache.has(roleId))await member.roles.add(roleId,"Role panel selection").catch(()=>{});if(!selected.has(roleId)&&member.roles.cache.has(roleId))await member.roles.remove(roleId,"Role panel selection").catch(()=>{});}
    await i.reply({content:"Your roles have been updated.",ephemeral:true});return true;
  }
  if(id.startsWith("v5:template-select:")&&i.isStringSelectMenu()){
    const templateId=Number(id.split(":")[2]),t=await one<any>(`SELECT select_config FROM message_templates WHERE id=$1 AND guild_id=$2`,[templateId,i.guildId]);
    const opt=(t?.select_config?.options||[]).find((x:any)=>String(x.value)===String(i.values?.[0]));
    if(!opt){await i.reply({content:"That option is no longer available.",ephemeral:true});return true;}
    if(opt.roleId){const member=await i.guild.members.fetch(i.user.id),role=i.guild.roles.cache.get(String(opt.roleId));if(role){if(member.roles.cache.has(role.id))await member.roles.remove(role.id).catch(()=>{});else await member.roles.add(role.id).catch(()=>{});}}
    await i.reply({content:String(opt.response||"Done."),ephemeral:true});return true;
  }
  if(id.startsWith("v5:noop:")){await i.reply({content:"This button has no action configured yet.",ephemeral:true});return true;}
  return false;
}

export async function onV5Message(message:any){
  if(!message.guildId||message.author?.bot)return;
  const gid=message.guildId,uid=message.author.id;
  const afk=await one<any>(`DELETE FROM member_afk WHERE guild_id=$1 AND user_id=$2 RETURNING set_at`,[gid,uid]);
  if(afk)await message.reply({content:"Welcome back. I've cleared your AFK status.",allowedMentions:{repliedUser:false}}).catch(()=>{});
  const mentions=[...message.mentions.users.keys()].filter((x:string)=>x!==uid).slice(0,5);
  if(mentions.length){
    const rows=await query<any>(`SELECT user_id,reason,set_at FROM member_afk WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,mentions]);
    if(rows.length)await message.reply({content:rows.map((r:any)=>`<@${r.user_id}> is AFK: **${r.reason||"AFK"}** (<t:${Math.floor(new Date(r.set_at).getTime()/1000)}:R>)`).join("\n"),allowedMentions:{users:[]}}).catch(()=>{});
  }

  const counting=await one<any>(`SELECT * FROM counting_configs WHERE guild_id=$1 AND enabled=true AND channel_id=$2`,[gid,message.channelId]);
  if(counting){
    const n=Number(String(message.content).trim());
    if(!Number.isInteger(n)||n!==Number(counting.next_number)||counting.last_user_id===uid){
      await message.react("❌").catch(()=>{});await message.delete().catch(()=>{});
      return;
    }
    await message.react("✅").catch(()=>{});
    await query(`UPDATE counting_configs SET next_number=next_number+1,last_user_id=$2,last_message_id=$3,updated_at=now() WHERE guild_id=$1`,[gid,uid,message.id]);
    if(Number(counting.reward_every)>0&&n%Number(counting.reward_every)===0){
      await awardCurrency({guildId:gid,userId:uid,currency:"coins",amount:25,reason:`Counting milestone ${n}`,sourceType:"counting",sourceId:String(n),idempotencyKey:`count:${gid}:${n}:coins`});
      await message.channel.send(`🎉 <@${uid}> hit **${n.toLocaleString()}** and earned **25 Live Coins**.`).catch(()=>{});
    }
    await recordUsage(gid,uid,"success","counting",message.channelId,{number:n});
  }

  await query(`INSERT INTO member_funnel(guild_id,user_id,first_active_at) VALUES($1,$2,now()) ON CONFLICT(guild_id,user_id) DO UPDATE SET first_active_at=COALESCE(member_funnel.first_active_at,now())`,[gid,uid]);
  await query(`UPDATE member_stats SET first_active_at=COALESCE(first_active_at,now()) WHERE guild_id=$1 AND user_id=$2`,[gid,uid]).catch(()=>{});
}

export async function refreshInviteSnapshot(guild:any){
  const invites=await guild.invites.fetch().catch(()=>null);if(!invites)return;
  for(const inv of invites.values())await query(`INSERT INTO invite_snapshots(guild_id,code,inviter_id,uses) VALUES($1,$2,$3,$4) ON CONFLICT(guild_id,code) DO UPDATE SET inviter_id=$3,uses=$4,updated_at=now()`,[guild.id,inv.code,inv.inviter?.id||null,inv.uses||0]);
}

export type InviteAttribution = { code:string; inviterId:string|null; inviterMention:string; totalInvites:number };

async function detectInvite(guild:any,userId:string):Promise<InviteAttribution|null>{
  const current=await guild.invites.fetch().catch(()=>null);if(!current)return null;
  const old=await query<any>(`SELECT * FROM invite_snapshots WHERE guild_id=$1`,[guild.id]);
  const map=new Map(old.map((x:any)=>[x.code,x]));
  let used:any=null;
  for(const inv of current.values()){const prev:any=map.get(inv.code);if((inv.uses||0)>Number(prev?.uses||0)){used=inv;break;}}
  await refreshInviteSnapshot(guild);
  if(used){
    await query(`INSERT INTO invite_joins(guild_id,user_id,inviter_id,invite_code) VALUES($1,$2,$3,$4) ON CONFLICT(guild_id,user_id) DO UPDATE SET inviter_id=$3,invite_code=$4`,[guild.id,userId,used.inviter?.id||null,used.code]);
    await query(`UPDATE member_funnel SET inviter_id=$3,invite_code=$4 WHERE guild_id=$1 AND user_id=$2`,[guild.id,userId,used.inviter?.id||null,used.code]);
    const total=used.inviter?.id?await one<any>(`SELECT count(*)::int total FROM invite_joins WHERE guild_id=$1 AND inviter_id=$2`,[guild.id,used.inviter.id]):null;
    return {code:used.code,inviterId:used.inviter?.id||null,inviterMention:used.inviter?.id?`<@${used.inviter.id}>`:"Unknown",totalInvites:Number(total?.total||0)};
  }
  return null;
}

export async function onV5MemberAdd(member:GuildMember){
  const gid=member.guild.id,uid=member.id;await ensureV5Defaults(gid);
  await query(`INSERT INTO member_funnel(guild_id,user_id,joined_at) VALUES($1,$2,now()) ON CONFLICT(guild_id,user_id) DO UPDATE SET joined_at=COALESCE(member_funnel.joined_at,now()),left_at=NULL`,[gid,uid]);
  const invite=await detectInvite(member.guild,uid).catch(()=>null);
  const feature=await getFeature(gid,"security_suite",{antiAlt:true,minAccountAgeHours:24,antiRaid:true,joinsPerMinute:8,quarantineOnRaid:true});
  if(!feature.enabled)return invite;
  const cfg=feature.config||{},ageHours=(Date.now()-member.user.createdTimestamp)/3600000;
  const onboarding=await onboardingConfig(gid);
  const now=Date.now(),window=(joinWindows.get(gid)||[]).filter(t=>now-t<60000);window.push(now);joinWindows.set(gid,window);
  const raid=cfg.antiRaid!==false&&window.length>=Number(cfg.joinsPerMinute||8);
  const young=cfg.antiAlt!==false&&ageHours<Number(cfg.minAccountAgeHours||24);
  if((young||raid)&&onboarding.quarantine_role_id)await member.roles.add(String(onboarding.quarantine_role_id),young?"New account quarantine":"Raid protection").catch(()=>{});
  if(young)await query(`INSERT INTO security_events(guild_id,event_type,target_id,severity,details,action_taken) VALUES($1,'young_account',$2,'warning',$3::jsonb,$4)`,[gid,uid,JSON.stringify({ageHours:Math.round(ageHours)}),onboarding.quarantine_role_id?"quarantine_role":"logged"]);
  if(raid)await query(`INSERT INTO security_events(guild_id,event_type,target_id,severity,details,action_taken) VALUES($1,'join_spike',$2,'critical',$3::jsonb,$4)`,[gid,uid,JSON.stringify({joinsLastMinute:window.length}),onboarding.quarantine_role_id?"quarantine_role":"logged"]);
  return invite;
}

export async function onV5MemberRemove(member:any){
  await query(`UPDATE member_funnel SET left_at=now() WHERE guild_id=$1 AND user_id=$2`,[member.guild.id,member.id]);
}

export async function onV5MemberUpdate(oldMember:any,newMember:any){
  if(!oldMember.premiumSinceTimestamp&&newMember.premiumSinceTimestamp){
    const feature=await getFeature(newMember.guild.id,"boosters",{xpReward:100,coinReward:150});
    if(feature.enabled){
      const key=`boost-start:${newMember.id}:${newMember.premiumSinceTimestamp}`;
      if(Number(feature.config.xpReward||0)>0)await awardCurrency({guildId:newMember.guild.id,userId:newMember.id,currency:"xp",amount:Number(feature.config.xpReward),reason:"Server booster reward",sourceType:"boost",sourceId:String(newMember.premiumSinceTimestamp),idempotencyKey:key+":xp"});
      if(Number(feature.config.coinReward||0)>0)await awardCurrency({guildId:newMember.guild.id,userId:newMember.id,currency:"coins",amount:Number(feature.config.coinReward),reason:"Server booster reward",sourceType:"boost",sourceId:String(newMember.premiumSinceTimestamp),idempotencyKey:key+":coins"});
    }
  }
}

export async function onV5Reaction(reaction:any,user:any,added:boolean){
  if(user.bot)return;
  if(reaction.partial)await reaction.fetch().catch(()=>null);
  const msg=reaction.message;if(!msg.guildId)return;
  const emoji=reaction.emoji.id||reaction.emoji.name||"";
  const map=await one<any>(`SELECT * FROM reaction_roles WHERE guild_id=$1 AND message_id=$2 AND emoji=$3 AND enabled=true`,[msg.guildId,msg.id,emoji]);
  if(!map)return;
  const member=await msg.guild?.members.fetch(user.id).catch(()=>null);if(!member)return;
  if(added)await member.roles.add(map.role_id,"Reaction role").catch(()=>{});else await member.roles.remove(map.role_id,"Reaction role removed").catch(()=>{});
}

function destructiveAction(action:any){
  return [AuditLogEvent.ChannelDelete,AuditLogEvent.RoleDelete,AuditLogEvent.MemberBanAdd,AuditLogEvent.WebhookCreate,AuditLogEvent.WebhookDelete].includes(action);
}

export async function onV5AuditEntry(entry:any,guild:any){
  if(!destructiveAction(entry.action)||!entry.executorId)return;
  const feature=await getFeature(guild.id,"security_suite",{antiNuke:true,actionWindowSeconds:60,maxDestructiveActions:4,trustedRoleIds:[],trustedUserIds:[]});
  if(!feature.enabled||feature.config.antiNuke===false)return;
  const actor=await guild.members.fetch(entry.executorId).catch(()=>null);if(!actor||actor.id===guild.ownerId||actor.user.bot)return;
  if(((feature.config.trustedUserIds||[]) as string[]).includes(actor.id)||actor.roles.cache.some((r:any)=>((feature.config.trustedRoleIds||[]) as string[]).includes(r.id)))return;
  const rawAction=String(entry.action),actionType="destructive",seconds=Math.max(10,Number(feature.config.actionWindowSeconds||60)),limit=Math.max(1,Number(feature.config.maxDestructiveActions||4));
  const state=await one<any>(`SELECT * FROM staff_action_windows WHERE guild_id=$1 AND actor_id=$2 AND action_type=$3`,[guild.id,actor.id,actionType]);
  const fresh=!state||Date.now()-new Date(state.window_started_at).getTime()>seconds*1000,count=fresh?1:Number(state.action_count||0)+1;
  await query(`INSERT INTO staff_action_windows(guild_id,actor_id,action_type,window_started_at,action_count) VALUES($1,$2,$3,now(),$4) ON CONFLICT(guild_id,actor_id,action_type) DO UPDATE SET window_started_at=CASE WHEN now()-staff_action_windows.window_started_at>($5||' seconds')::interval THEN now() ELSE staff_action_windows.window_started_at END,action_count=CASE WHEN now()-staff_action_windows.window_started_at>($5||' seconds')::interval THEN 1 ELSE staff_action_windows.action_count+1 END`,[guild.id,actor.id,actionType,count,String(seconds)]);
  let actionTaken="logged";
  if(count>limit){
    const removable=actor.roles.cache.filter((r:any)=>r.id!==guild.id&&!r.managed&&r.position<(guild.members.me?.roles.highest.position||0)&&r.permissions.any([PermissionFlagsBits.Administrator,PermissionFlagsBits.ManageGuild,PermissionFlagsBits.ManageChannels,PermissionFlagsBits.ManageRoles,PermissionFlagsBits.BanMembers]));
    for(const role of removable.values())await actor.roles.remove(role.id,"EAFC.Live anti-nuke action limit").catch(()=>{});
    actionTaken=removable.size?"removed_dangerous_roles":"limit_exceeded";
  }
  await query(`INSERT INTO security_events(guild_id,event_type,actor_id,target_id,severity,details,action_taken) VALUES($1,'destructive_action',$2,$3,$4,$5::jsonb,$6)`,[guild.id,actor.id,entry.targetId||null,count>limit?"critical":"warning",JSON.stringify({action:rawAction,count,limit}),actionTaken]);
}

async function awardKudosMilestones(client:Client,guildId:string){
  const rows=await query<any>(`SELECT m.*,s.thanks_received FROM kudos_milestones m JOIN member_stats s ON s.guild_id=m.guild_id AND s.thanks_received>=m.milestone WHERE m.guild_id=$1 AND m.enabled=true ORDER BY m.milestone`,[guildId]);
  const guild=client.guilds.cache.get(guildId);
  for(const r of rows){
    const inserted=await query<any>(`INSERT INTO kudos_awards(guild_id,user_id,milestone_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING milestone_id`,[guildId,r.user_id,r.id]);if(!inserted.length)continue;
    if(Number(r.xp_reward)>0)await awardCurrency({guildId,userId:r.user_id,currency:"xp",amount:Number(r.xp_reward),reason:`Kudos milestone: ${r.milestone}`,sourceType:"kudos_milestone",sourceId:String(r.id),idempotencyKey:`kudos-milestone:${r.id}:${r.user_id}:xp`});
    if(Number(r.coin_reward)>0)await awardCurrency({guildId,userId:r.user_id,currency:"coins",amount:Number(r.coin_reward),reason:`Kudos milestone: ${r.milestone}`,sourceType:"kudos_milestone",sourceId:String(r.id),idempotencyKey:`kudos-milestone:${r.id}:${r.user_id}:coins`});
    if(r.badge_key)await query(`INSERT INTO achievements(guild_id,user_id,achievement_key) VALUES($1,$2,$3) ON CONFLICT DO NOTHING`,[guildId,r.user_id,r.badge_key]);
    const member=guild?await guild.members.fetch(r.user_id).catch(()=>null):null;if(member&&r.role_id)await member.roles.add(r.role_id,`${r.milestone} kudos milestone`).catch(()=>{});
  }
}

async function processLevelWorkflows(client:Client,guildId:string){
  const rows=await query<any>(`SELECT w.*,e.user_id,e.xp_total FROM level_workflows w JOIN member_economy e ON e.guild_id=w.guild_id WHERE w.guild_id=$1 AND w.enabled=true ORDER BY w.level`,[guildId]);
  const guild=client.guilds.cache.get(guildId);if(!guild)return;
  for(const r of rows){
    if(levelFromXp(Number(r.xp_total||0))<Number(r.level))continue;
    const key=`level-workflow:${r.id}:${r.user_id}`,ins=await query<any>(`INSERT INTO level_workflow_awards(guild_id,user_id,workflow_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING workflow_id`,[guildId,r.user_id,r.id]);
    if(!ins.length)continue;
    if(Number(r.coin_reward)>0)await awardCurrency({guildId,userId:r.user_id,currency:"coins",amount:Number(r.coin_reward),reason:`Level ${r.level} reward`,sourceType:"level_workflow",sourceId:String(r.id),idempotencyKey:key+":coins"});
    const member=await guild.members.fetch(r.user_id).catch(()=>null);if(member&&r.role_id)await member.roles.add(r.role_id,`Reached level ${r.level}`).catch(()=>{});
    if(r.message){if(r.announce_channel_id){const ch=await client.channels.fetch(r.announce_channel_id).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send(String(r.message).replaceAll("{user}",`<@${r.user_id}>`).replaceAll("{level}",String(r.level))).catch(()=>{});}else if(member)await member.send(String(r.message).replaceAll("{level}",String(r.level))).catch(()=>{});}
  }
}

async function processBirthdays(client:Client,guildId:string){
  const now=new Date(),day=now.getUTCDate(),month=now.getUTCMonth()+1,year=now.getUTCFullYear();
  const feature=await getFeature(guildId,"birthdays",{channelId:"",roleId:"",xpReward:50,coinReward:100});if(!feature.enabled)return;
  const rows=await query<any>(`SELECT * FROM member_profiles WHERE guild_id=$1 AND birthday_day=$2 AND birthday_month=$3`,[guildId,day,month]);
  const guild=client.guilds.cache.get(guildId);
  for(const p of rows){
    const inserted=await query<any>(`INSERT INTO birthday_awards(guild_id,user_id,award_year) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING award_year`,[guildId,p.user_id,year]);if(!inserted.length)continue;
    if(Number(feature.config.xpReward||0)>0)await awardCurrency({guildId,userId:p.user_id,currency:"xp",amount:Number(feature.config.xpReward),reason:"Birthday reward",sourceType:"birthday",sourceId:String(year),idempotencyKey:`birthday:${year}:${p.user_id}:xp`});
    if(Number(feature.config.coinReward||0)>0)await awardCurrency({guildId,userId:p.user_id,currency:"coins",amount:Number(feature.config.coinReward),reason:"Birthday reward",sourceType:"birthday",sourceId:String(year),idempotencyKey:`birthday:${year}:${p.user_id}:coins`});
    const member=guild?await guild.members.fetch(p.user_id).catch(()=>null):null;if(member&&feature.config.roleId)await member.roles.add(String(feature.config.roleId),"Birthday role").catch(()=>{});
    if(p.birthday_public!==false&&feature.config.channelId){const ch=await client.channels.fetch(String(feature.config.channelId)).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send(`🎂 Happy birthday <@${p.user_id}>! Have a brilliant day. 🎉`).catch(()=>{});}
  }
  if(guild&&feature.config.roleId){for(const m of guild.members.cache.values())if(m.roles.cache.has(String(feature.config.roleId))&&!rows.some((p:any)=>p.user_id===m.id))await m.roles.remove(String(feature.config.roleId),"Birthday ended").catch(()=>{});}
}

async function processRetention(guildId:string){
  await query(`UPDATE member_funnel f SET retained_1d=true WHERE guild_id=$1 AND joined_at<=now()-interval '1 day' AND EXISTS(SELECT 1 FROM member_stats s WHERE s.guild_id=f.guild_id AND s.user_id=f.user_id AND s.last_message_at>=f.joined_at+interval '1 day')`,[guildId]);
  await query(`UPDATE member_funnel f SET retained_7d=true WHERE guild_id=$1 AND joined_at<=now()-interval '7 days' AND EXISTS(SELECT 1 FROM member_stats s WHERE s.guild_id=f.guild_id AND s.user_id=f.user_id AND s.last_message_at>=f.joined_at+interval '7 days')`,[guildId]);
  await query(`UPDATE member_funnel f SET retained_30d=true WHERE guild_id=$1 AND joined_at<=now()-interval '30 days' AND EXISTS(SELECT 1 FROM member_stats s WHERE s.guild_id=f.guild_id AND s.user_id=f.user_id AND s.last_message_at>=f.joined_at+interval '30 days')`,[guildId]);
  await query(`UPDATE invite_joins i SET retained_7d=true WHERE guild_id=$1 AND joined_at<=now()-interval '7 days' AND EXISTS(SELECT 1 FROM member_funnel f WHERE f.guild_id=i.guild_id AND f.user_id=i.user_id AND f.left_at IS NULL)`,[guildId]);
}

async function processInviteMilestones(client:Client,guildId:string){
  const rows=await query<any>(`SELECT m.*,x.inviter_id,x.total FROM invite_milestones m JOIN (SELECT inviter_id,count(*)::int total FROM invite_joins WHERE guild_id=$1 AND retained_7d=true AND inviter_id IS NOT NULL GROUP BY inviter_id) x ON x.total>=m.retained_invites WHERE m.guild_id=$1 AND m.enabled=true`,[guildId]);
  const guild=client.guilds.cache.get(guildId),feature=await getFeature(guildId,"growth",{inviteUnlockChannelId:""});
  for(const r of rows){const ins=await query<any>(`INSERT INTO invite_milestone_awards(guild_id,user_id,milestone_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING milestone_id`,[guildId,r.inviter_id,r.id]);if(!ins.length)continue;
    if(Number(r.xp_reward)>0)await awardCurrency({guildId,userId:r.inviter_id,currency:"xp",amount:Number(r.xp_reward),reason:`Invite milestone: ${r.retained_invites}`,sourceType:"invite_milestone",sourceId:String(r.id),idempotencyKey:`invite:${r.id}:${r.inviter_id}:xp`});
    if(Number(r.coin_reward)>0)await awardCurrency({guildId,userId:r.inviter_id,currency:"coins",amount:Number(r.coin_reward),reason:`Invite milestone: ${r.retained_invites}`,sourceType:"invite_milestone",sourceId:String(r.id),idempotencyKey:`invite:${r.id}:${r.inviter_id}:coins`});
    const member=guild?await guild.members.fetch(r.inviter_id).catch(()=>null):null;if(member&&r.role_id)await member.roles.add(r.role_id,"Invite milestone").catch(()=>{});
    if(Number(r.premium_days||0)>0){const plans=await listPlans(guildId,true),plan=plans[0];if(plan)await grantComp(guildId,r.inviter_id,plan.id,Number(r.premium_days),"invite-milestone").catch(()=>{});}
    if(feature.config.inviteUnlockChannelId){
      const ch=await client.channels.fetch(String(feature.config.inviteUnlockChannelId)).catch(()=>null);
      const rewards=[Number(r.premium_days||0)>0?`**${r.premium_days} Days Premium**`:null,Number(r.coin_reward)>0?`**${fmt(Number(r.coin_reward))} Live Coins**`:null,Number(r.xp_reward)>0?`**${fmt(Number(r.xp_reward))} XP**`:null].filter(Boolean).join(" + ")||"a reward";
      if(ch?.isTextBased())await (ch as TextChannel).send({embeds:[systemEmbed("🎉 Invite Milestone",`<@${r.inviter_id}> has unlocked ${rewards} with **${r.retained_invites} retained invites**!`,BRAND.colours.primary)]}).catch(()=>{});
    }
  }
}

async function processBoosterMilestones(client:Client,guildId:string){
  const guild=client.guilds.cache.get(guildId);if(!guild)return;
  const defs=await query<any>(`SELECT * FROM booster_milestones WHERE guild_id=$1 AND enabled=true ORDER BY months`,[guildId]);
  for(const member of guild.members.cache.values()){if(!member.premiumSinceTimestamp)continue;const months=Math.floor((Date.now()-member.premiumSinceTimestamp)/(30.4375*86400000));
    for(const d of defs){if(months<Number(d.months))continue;const ins=await query<any>(`INSERT INTO booster_awards(guild_id,user_id,milestone_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING milestone_id`,[guildId,member.id,d.id]);if(!ins.length)continue;
      if(Number(d.xp_reward)>0)await awardCurrency({guildId,userId:member.id,currency:"xp",amount:Number(d.xp_reward),reason:`${d.months}-month booster milestone`,sourceType:"booster_milestone",sourceId:String(d.id),idempotencyKey:`boost:${d.id}:${member.id}:xp`});
      if(Number(d.coin_reward)>0)await awardCurrency({guildId,userId:member.id,currency:"coins",amount:Number(d.coin_reward),reason:`${d.months}-month booster milestone`,sourceType:"booster_milestone",sourceId:String(d.id),idempotencyKey:`boost:${d.id}:${member.id}:coins`});
      if(d.role_id)await member.roles.add(d.role_id,`${d.months}-month booster milestone`).catch(()=>{});
    }
  }
}

async function processRecognitionRoles(client:Client,guildId:string){
  const settings=await one<any>(`SELECT * FROM recognition_role_settings WHERE guild_id=$1`,[guildId]);if(!settings)return;
  const guild=client.guilds.cache.get(guildId);if(!guild)return;
  if(settings.weekly_role_id){
    const top=await one<any>(`SELECT receiver_id,count(*) c FROM reputation_events WHERE guild_id=$1 AND created_at>=date_trunc('week',now()) GROUP BY receiver_id ORDER BY c DESC,receiver_id LIMIT 1`,[guildId]);
    if(top?.receiver_id&&top.receiver_id!==settings.current_weekly_user_id){
      if(settings.current_weekly_user_id){const old=await guild.members.fetch(settings.current_weekly_user_id).catch(()=>null);if(old)await old.roles.remove(settings.weekly_role_id,"Weekly recognition rotated").catch(()=>{});}
      const next=await guild.members.fetch(top.receiver_id).catch(()=>null);if(next)await next.roles.add(settings.weekly_role_id,"Weekly recognition winner").catch(()=>{});
      await query(`UPDATE recognition_role_settings SET current_weekly_user_id=$2,updated_at=now() WHERE guild_id=$1`,[guildId,top.receiver_id]);
    }
  }
  if(settings.season_role_id){
    const top=await one<any>(`SELECT m.user_id FROM season_member_stats m JOIN economy_seasons s ON s.id=m.season_id WHERE s.guild_id=$1 AND s.active=true ORDER BY m.xp_earned DESC LIMIT 1`,[guildId]);
    if(top?.user_id&&top.user_id!==settings.current_season_user_id){
      if(settings.current_season_user_id){const old=await guild.members.fetch(settings.current_season_user_id).catch(()=>null);if(old)await old.roles.remove(settings.season_role_id,"Season champion changed").catch(()=>{});}
      const next=await guild.members.fetch(top.user_id).catch(()=>null);if(next)await next.roles.add(settings.season_role_id,"Current season champion").catch(()=>{});
      await query(`UPDATE recognition_role_settings SET current_season_user_id=$2,updated_at=now() WHERE guild_id=$1`,[guildId,top.user_id]);
    }
  }
}

async function processCounters(client:Client,guildId:string){
  const guild=client.guilds.cache.get(guildId);if(!guild)return;
  const counters=await query<any>(`SELECT * FROM server_counters WHERE guild_id=$1 AND enabled=true`,[guildId]);if(!counters.length)return;
  const premium=Number((await one<any>(`SELECT count(DISTINCT discord_user_id) c FROM entitlements WHERE guild_id=$1 AND active=true AND (expires_at IS NULL OR expires_at>now())`,[guildId]))?.c||0);
  const verified=Number((await one<any>(`SELECT count(*) c FROM onboarding_answers WHERE guild_id=$1 AND verified=true`,[guildId]))?.c||0);
  const values:any={members:guild.memberCount,online:guild.members.cache.filter((m:any)=>m.presence?.status&&m.presence.status!=="offline").size,premium,boosters:guild.premiumSubscriptionCount||0,verified};
  for(const c of counters){const ch=guild.channels.cache.get(c.channel_id);if(!ch)continue;const name=String(c.label).replace("{count}",fmt(Number(values[c.metric]||0))).slice(0,100);if(ch.name!==name)await ch.setName(name,"EAFC.Live server counter").catch(()=>{});}
}

function weekKey(d=new Date()){const x=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate()));const day=x.getUTCDay()||7;x.setUTCDate(x.getUTCDate()+4-day);const y=new Date(Date.UTC(x.getUTCFullYear(),0,1));return `${x.getUTCFullYear()}-W${String(Math.ceil((((x.getTime()-y.getTime())/86400000)+1)/7)).padStart(2,"0")}`;}
function monthKey(d=new Date()){return d.toISOString().slice(0,7);}

async function processRecaps(client:Client,guildId:string){
  const s=await one<any>(`SELECT * FROM recap_settings WHERE guild_id=$1`,[guildId]);if(!s)return;
  const now=new Date(),wk=weekKey(now),mk=monthKey(now);
  if(s.weekly_enabled&&s.last_weekly_key!==wk&&now.getUTCDay()===Number(s.weekly_day??0)&&now.getUTCHours()>=Number(s.weekly_hour||19)){
    const m=await one<any>(`SELECT
      (SELECT count(*) FROM member_stats WHERE guild_id=$1 AND last_message_at>=now()-interval '7 days') active,
      (SELECT count(*) FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '7 days') kudos,
      (SELECT count(*) FROM member_quest_progress WHERE guild_id=$1 AND rewarded_at>=now()-interval '7 days') quests,
      (SELECT count(*) FROM member_funnel WHERE guild_id=$1 AND joined_at>=now()-interval '7 days') joins,
      (SELECT count(*) FROM billing_subscriptions WHERE guild_id=$1 AND created_at>=now()-interval '7 days' AND status IN ('active','trialing')) premium`,[guildId]);
    const top=await one<any>(`SELECT receiver_id,count(*) c FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '7 days' GROUP BY receiver_id ORDER BY c DESC LIMIT 1`,[guildId]);
    if(s.weekly_channel_id){const ch=await client.channels.fetch(s.weekly_channel_id).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send({embeds:[brandEmbed("📊 This week on EAFC.Live",`**${m?.active||0}** active members\n**${m?.joins||0}** new members\n**${m?.kudos||0}** kudos given\n**${m?.quests||0}** quests completed\n**${m?.premium||0}** Premium joins${top?`\n\n👏 Most recognised: <@${top.receiver_id}> (${top.c})`:""}`,BRAND.colours.primary)]}).catch(()=>{});}
    if(s.personal_weekly_enabled){
      const users=await query<any>(`SELECT user_id FROM member_stats WHERE guild_id=$1 AND last_message_at>=now()-interval '7 days' LIMIT 500`,[guildId]);
      for(const u of users){const stats=await one<any>(`SELECT COALESCE(sum(CASE WHEN currency='xp' AND amount>0 THEN amount ELSE 0 END),0) xp,COALESCE(sum(CASE WHEN currency='coins' AND amount>0 THEN amount ELSE 0 END),0) coins FROM economy_ledger WHERE guild_id=$1 AND user_id=$2 AND created_at>=now()-interval '7 days'`,[guildId,u.user_id]);const kudos=Number((await one<any>(`SELECT count(*) c FROM reputation_events WHERE guild_id=$1 AND receiver_id=$2 AND created_at>=now()-interval '7 days'`,[guildId,u.user_id]))?.c||0);const profile=await getEconomyProfile(guildId,u.user_id);const user=await client.users.fetch(u.user_id).catch(()=>null);if(user)await user.send({embeds:[brandEmbed("Your EAFC.Live week",`+${fmt(Number(stats?.xp||0))} XP\n+${fmt(Number(stats?.coins||0))} Live Coins\n${kudos} kudos received\n🔥 ${profile.streak.current_streak||0}-day streak\n🏆 #${profile.rank} server rank`,BRAND.colours.primary)]}).catch(()=>{});}
    }
    await query(`UPDATE recap_settings SET last_weekly_key=$2,updated_at=now() WHERE guild_id=$1`,[guildId,wk]);
  }
  if(s.monthly_enabled&&s.last_monthly_key!==mk&&now.getUTCDate()===1&&now.getUTCHours()>=19){
    const m=await one<any>(`SELECT
      (SELECT count(*) FROM member_stats WHERE guild_id=$1 AND last_message_at>=now()-interval '30 days') active,
      (SELECT count(*) FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '30 days') kudos,
      (SELECT count(*) FROM member_funnel WHERE guild_id=$1 AND joined_at>=now()-interval '30 days') joins,
      (SELECT count(*) FROM member_funnel WHERE guild_id=$1 AND retained_7d=true AND joined_at>=now()-interval '60 days') retained`,[guildId]);
    const target=s.monthly_channel_id||s.weekly_channel_id;if(target){const ch=await client.channels.fetch(target).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send({embeds:[brandEmbed("📈 EAFC.Live monthly community report",`**${m?.active||0}** active members\n**${m?.joins||0}** joined\n**${m?.retained||0}** reached 7-day retention\n**${m?.kudos||0}** kudos given`,BRAND.colours.premium)]}).catch(()=>{});}
    await query(`UPDATE recap_settings SET last_monthly_key=$2,updated_at=now() WHERE guild_id=$1`,[guildId,mk]);
  }
}

async function updateBotStatusPanels(client:Client,guildId:string){
  if(Date.now()-(statusLastRun.get(guildId)||0)<config.statusUpdateSeconds*1000)return;
  statusLastRun.set(guildId,Date.now());
  const panel=await one<any>(`SELECT * FROM bot_status_panels WHERE guild_id=$1`,[guildId]);if(!panel)return;
  const ch=await client.channels.fetch(panel.channel_id).catch(()=>null);if(!ch?.isTextBased())return;
  const msg=await (ch as TextChannel).messages.fetch(panel.message_id).catch(()=>null);if(!msg)return;
  await msg.edit({embeds:[botStatusEmbed(client)]}).catch(()=>{});
  await query(`UPDATE bot_status_panels SET updated_at=now() WHERE guild_id=$1`,[guildId]).catch(()=>{});
}

export async function scanHealth(client:Client,guildId:string){
  const guild=client.guilds.cache.get(guildId);if(!guild)return [];
  const findings:any[]=[],me=guild.members.me;
  const push=(key:string,severity:string,title:string,detail:string,fixType?:string,fixPayload:any={})=>findings.push({key,severity,title,detail,fixType,fixPayload});
  if(!me?.permissions.has(PermissionFlagsBits.ManageRoles))push("bot-manage-roles","critical","Bot cannot manage roles","Grant the bot Manage Roles so verification, rewards and Premium roles can work.");
  if(!me?.permissions.has(PermissionFlagsBits.ManageChannels))push("bot-manage-channels","critical","Bot cannot manage channels","Grant Manage Channels for tickets, counters and server tooling.");
  if(!me?.permissions.has(PermissionFlagsBits.ViewAuditLog))push("bot-audit-log","warning","Anti-nuke cannot inspect audit logs","Grant View Audit Log so destructive staff actions can be attributed.");
  if(!me?.permissions.has(PermissionFlagsBits.ManageGuild))push("bot-invite-tracking","warning","Invite tracking cannot read server invites","Grant Manage Server so retained invite attribution and partner performance can work.");
  const settings=await query<any>(`SELECT feature_key,config FROM feature_settings WHERE guild_id=$1`,[guildId]);
  for(const s of settings){
    for(const [k,v] of Object.entries(s.config||{})){if(!v||typeof v!=="string")continue;if(k.toLowerCase().includes("channelid")&&!guild.channels.cache.has(v))push(`missing-channel:${s.feature_key}:${k}`,"warning",`${s.feature_key}: configured channel is missing`,`${k} points to a deleted channel.`,"clear_feature_key",{featureKey:s.feature_key,key:k});if(k.toLowerCase().includes("roleid")&&!guild.roles.cache.has(v))push(`missing-role:${s.feature_key}:${k}`,"warning",`${s.feature_key}: configured role is missing`,`${k} points to a deleted role.`,"clear_feature_key",{featureKey:s.feature_key,key:k});}
  }
  const plans=await query<any>(`SELECT id,name,role_id FROM billing_plans WHERE guild_id=$1 AND active=true`,[guildId]);for(const p of plans){const role=guild.roles.cache.get(p.role_id);if(!role)push(`billing-role:${p.id}`,"critical",`${p.name}: Premium role is missing`,"Choose a replacement Premium role in Billing.");else if(me&&role.position>=me.roles.highest.position)push(`billing-hierarchy:${p.id}`,"critical",`${p.name}: role is above the bot`,"Move the bot role above this Premium role.");}
  for(const channel of guild.channels.cache.values()){if(channel.parentId&&"permissionsLocked" in channel&&channel.permissionsLocked===false&&channel.permissionOverwrites.cache.size){push(`permission-drift:${channel.id}`,"warning",`#${channel.name}: permissions differ from its category`,"This may be intentional, but review the channel overrides because category and channel permissions are not synchronised.");}}
  const roleRefs:any[]=[];
  const onboard=await one<any>(`SELECT * FROM onboarding_configs WHERE guild_id=$1`,[guildId]);if(onboard){roleRefs.push(["verified",onboard.verified_role_id],["quarantine",onboard.quarantine_role_id]);for(const v of Object.values(onboard.platform_roles||{}))roleRefs.push(["onboarding",v]);for(const v of Object.values(onboard.interest_roles||{}))roleRefs.push(["interest",v]);}
  const rewardRoles=await query<any>(`SELECT id,name,role_id FROM store_items WHERE guild_id=$1 AND active=true AND role_id IS NOT NULL`,[guildId]);for(const r of rewardRoles)roleRefs.push([`reward ${r.name}`,r.role_id]);
  for(const [label,roleId] of roleRefs){if(!roleId)continue;const role=guild.roles.cache.get(String(roleId));if(!role)push(`role-missing:${label}:${roleId}`,"warning",`${label}: configured role is missing`,"Choose a replacement role in the relevant workspace.");else if(me&&role.position>=me.roles.highest.position)push(`role-hierarchy:${role.id}`,"critical",`@${role.name} is above the bot`,`The bot cannot assign or remove this ${label} role until its own role is moved higher.`);}
  const deadCounters=await query<any>(`SELECT id,channel_id,metric FROM server_counters WHERE guild_id=$1 AND enabled=true`,[guildId]);for(const c of deadCounters){if(!guild.channels.cache.has(c.channel_id))push(`counter-channel:${c.id}`,"warning","Server counter points to a deleted channel","Disable the broken counter.","disable_counter",{id:c.id});else if(c.metric==="online"&&guild.presences.cache.size<=1)push(`counter-presence:${c.id}`,"warning","Online counter may be incomplete","Discord presence data is not available. Enable the Server Presence intent in the Discord developer portal before relying on this counter.");}
  const deadReactionRoles=await query<any>(`SELECT message_id,emoji,role_id FROM reaction_roles WHERE guild_id=$1 AND enabled=true`,[guildId]);for(const rr of deadReactionRoles)if(!guild.roles.cache.has(rr.role_id))push(`reaction-role:${rr.message_id}:${rr.emoji}`,"warning","Reaction role points to a deleted role","Disable the broken reaction-role mapping.","disable_reaction_role",{messageId:rr.message_id,emoji:rr.emoji});
  await query(`UPDATE health_findings SET active=false,resolved_at=now() WHERE guild_id=$1`,[guildId]);
  for(const f of findings)await query(`INSERT INTO health_findings(guild_id,finding_key,severity,title,detail,fix_type,fix_payload,active,detected_at,resolved_at) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,true,now(),NULL) ON CONFLICT(guild_id,finding_key) DO UPDATE SET severity=$3,title=$4,detail=$5,fix_type=$6,fix_payload=$7::jsonb,active=true,detected_at=now(),resolved_at=NULL`,[guildId,f.key,f.severity,f.title,f.detail,f.fixType||null,JSON.stringify(f.fixPayload||{})]);
  return findings;
}

export async function applyHealthFix(guildId:string,findingId:number){
  const f=await one<any>(`SELECT * FROM health_findings WHERE id=$1 AND guild_id=$2 AND active=true`,[findingId,guildId]);if(!f)throw new Error("Finding not found.");
  if(f.fix_type==="clear_feature_key"){
    const row=await one<any>(`SELECT config FROM feature_settings WHERE guild_id=$1 AND feature_key=$2`,[guildId,f.fix_payload.featureKey]);if(!row)throw new Error("Feature setting no longer exists.");
    const cfg={...(row.config||{})};delete cfg[f.fix_payload.key];await query(`UPDATE feature_settings SET config=$3::jsonb,updated_at=now() WHERE guild_id=$1 AND feature_key=$2`,[guildId,f.fix_payload.featureKey,JSON.stringify(cfg)]);
    await query(`UPDATE health_findings SET active=false,resolved_at=now() WHERE id=$1`,[findingId]);return true;
  }
  if(f.fix_type==="disable_counter"){await query(`UPDATE server_counters SET enabled=false,updated_at=now() WHERE id=$1 AND guild_id=$2`,[f.fix_payload.id,guildId]);await query(`UPDATE health_findings SET active=false,resolved_at=now() WHERE id=$1`,[findingId]);return true;}
  if(f.fix_type==="disable_reaction_role"){await query(`UPDATE reaction_roles SET enabled=false WHERE guild_id=$1 AND message_id=$2 AND emoji=$3`,[guildId,f.fix_payload.messageId,f.fix_payload.emoji]);await query(`UPDATE health_findings SET active=false,resolved_at=now() WHERE id=$1`,[findingId]);return true;}
  throw new Error("This finding needs a manual Discord permission change.");
}

export async function inspectMemberPermission(guildId:string,userId:string,channelId:string){
  const guild=globalClient?.guilds.cache.get(guildId);if(!guild)throw new Error("Guild unavailable.");
  const member=await guild.members.fetch(userId),channel=guild.channels.cache.get(channelId);if(!channel)throw new Error("Channel unavailable.");
  const c:any=channel;if(!c.permissionsFor||!c.permissionOverwrites)throw new Error("That channel type does not expose permission overwrites.");
  const perms=c.permissionsFor(member),everyone=c.permissionOverwrites.cache.get(guild.id),memberOw=c.permissionOverwrites.cache.get(member.id);
  const roleDetails=member.roles.cache.filter((r:any)=>r.id!==guild.id).map((r:any)=>{const ow=c.permissionOverwrites.cache.get(r.id);return {id:r.id,name:r.name,allow:ow?[...ow.allow.toArray()]:[],deny:ow?[...ow.deny.toArray()]:[]};});
  return {member:{id:member.id,name:member.displayName},channel:{id:channel.id,name:channel.name},effective:perms?[...perms.toArray()]:[],everyone:{allow:everyone?[...everyone.allow.toArray()]:[],deny:everyone?[...everyone.deny.toArray()]:[]},memberOverride:{allow:memberOw?[...memberOw.allow.toArray()]:[],deny:memberOw?[...memberOw.deny.toArray()]:[]},roles:roleDetails};
}

export async function publishTemplate(client:Client,guildId:string,templateId:number,channelId:string){
  const t=await one<any>(`SELECT * FROM message_templates WHERE id=$1 AND guild_id=$2`,[templateId,guildId]);if(!t)throw new Error("Template not found.");
  const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased())throw new Error("Channel unavailable.");
  const embed=brandEmbed(t.title||t.name,t.body||"",Number(t.colour||BRAND.colours.primary));if(t.image_url)embed.setImage(t.image_url);if(t.thumbnail_url)embed.setThumbnail(t.thumbnail_url);
  const rows:any[]=[];
  const buttons=Array.isArray(t.button_config)?t.button_config:[];
  if(buttons.length){const row=new ActionRowBuilder<ButtonBuilder>();for(const b of buttons.slice(0,5)){const btn=new ButtonBuilder().setLabel(String(b.label||"Open").slice(0,80));if(b.url)btn.setStyle(ButtonStyle.Link).setURL(String(b.url));else if(b.roleId)btn.setStyle(ButtonStyle.Secondary).setCustomId(`v5:role:${b.roleId}`);else btn.setStyle(ButtonStyle.Secondary).setCustomId(`v5:noop:${templateId}`);row.addComponents(btn);}rows.push(row);}
  const select=t.select_config||{};if(Array.isArray(select.options)&&select.options.length&&rows.length<5){const menu=new StringSelectMenuBuilder().setCustomId(`v5:template-select:${templateId}`).setPlaceholder(String(select.placeholder||"Choose an option").slice(0,100));for(const o of select.options.slice(0,25))menu.addOptions(new StringSelectMenuOptionBuilder().setLabel(String(o.label||o.value).slice(0,100)).setValue(String(o.value).slice(0,100)));rows.push(new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu));}
  const mention=t.mention_role_id?`<@&${t.mention_role_id}>`:undefined;
  const msg=await (ch as TextChannel).send({content:mention,embeds:[embed],components:rows,allowedMentions:t.mention_role_id?{roles:[t.mention_role_id]}:{parse:[]}});
  await query(`INSERT INTO published_messages(guild_id,template_id,channel_id,message_id,purpose) VALUES($1,$2,$3,$4,$5)`,[guildId,templateId,channelId,t.template_type]);
  return msg;
}

export async function publishRolePanel(client:Client,guildId:string,panelId:number){
  const p=await one<any>(`SELECT * FROM role_panels WHERE id=$1 AND guild_id=$2`,[panelId,guildId]);if(!p)throw new Error("Role panel not found.");
  const ch=await client.channels.fetch(p.channel_id).catch(()=>null);if(!ch?.isTextBased())throw new Error("Channel unavailable.");
  const roles=Array.isArray(p.roles)?p.roles:[],components:any[]=[];
  if(p.panel_type==="buttons"){
    for(let offset=0;offset<roles.length&&components.length<5;offset+=5){const row=new ActionRowBuilder<ButtonBuilder>();for(const x of roles.slice(offset,offset+5))row.addComponents(new ButtonBuilder().setCustomId(`v5:role:${x.roleId}`).setLabel(String(x.label||x.name||"Role").slice(0,80)).setStyle(ButtonStyle.Secondary));components.push(row);}
  }else{
    const menu=new StringSelectMenuBuilder().setCustomId(`v5:panel:${p.id}`).setPlaceholder("Choose your options").setMinValues(0).setMaxValues(Math.min(25,roles.length));
    for(const x of roles.slice(0,25)){
      const option=new StringSelectMenuOptionBuilder().setLabel(String(x.label||x.name||"Role").slice(0,100)).setValue(String(x.roleId));
      if(x.description)option.setDescription(String(x.description).slice(0,100));
      if(x.emoji)option.setEmoji(String(x.emoji));
      menu.addOptions(option);
    }
    components.push(new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu));
  }
  const msg=await (ch as TextChannel).send({embeds:[systemEmbed(p.title,p.body||"",BRAND.colours.primary)],components});
  await query(`UPDATE role_panels SET message_id=$2,updated_at=now() WHERE id=$1`,[p.id,msg.id]);return msg;
}

export async function publishDailyPanel(client:Client,guildId:string,channelId:string){
  const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased())throw new Error("Channel unavailable.");
  const row=new ActionRowBuilder<ButtonBuilder>().addComponents(new ButtonBuilder().setCustomId("v5:daily").setLabel("Claim daily reward").setEmoji("🔥").setStyle(ButtonStyle.Success),new ButtonBuilder().setCustomId("economy:shop-refresh").setLabel("Rewards store").setEmoji("🪙").setStyle(ButtonStyle.Secondary));
  return (ch as TextChannel).send({embeds:[brandEmbed("🔥 Daily check-in","Claim your daily Live Coins, build your streak and work through community quests.",BRAND.colours.coins)],components:[row]});
}

export async function publishFlashDrop(client:Client,guildId:string,channelId:string,name:string,coins:number,xp:number,durationMinutes:number,maxClaims:number|null,actorId:string){
  const ch=await client.channels.fetch(channelId).catch(()=>null);if(!ch?.isTextBased())throw new Error("Channel unavailable.");
  const ends=new Date(Date.now()+durationMinutes*60000),row=(await query<any>(`INSERT INTO flash_drops(guild_id,channel_id,name,reward_coins,reward_xp,max_claims,ends_at,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *`,[guildId,channelId,name,coins,xp,maxClaims,ends,actorId]))[0];
  const components=new ActionRowBuilder<ButtonBuilder>().addComponents(new ButtonBuilder().setCustomId(`v5:drop:${row.id}`).setLabel("Claim drop").setEmoji("⚡").setStyle(ButtonStyle.Success));
  const msg=await (ch as TextChannel).send({embeds:[brandEmbed(`⚡ ${name}`,`Claim **${fmt(coins)} Live Coins**${xp?` + **${fmt(xp)} XP**`:""} before <t:${Math.floor(ends.getTime()/1000)}:R>.${maxClaims?`\nFirst **${maxClaims}** claims only.`:""}`,BRAND.colours.coins)],components:[components]});
  await query(`UPDATE flash_drops SET message_id=$2 WHERE id=$1`,[row.id,msg.id]);return row;
}

export async function runV5Tick(client:Client){
  globalClient=client;
  const guilds=await query<any>(`SELECT guild_id FROM guild_settings`);
  for(const g of guilds){
    await ensureV5Defaults(g.guild_id);
    await Promise.all([
      awardKudosMilestones(client,g.guild_id),
      processLevelWorkflows(client,g.guild_id),
      processBirthdays(client,g.guild_id),
      processRetention(g.guild_id),
      processInviteMilestones(client,g.guild_id),
      processBoosterMilestones(client,g.guild_id),
      processRecognitionRoles(client,g.guild_id),
      processCounters(client,g.guild_id),
      processRecaps(client,g.guild_id),
      updateBotStatusPanels(client,g.guild_id)
    ]).catch(console.error);
    if(Date.now()-(healthLastRun.get(g.guild_id)||0)>10*60_000){healthLastRun.set(g.guild_id,Date.now());await scanHealth(client,g.guild_id).catch(console.error);}
  }
  await query(`UPDATE flash_drops SET status='ENDED' WHERE status='LIVE' AND ends_at<=now()`);
  const expired=await query<any>(`DELETE FROM temporary_role_grants WHERE expires_at IS NOT NULL AND expires_at<=now() RETURNING *`);
  for(const x of expired){const guild=client.guilds.cache.get(x.guild_id),member=guild?await guild.members.fetch(x.user_id).catch(()=>null):null;if(member)await member.roles.remove(x.role_id,"EAFC.Live temporary role expired").catch(()=>{});}
}

export function attachV5Client(client:Client){globalClient=client;}
