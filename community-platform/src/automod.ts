import { Client, Message, PermissionFlagsBits, TextChannel } from "discord.js";
import { audit, getFeature, one, query } from "./db.js";

const recent = new Map<string, { content:string; times:number[] }>();
const joins = new Map<string, number[]>();
const inviteRegex = /(discord\.gg\/|discord(?:app)?\.com\/invite\/)[a-z0-9-]+/i;
const urlRegex = /https?:\/\/([^\s/]+)/ig;
const suspicious=/\b(free\s*(coins?|points?|fc)|claim\s*(coins?|reward)|verify\s*(account|wallet)|steamcommunity\.[^\s]*gift|nitro\s*gift)\b/i;

export async function handleMessage(message: Message) {
  if (!message.guildId || message.author.bot || !message.member) return;

  const levels = await getFeature(message.guildId, "levels", {messageXp:2,cooldownSeconds:60,ignoredChannelIds:[],rewards:[]});
  if (levels.enabled && !(levels.config.ignoredChannelIds as string[] || []).includes(message.channelId)) {
    const now=Date.now(),statKey=`xp:${message.guildId}:${message.author.id}`,hit=recent.get(statKey);
    if(!hit || !hit.times[0] || now-hit.times[0] > Number(levels.config.cooldownSeconds||60)*1000) {
      recent.set(statKey,{content:"",times:[now]});
      const economy=await one<any>(`SELECT enabled FROM economy_settings WHERE guild_id=$1`,[message.guildId]);
      const legacyXp=economy?.enabled===false?Number(levels.config.messageXp||2):0;
      await query(`INSERT INTO member_stats(guild_id,user_id,xp,messages,last_message_at) VALUES($1,$2,$3,1,now()) ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=member_stats.xp+$3,messages=member_stats.messages+1,last_message_at=now()`,[message.guildId,message.author.id,legacyXp]);
      const stat=await one<any>(`SELECT xp FROM member_stats WHERE guild_id=$1 AND user_id=$2`,[message.guildId,message.author.id]);
      for(const reward of (levels.config.rewards||[]) as any[]) if(reward.roleId&&Number(stat?.xp||0)>=Number(reward.xp||0)&&!message.member.roles.cache.has(reward.roleId)) await message.member.roles.add(reward.roleId,"EAFC.Live level reward").catch(()=>{});
    }
  }

  const feature=await getFeature(message.guildId,"automod",{
    blockInvites:true,inviteBypassRoleIds:[],maxMentions:5,duplicateWindowSeconds:15,duplicateLimit:4,
    blockedTerms:[],blockedDomains:[],action:"delete",timeoutMinutes:10,modLogChannelId:"",phishingDetection:true,capsPercent:85,capsMinLength:18
  });
  if(!feature.enabled || message.member.permissions.has(PermissionFlagsBits.ManageMessages)) return;

  const cfg=feature.config as any;let reason="";const content=message.content.toLowerCase();
  if(cfg.blockInvites && inviteRegex.test(message.content) && !message.member.roles.cache.some(r=>(cfg.inviteBypassRoleIds||[]).includes(r.id))) reason="Discord invite";
  if(!reason && message.mentions.users.size + message.mentions.roles.size > Number(cfg.maxMentions||5)) reason="Mention spam";
  if(!reason && (cfg.blockedTerms||[]).some((term:string)=>term && content.includes(term.toLowerCase()))) reason="Blocked term";
  if(!reason && cfg.phishingDetection!==false && suspicious.test(message.content) && /https?:\/\//i.test(message.content)) reason="Possible phishing/scam message";
  if(!reason && message.content.length>=Number(cfg.capsMinLength||18)) {const letters=message.content.replace(/[^a-z]/gi,"");const upper=letters.replace(/[^A-Z]/g,"").length;if(letters.length&&upper/letters.length*100>=Number(cfg.capsPercent||85)) reason="Excessive caps";}
  if(!reason && (cfg.blockedDomains||[]).length) for(const match of message.content.matchAll(urlRegex)){const host=(match[1]||"").toLowerCase().replace(/^www\./,"");if((cfg.blockedDomains as string[]).some((d:string)=>host===d.toLowerCase()||host.endsWith(`.${d.toLowerCase()}`))){reason="Blocked/scam domain";break;}}

  const key=`dup:${message.guildId}:${message.author.id}`,now=Date.now(),windowMs=Number(cfg.duplicateWindowSeconds||15)*1000,state=recent.get(key)||{content:"",times:[]};state.times=state.times.filter(t=>now-t<windowMs);if(state.content===content&&content.length>3)state.times.push(now);else{state.content=content;state.times=[now];}recent.set(key,state);if(!reason&&state.times.length>=Number(cfg.duplicateLimit||4))reason="Repeated-message spam";
  if(!reason)return;
  await message.delete().catch(()=>{});if(cfg.action==="timeout"||reason.includes("phishing"))await message.member.timeout(Number(cfg.timeoutMinutes||10)*60_000,`Automod: ${reason}`).catch(()=>{});await audit(message.guildId,null,"automod.action",{userId:message.author.id,reason,channelId:message.channelId});
  if(cfg.modLogChannelId){const ch=await message.client.channels.fetch(String(cfg.modLogChannelId)).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send(`🛡️ Automod: **${reason}** • ${message.author} in <#${message.channelId}>`).catch(()=>{});}
}

export async function handleJoin(client:Client, member:any) {
  const feature=await getFeature(member.guild.id,"join_security",{minAccountAgeHours:24,alertChannelId:"",joinsPerMinuteAlert:8,raidModeRoleId:""});
  if(!feature.enabled) return;
  const now=Date.now(),arr=(joins.get(member.guild.id)||[]).filter(t=>now-t<60_000);arr.push(now);joins.set(member.guild.id,arr);
  const ageHours=(now-member.user.createdTimestamp)/3_600_000,young=ageHours<Number(feature.config.minAccountAgeHours||24),raid=arr.length>=Number(feature.config.joinsPerMinuteAlert||8);
  if(feature.config.raidModeRoleId&&raid) await member.roles.add(String(feature.config.raidModeRoleId),"Automatic raid mode").catch(()=>{});
  if((young||raid)&&feature.config.alertChannelId){const ch=await client.channels.fetch(String(feature.config.alertChannelId)).catch(()=>null);if(ch?.isTextBased())await (ch as TextChannel).send(raid?`🚨 **Raid alert:** ${arr.length} members joined in the last minute. Latest: ${member.user.tag}`:`⚠️ New account joined: ${member.user.tag} (${ageHours.toFixed(1)} hours old).`);}
  if(raid) await audit(member.guild.id,null,"security.raid_alert",{joinsLastMinute:arr.length,userId:member.id});
}
