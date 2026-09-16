import {
  Client, Events, GatewayIntentBits, Partials, REST, Routes, TextChannel
} from "discord.js";
import { config } from "./config.js";
import { commandData, handleCommand } from "./commands.js";
import { handleJoin, handleMessage } from "./automod.js";
import { getFeature, query } from "./db.js";

export const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildModeration
  ],
  partials: [Partials.Channel, Partials.Message, Partials.User, Partials.GuildMember]
});

export async function startBot() {
  const rest=new REST({version:"10"}).setToken(config.discordToken);
  await rest.put(Routes.applicationGuildCommands(config.clientId,config.targetGuildId),{body:commandData});

  client.once(Events.ClientReady, async ready => {
    console.log(`Discord ready as ${ready.user.tag}`);
    const guild=await ready.guilds.fetch(config.targetGuildId).catch(()=>null);
    if(guild) await query(`INSERT INTO guild_settings(guild_id,guild_name) VALUES($1,$2) ON CONFLICT(guild_id) DO UPDATE SET guild_name=$2,updated_at=now()`,[guild.id,guild.name]);
  });

  client.on(Events.InteractionCreate, async interaction => {
    if(interaction.isChatInputCommand()) {
      try { await handleCommand(client,interaction); }
      catch(err) {
        console.error(err);
        const payload={content:"Something went wrong running that command.",ephemeral:true};
        if(interaction.replied||interaction.deferred) await interaction.followUp(payload).catch(()=>{});
        else await interaction.reply(payload).catch(()=>{});
      }
    }
  });

  client.on(Events.MessageCreate, handleMessage);

  client.on(Events.GuildMemberAdd, async member => {
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

  await client.login(config.discordToken);
}
