import {
  Client, Events, GatewayIntentBits, Partials, REST, Routes, TextChannel
} from "discord.js";
import { config } from "./config.js";
import { commandData, handleCommand } from "./commands.js";
import { billingCommandData, handleBillingAutocomplete, handleBillingCommand } from "./billing-commands.js";
import { handleJoin, handleMessage } from "./automod.js";
import { getFeature, query } from "./db.js";
import {
  featureCommandData, handleComponent, handleContextCommand, handleFeatureAutocomplete,
  handleFeatureCommand, onMemberActivity, onMemberJoinLeave
} from "./feature-suite.js";
import { handleTicketOps, ticketOpsCommandData } from "./ticket-ops.js";
import { economyCommandData, handleEconomyAutocomplete, handleEconomyCommand, handleEconomyComponent, onEconomyJoin, onEconomyMessage } from "./economy.js";
import { ensureEconomyDefaults } from "./economy-core.js";
import { handleCommunityMessage, onCommunityReactionAdd, onCommunityReactionRemove } from "./community-features.js";
import {
  attachV5Client, ensureV5Defaults, handleV5Command, handleV5Component, handleV5Context, onV5AuditEntry,
  onV5MemberAdd, onV5MemberRemove, onV5MemberUpdate, onV5Message, onV5Reaction, recordUsage,
  refreshInviteSnapshot, v5CommandData, v5ContextCommandData
} from "./community-suite-v5.js";
import { guildSystemEmbed, BRAND } from "./brand.js";

const commandFeatureMap:Record<string,string>={
  kudos:"reputation",kudosboard:"reputation",rank:"levels",leaderboard:"levels",profile:"levels",wallet:"levels",daily:"levels",quests:"levels",season:"levels",
  shop:"rewards",redeem:"rewards",giveaway:"giveaways",suggest:"suggestions",ticket:"tickets",ticketstaff:"tickets",verify:"onboarding",birthday:"birthdays",afk:"afk",
  referral:"premium_billing",premium:"premium_billing",subscription:"premium_billing",giftpremium:"premium_billing",
  warn:"mod_tools",history:"mod_tools",note:"mod_tools",timeout:"mod_tools",kick:"mod_tools",ban:"mod_tools",purge:"mod_tools",slowmode:"mod_tools",lock:"mod_tools",unlock:"mod_tools",nick:"mod_tools",role:"mod_tools",
  event:"scheduled_messages",achievements:"levels",system:"system_panels",serverbrand:"server_branding"
};

export const client = new Client({
  intents: [GatewayIntentBits.Guilds,GatewayIntentBits.GuildMembers,GatewayIntentBits.GuildMessages,GatewayIntentBits.MessageContent,GatewayIntentBits.GuildModeration,GatewayIntentBits.GuildMessageReactions,GatewayIntentBits.GuildInvites],
  partials: [Partials.Channel, Partials.Message, Partials.User, Partials.GuildMember, Partials.Reaction]
});

function assertUniqueCommands(commands:any[]){
  const seen=new Set<string>(),duplicates=new Set<string>();
  for(const command of commands){const name=String(command?.name||"");if(seen.has(name))duplicates.add(name);seen.add(name);}
  if(duplicates.size)throw new Error(`Duplicate Discord command names: ${[...duplicates].join(", ")}`);
}

function normalizeCommandOptions(command:any):any {
  const clone={...command};
  if(!Array.isArray(command?.options)) return clone;

  const options=command.options.map((option:any)=>normalizeCommandOptions(option));
  const hasSubcommands=options.some((option:any)=>option?.type===1||option?.type===2);

  clone.options=hasSubcommands
    ? options
    : options.map((option:any,index:number)=>({option,index}))
        .sort((a:any,b:any)=>Number(Boolean(b.option?.required))-Number(Boolean(a.option?.required))||a.index-b.index)
        .map((entry:any)=>entry.option);

  return clone;
}

async function ensureGuildDefaults(guild:any) {
  await query(`INSERT INTO guild_settings(guild_id,guild_name) VALUES($1,$2) ON CONFLICT(guild_id) DO UPDATE SET guild_name=$2,updated_at=now()`,[guild.id,guild.name]);
  await ensureEconomyDefaults(guild.id);
  await ensureV5Defaults(guild.id);
  await refreshInviteSnapshot(guild).catch(()=>{});
}

async function registerCommandsForGuild(rest:REST,guildId:string,commands:any[]) {
  await rest.put(Routes.applicationGuildCommands(config.clientId,guildId),{body:commands});
}

