import { PermissionFlagsBits, TextChannel } from "discord.js";
import { getFeature } from "./db.js";

/** Keep moderation feature state and its configured staff roles authoritative at runtime. */
export async function moderationCommandAllowed(i:any):Promise<boolean>{
  const feature=await getFeature(i.guildId,"mod_tools",{staffRoleIds:[],modLogChannelId:""});
  if(!feature.enabled){
    await i.reply({content:"Staff moderation is switched off for this server. A server admin can enable it in Admin → Safety → Staff moderation.",ephemeral:true});
    return false;
  }
  const roles=Array.isArray(feature.config.staffRoleIds)?feature.config.staffRoleIds.map(String):[];
  const member=i.member?.roles?.cache?i.member:await i.guild.members.fetch(i.user.id);
  const admin=Boolean(member.permissions?.has(PermissionFlagsBits.Administrator)||member.permissions?.has(PermissionFlagsBits.ManageGuild));
  if(!admin&&(!roles.length||!member.roles.cache.some((role:any)=>roles.includes(role.id)))){
    await i.reply({content:"You need a configured moderation staff role to use this command. Ask a server admin to check Staff moderation setup.",ephemeral:true});
    return false;
  }
  return true;
}

/** Send a human-readable copy to the selected log channel; the database audit remains authoritative. */
export async function postModerationLog(client:any,guildId:string,action:string,details:string){
  const feature=await getFeature(guildId,"mod_tools",{modLogChannelId:""});
  if(!feature.enabled||!feature.config.modLogChannelId)return;
  const channel=await client.channels.fetch(String(feature.config.modLogChannelId)).catch(()=>null);
  if(channel?.isTextBased())await (channel as TextChannel).send({content:`**${action}**\n${details}`,allowedMentions:{parse:[]}}).catch(()=>{});
}
