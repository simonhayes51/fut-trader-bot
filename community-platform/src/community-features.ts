import { Client, Message, MessageReaction, PartialMessageReaction, PartialUser, TextChannel, User } from "discord.js";
import { getFeature, one, query } from "./db.js";
import { brandEmbed, BRAND } from "./brand.js";

const responseMemory=new Map<string,number>();

function triggerMatches(mode:string,trigger:string,content:string){
  const a=content.toLowerCase(),b=trigger.toLowerCase();
  if(mode==="exact")return a.trim()===b.trim();
  if(mode==="starts_with")return a.trim().startsWith(b.trim());
  return a.includes(b);
}

export async function handleCommunityMessage(message:Message){
  if(!message.guildId||message.author.bot)return;

  const responses=await query<any>(`SELECT * FROM custom_responses WHERE guild_id=$1 AND enabled=true ORDER BY id`,[message.guildId]);
  for(const row of responses){
    if(row.channel_ids?.length&&!row.channel_ids.includes(message.channelId))continue;
    if(!triggerMatches(row.match_mode,row.trigger,message.content))continue;
    const key=`${message.guildId}:${row.id}:${message.channelId}`,now=Date.now();
    if((responseMemory.get(key)||0)>now)continue;
    responseMemory.set(key,now+Math.max(1,Number(row.cooldown_seconds||30))*1000);
    await message.reply({content:String(row.response).slice(0,2000),allowedMentions:{repliedUser:false}}).catch(()=>{});
  }

  const sticky=await one<any>(`SELECT * FROM sticky_messages WHERE guild_id=$1 AND channel_id=$2 AND enabled=true`,[message.guildId,message.channelId]);
  if(sticky){
    const last=sticky.last_posted_at?new Date(sticky.last_posted_at).getTime():0;
    if(Date.now()-last>=Math.max(60,Number(sticky.min_interval_seconds||300))*1000){
      const channel=message.channel;
      if(sticky.last_message_id&&channel.isTextBased()){
        const old=await channel.messages.fetch(sticky.last_message_id).catch(()=>null);
        if(old?.author.id===message.client.user?.id)await old.delete().catch(()=>{});
      }
      const sent=await (message.channel as TextChannel).send({embeds:[brandEmbed("📌 Pinned reminder",String(sticky.content).slice(0,4000),BRAND.colours.neutral)]}).catch(()=>null);
      if(sent)await query(`UPDATE sticky_messages SET last_message_id=$1,last_posted_at=now(),updated_at=now() WHERE id=$2`,[sent.id,sticky.id]);
    }
  }
}

async function syncStarboard(reaction:MessageReaction|PartialMessageReaction,user:User|PartialUser){
  if(user.bot)return;
  if(reaction.partial)await reaction.fetch().catch(()=>null);
  const message=reaction.message;
  if(!message.guildId)return;
  if(message.partial)await message.fetch().catch(()=>null);

  const feature=await getFeature(message.guildId,"starboard",{channelId:"",emoji:"⭐",threshold:5,allowSelf:false,ignoredChannelIds:[]});
  if(!feature.enabled||!feature.config.channelId)return;
  if(((feature.config.ignoredChannelIds||[]) as string[]).includes(message.channelId))return;

  const wanted=String(feature.config.emoji||"⭐");
  const got=reaction.emoji.id||reaction.emoji.name||"";
  if(got!==wanted&&reaction.emoji.name!==wanted)return;

  const users=await reaction.users.fetch().catch(()=>null);
  if(!users)return;
  let count=[...users.values()].filter(u=>!u.bot).length;
  const authorId=message.author?.id||"";if(feature.config.allowSelf===false&&authorId)count=[...users.values()].filter(u=>!u.bot&&u.id!==authorId).length;

  const threshold=Math.max(2,Number(feature.config.threshold||5));
  const existing=await one<any>(`SELECT * FROM starboard_posts WHERE guild_id=$1 AND source_message_id=$2`,[message.guildId,message.id]);
  const channel=await message.client.channels.fetch(String(feature.config.channelId)).catch(()=>null);
  if(!channel?.isTextBased())return;

  if(count<threshold){
    if(existing?.starboard_message_id){
      const old=await (channel as TextChannel).messages.fetch(existing.starboard_message_id).catch(()=>null);
      if(old)await old.delete().catch(()=>{});
      await query(`DELETE FROM starboard_posts WHERE guild_id=$1 AND source_message_id=$2`,[message.guildId,message.id]);
    }
    return;
  }

  const embed=brandEmbed(`${wanted} Community favourite • ${count}`,message.content?.slice(0,3000)||"*Attachment or embed*",BRAND.colours.premium)
    .setAuthor({name:message.author?.username||"Member",iconURL:message.author?.displayAvatarURL()})
    .addFields({name:"Source",value:`[Jump to message](${message.url})`});
  const attachment=[...message.attachments.values()].find(a=>a.contentType?.startsWith("image/"));
  if(attachment)embed.setImage(attachment.url);

  if(existing?.starboard_message_id){
    const target=await (channel as TextChannel).messages.fetch(existing.starboard_message_id).catch(()=>null);
    if(target){await target.edit({embeds:[embed]});await query(`UPDATE starboard_posts SET reaction_count=$3,updated_at=now() WHERE guild_id=$1 AND source_message_id=$2`,[message.guildId,message.id,count]);return;}
  }

  const sent=await (channel as TextChannel).send({embeds:[embed]});
  await query(`INSERT INTO starboard_posts(guild_id,source_message_id,source_channel_id,starboard_message_id,reaction_count) VALUES($1,$2,$3,$4,$5)
    ON CONFLICT(guild_id,source_message_id) DO UPDATE SET starboard_message_id=$4,reaction_count=$5,updated_at=now()`,[message.guildId,message.id,message.channelId,sent.id,count]);
}

export async function onCommunityReactionAdd(reaction:MessageReaction|PartialMessageReaction,user:User|PartialUser){
  await syncStarboard(reaction,user).catch(console.error);
}
export async function onCommunityReactionRemove(reaction:MessageReaction|PartialMessageReaction,user:User|PartialUser){
  await syncStarboard(reaction,user).catch(console.error);
}