export async function startBot() {
  const rest=new REST({version:"10"}).setToken(config.discordToken);
  const commands=[...commandData,...billingCommandData,...economyCommandData,...featureCommandData,...ticketOpsCommandData,...v5CommandData,...v5ContextCommandData].map(normalizeCommandOptions);
  assertUniqueCommands(commands);
  client.once(Events.ClientReady, async ready => {console.log(`Discord ready as ${ready.user.tag}`);attachV5Client(client);for(const guild of ready.guilds.cache.values()){await registerCommandsForGuild(rest,guild.id,commands).catch(err=>console.error("Command registration failed",guild.id,err));await ensureGuildDefaults(guild).catch(err=>console.error("Guild init failed",guild.id,err));}});
  client.on(Events.GuildCreate,async guild=>{await registerCommandsForGuild(rest,guild.id,commands).catch(err=>console.error("Command registration failed",guild.id,err));await ensureGuildDefaults(guild).catch(err=>console.error("Guild init failed",guild.id,err));});
  client.on(Events.InteractionCreate, async interaction => {try{
    if(interaction.isAutocomplete()){if(await handleBillingAutocomplete(interaction))return;if(await handleEconomyAutocomplete(interaction))return;if(await handleFeatureAutocomplete(interaction))return;await interaction.respond([]).catch(()=>{});return;}
    if(interaction.guildId){if(interaction.isChatInputCommand()){void recordUsage(interaction.guildId,interaction.user.id,"command",interaction.commandName,interaction.channelId||undefined);const mapped=commandFeatureMap[interaction.commandName];if(mapped)void recordUsage(interaction.guildId,interaction.user.id,"feature",mapped,interaction.channelId||undefined,{command:interaction.commandName});}else if(interaction.isButton()||interaction.isStringSelectMenu())void recordUsage(interaction.guildId,interaction.user.id,"component",String(interaction.customId||"component").split(":").slice(0,2).join(":"),interaction.channelId||undefined);}
    if((interaction.isButton()||interaction.isStringSelectMenu()||interaction.isModalSubmit())&&await handleV5Component(client,interaction))return;
    if(interaction.isButton()&&await handleEconomyComponent(client,interaction))return;
    if((interaction.isButton()||interaction.isStringSelectMenu())&&await handleComponent(client,interaction))return;
    if((interaction.isUserContextMenuCommand()||interaction.isMessageContextMenuCommand())&&await handleV5Context(client,interaction))return;
    if((interaction.isUserContextMenuCommand()||interaction.isMessageContextMenuCommand())&&await handleContextCommand(interaction))return;
    if(interaction.isChatInputCommand()){if(await handleV5Command(interaction))return;if(await handleBillingCommand(client,interaction))return;if(await handleEconomyCommand(client,interaction))return;if(await handleTicketOps(client,interaction))return;if(await handleFeatureCommand(client,interaction))return;await handleCommand(client,interaction);}
  }catch(err){console.error("Interaction error",err);const payload={content:"Something went wrong running that action.",ephemeral:true};if("replied" in interaction&&(interaction.replied||interaction.deferred))await interaction.followUp(payload).catch(()=>{});else if("reply" in interaction)await interaction.reply(payload).catch(()=>{});}});
  client.on(Events.MessageCreate,async message=>{await handleMessage(message);await handleCommunityMessage(message).catch(console.error);await onV5Message(message).catch(console.error);await onMemberActivity(message).catch(console.error);await onEconomyMessage(message).catch(console.error);});
  client.on(Events.MessageReactionAdd,(reaction,user)=>{void onCommunityReactionAdd(reaction,user);void onV5Reaction(reaction,user,true);});
  client.on(Events.MessageReactionRemove,(reaction,user)=>{void onCommunityReactionRemove(reaction,user);void onV5Reaction(reaction,user,false);});
  client.on(Events.GuildMemberAdd,async member=>{await onMemberJoinLeave(member.guild.id,"joins").catch(console.error);await onEconomyJoin(member.guild.id,member.id).catch(console.error);await onV5MemberAdd(member).catch(console.error);await handleJoin(client,member);const feature=await getFeature(member.guild.id,"welcome",{channelId:"",autoRoleId:"",message:"Welcome {user} to {server}! Please read and accept the server rules.",dmWelcome:false});if(!feature.enabled)return;if(feature.config.autoRoleId)await member.roles.add(String(feature.config.autoRoleId)).catch(()=>{});const text=String(feature.config.message||"Welcome {user}!").replaceAll("{user}",`<@${member.id}>`).replaceAll("{server}",member.guild.name);if(feature.config.channelId){const ch=await client.channels.fetch(String(feature.config.channelId)).catch(()=>null);if(ch?.isTextBased()){const embed=(await guildSystemEmbed(member.guild.id,`Welcome to ${member.guild.name}`,text,BRAND.colours.primary)).setThumbnail(member.user.displayAvatarURL()).addFields({name:"Member count",value:String(member.guild.memberCount),inline:false});await (ch as TextChannel).send({content:`Welcome ${member}. Say hi!`,embeds:[embed],allowedMentions:{users:[member.id]}}).catch(()=>{});}}if(feature.config.dmWelcome)await member.send(text.replace(`<@${member.id}>`,member.user.username)).catch(()=>{});});
  client.on(Events.GuildMemberRemove,member=>{void onMemberJoinLeave(member.guild.id,"leaves").catch(console.error);void onV5MemberRemove(member).catch(console.error);});
  client.on(Events.GuildMemberUpdate,(oldMember,newMember)=>{void onV5MemberUpdate(oldMember,newMember).catch(console.error);});
  client.on(Events.GuildAuditLogEntryCreate,(entry,guild)=>{void onV5AuditEntry(entry,guild).catch(console.error);});
  await client.login(config.discordToken);
}
