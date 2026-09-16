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

export const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildModeration,
    GatewayIntentBits.GuildMessageReactions
  ],
  partials: [Partials.Channel, Partials.Message, Partials.User, Partials.GuildMember, Partials.Reaction]
});

export async function startBot() {
  const rest=new REST({version:"10"}).setToken(config.discordToken);
  await rest.put(Routes.applicationGuildCommands(config.clientId,config.targetGuildId),{body:[...commandData,...billingCommandData,...featureCommandData]});

  client.once(Events.ClientReady, async ready => {
    console.log(`Discord ready as ${ready.user.tag}`);
    const guild=await ready.guilds.fetch(config.targetGuildId).catch(()=>null);
    if(guild) await query(`INSERT INTO guild_settings(guild_id,guild_name) VALUES($1,$2) ON CONFLICT(guild_id) DO UPDATE SET guild_name=$2,updated_at=now()`,[guild.id,guild.name]);
  });

  client.on(Events.InteractionCreate, async interaction => {
    try {
      if(interaction.isAutocomplete()) {
        if(await handleBillingAutocomplete(interaction)) return;
        if(await handleFeatureAutocomplete(interaction)) return;
        await interaction.respond([]).catch(()=>{});
        return;
      }
      if(interaction.isButton()) {
        if(await handleComponent(client,interaction)) return;
      }
      if(interaction.isUserContextMenuCommand()||interaction.isMessageContextMenuCommand()) {
        if(await handleContextCommand(interaction)) return;
      }
      if(interaction.isChatInputCommand()) {
        if(await handleBillingCommand(client,interaction)) return;
        if(await handleFeatureCommand(client,interaction)) return;
        await handleCommand(client,interaction);
      }
    } catch(err) {
      console.error("Interaction error",err);
      const payload={content:"Something went wrong running that action.",ephemeral:true};
      if("replied" in interaction && (interaction.replied||interaction.deferred)) await interaction.followUp(payload).catch(()=>{});
      else if("reply" in interaction) await interaction.reply(payload).catch(()=>{});
    }
  });

  client.on(Events.MessageCreate, async message => {
    await handleMessage(message);
    await onMemberActivity(message).catch(console.error);
  });

  client.on(Events.GuildMemberAdd, async member => {
    await onMemberJoinLeave(member.guild.id,"joins").catch(console.error);
    await handleJoin(client,member);
    const feature=await getFeature(member.guild.id,"welcome",{channelId:"",autoRoleId:"",message:"Welcome {user} to {server}!",dmWelcome:false});
    if(!feature.enabled) return;
    if(feature.config.autoRoleId) await member.roles.add(String(feature.config.autoRoleId)).catch(()=>{});
    const text=String(feature.config.message||"Welcome {user}!").replaceAll("{user}",`<@${member.id}>`).replaceAll("{server}",member.guild.name);
    if(feature.config.channelId) {
      const ch=await client.channels.fetch(String(feature.config.channelId)).catch(()=>null);
      if(ch?.isTextBased()) await (ch as TextChannel).send(text).catch(()=>{});
    }
    if(feature.config.dmWelcome) await member.send(text.replace(`<@${member.id}>`,member.user.username)).catch(()=>{});
  });
  client.on(Events.GuildMemberRemove,member=>{void onMemberJoinLeave(member.guild.id,"leaves").catch(console.error);});

  await client.login(config.discordToken);
}
