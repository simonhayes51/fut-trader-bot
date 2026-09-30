import {
  ActionRowBuilder, ButtonBuilder, ButtonStyle,
  ChatInputCommandInteraction, Client, PermissionFlagsBits,
  SlashCommandBuilder, TextChannel, ChannelType
} from "discord.js";
import { audit, getFeature, one, query } from "./db.js";
import { clearGuildBrandCache, guildEmbed, guildSystemEmbed, BRAND } from "./brand.js";
import { recordEconomyEvent } from "./economy-core.js";

export const commandData=[
  new SlashCommandBuilder().setName("kudos").setDescription("Give kudos to a member")
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true))
    .addStringOption(o=>o.setName("type").setDescription("What are you recognising?").setRequired(true).addChoices(
      {name:"Good trade / call",value:"Good trade"},
      {name:"Helpful answer",value:"Helpful"},
      {name:"Great contribution",value:"Contribution"},
      {name:"Community support",value:"Community"}
    ))
    .addStringOption(o=>o.setName("reason").setDescription("Optional note").setMaxLength(200)),
  new SlashCommandBuilder().setName("suggest").setDescription("Make a server suggestion")
    .addStringOption(o=>o.setName("suggestion").setDescription("Your suggestion").setRequired(true).setMaxLength(1000)),
  new SlashCommandBuilder().setName("warn").setDescription("Warn a member")
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true))
    .addStringOption(o=>o.setName("reason").setDescription("Reason").setRequired(true).setMaxLength(500)),
  new SlashCommandBuilder().setName("history").setDescription("View moderation history")
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o=>o.setName("member").setDescription("Member").setRequired(true)),
  new SlashCommandBuilder().setName("ticket").setDescription("Open a private support ticket")
    .addStringOption(o=>o.setName("type").setDescription("Ticket type").setRequired(true).addChoices(
      {name:"Support",value:"Support"},
      {name:"Report",value:"Report"},
      {name:"Appeal",value:"Appeal"},
      {name:"Partnership",value:"Partnership"},
      {name:"Other",value:"Other"}
    )),
  new SlashCommandBuilder().setName("serverbrand").setDescription("Customise this server's bot branding")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o=>o.setName("name").setDescription("Brand name shown in embeds").setMaxLength(80))
    .addStringOption(o=>o.setName("logo_url").setDescription("Logo URL shown as embed thumbnail").setMaxLength(500))
    .addStringOption(o=>o.setName("banner_url").setDescription("Header/banner image URL").setMaxLength(500))
    .addStringOption(o=>o.setName("footer").setDescription("Embed footer text").setMaxLength(120))
    .addStringOption(o=>o.setName("primary_colour").setDescription("Primary colour, e.g. #22d3ee").setMaxLength(7))
    .addStringOption(o=>o.setName("premium_colour").setDescription("Premium colour, e.g. #8b5cf6").setMaxLength(7)),
  new SlashCommandBuilder().setName("announce").setDescription("Post an announcement as the bot in this channel")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addStringOption(o=>o.setName("message").setDescription("Announcement text").setRequired(true).setMaxLength(2000))
    .addRoleOption(o=>o.setName("tag").setDescription("Optional role to tag")),
  new SlashCommandBuilder().setName("post").setDescription("Post a message as the bot in this channel")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addStringOption(o=>o.setName("message").setDescription("Message text").setRequired(true).setMaxLength(2000))
    .addRoleOption(o=>o.setName("tag").setDescription("Optional role to tag")),
  new SlashCommandBuilder().setName("tradetip").setDescription("Post a tracked trader tip")
    .addStringOption(o=>o.setName("player").setDescription("Player/card name").setRequired(true).setMaxLength(100))
    .addIntegerOption(o=>o.setName("buy_price").setDescription("Suggested buy price").setRequired(true).setMinValue(1))
    .addIntegerOption(o=>o.setName("target_price").setDescription("Suggested sell/target price").setMinValue(1))
    .addStringOption(o=>o.setName("platform").setDescription("Platform").addChoices(
      {name:"Console",value:"Console"},
      {name:"PC",value:"PC"},
      {name:"All platforms",value:"All"}
    ))
    .addStringOption(o=>o.setName("sell_time").setDescription("When to sell").setMaxLength(120))
    .addStringOption(o=>o.setName("reason").setDescription("Reason or notes").setMaxLength(800))
    .addStringOption(o=>o.setName("image_url").setDescription("Optional image URL").setMaxLength(500)),
  new SlashCommandBuilder().setName("ping").setDescription("Check bot latency")
].map(c=>c.toJSON());

async function giveKudos(guildId:string,giverId:string,receiverId:string,reason:string,dailyLimit:number){
  if(giverId===receiverId)throw new Error("You can't give kudos to yourself.");
  const count=await one<{count:string}>(`SELECT count(*)::text count FROM reputation_events WHERE guild_id=$1 AND giver_id=$2 AND created_at>now()-interval '24 hours'`,[guildId,giverId]);
  if(Number(count?.count||0)>=dailyLimit)throw new Error("You've reached today's kudos limit.");
  const repeat=await one<any>(`SELECT 1 FROM reputation_events WHERE guild_id=$1 AND giver_id=$2 AND receiver_id=$3 AND created_at>now()-interval '12 hours' LIMIT 1`,[guildId,giverId,receiverId]);
  if(repeat)throw new Error("You've already given that member kudos recently. Spread it around.");
  const pair=await one<any>(`SELECT count(*) c FROM reputation_events WHERE guild_id=$1 AND ((giver_id=$2 AND receiver_id=$3) OR (giver_id=$3 AND receiver_id=$2)) AND created_at>now()-interval '7 days'`,[guildId,giverId,receiverId]);
  if(Number(pair?.c||0)>=6)throw new Error("Kudos between the same two members are temporarily capped to prevent farming.");
  const parts=String(reason).split(": "),category=parts[0]||"Community",comment=parts.slice(1).join(": ")||null;
  await query(`INSERT INTO reputation_events(guild_id,giver_id,receiver_id,reason,category,comment) VALUES($1,$2,$3,$4,$5,$6)`,[guildId,giverId,receiverId,reason,category,comment]);
  await query(`INSERT INTO member_stats(guild_id,user_id,thanks_received) VALUES($1,$2,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET thanks_received=member_stats.thanks_received+1`,[guildId,receiverId]);
  await query(`INSERT INTO member_stats(guild_id,user_id,thanks_given) VALUES($1,$2,1) ON CONFLICT(guild_id,user_id) DO UPDATE SET thanks_given=member_stats.thanks_given+1`,[guildId,giverId]);
}

const trackerLabels:Record<string,string>={bought:"Bought",watching:"Watching",passed:"Passed",sold:"Sold"};

function trackerButtons(callId:number|string){
  return [
    new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder().setCustomId(`tradetip:bought:${callId}`).setLabel("I bought this").setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId(`tradetip:watching:${callId}`).setLabel("Watching").setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId(`tradetip:passed:${callId}`).setLabel("Passed").setStyle(ButtonStyle.Secondary),
      new ButtonBuilder().setCustomId(`tradetip:sold:${callId}`).setLabel("Sold").setStyle(ButtonStyle.Danger),
      new ButtonBuilder().setCustomId(`tradetip:view:${callId}`).setLabel("View trackers").setStyle(ButtonStyle.Secondary)
    )
  ];
}

async function tradeTipCounts(guildId:string,callId:number|string){
  const rows=await query<any>(`SELECT status,count(*)::int count FROM trade_tip_tracking WHERE guild_id=$1 AND trade_call_id=$2 GROUP BY status`,[guildId,callId]);
  const counts:Record<string,number>={bought:0,watching:0,passed:0,sold:0};
  for(const row of rows)if(row.status in counts)counts[row.status]=Number(row.count||0);
  return counts;
}

function trackingSummary(counts:Record<string,number>){
  return `**Bought:** ${counts.bought||0} | **Watching:** ${counts.watching||0} | **Passed:** ${counts.passed||0} | **Sold:** ${counts.sold||0}`;
}

async function refreshTradeTipMessage(client:Client,guildId:string,callId:number|string){
  const call=await one<any>(`SELECT * FROM trade_calls WHERE guild_id=$1 AND id=$2`,[guildId,callId]);
  if(!call?.discord_message_id||!call?.metadata?.channel_id)return;
  const channel=await client.channels.fetch(String(call.metadata.channel_id)).catch(()=>null);
  if(!channel?.isTextBased())return;
  const message=await (channel as TextChannel).messages.fetch(String(call.discord_message_id)).catch(()=>null);
  if(!message?.embeds?.length)return;
  const embed=message.embeds[0]!.toJSON() as any;
  const counts=await tradeTipCounts(guildId,callId);
  const fields=(embed.fields||[]).filter((field:any)=>field.name!=="Tracking");
  fields.push({name:"Tracking",value:trackingSummary(counts),inline:false});
  await message.edit({embeds:[{...embed,fields}],components:trackerButtons(callId)}).catch(()=>{});
}

export async function handleTradeTipComponent(client:Client,i:any){
  if(!i.guildId||!i.isButton?.()||!String(i.customId||"").startsWith("tradetip:"))return false;
  const [,action,rawId]=String(i.customId).split(":");
  const callId=Number(rawId||0);
  if(!callId){await i.reply({content:"That trade tip is no longer tracked.",ephemeral:true});return true;}
  const call=await one<any>(`SELECT * FROM trade_calls WHERE guild_id=$1 AND id=$2`,[i.guildId,callId]);
  if(!call){await i.reply({content:"That trade tip is no longer tracked.",ephemeral:true});return true;}

  if(action==="view"){
    const isOwner=String(call.user_id)===String(i.user.id);
    const canManage=Boolean(i.memberPermissions?.has?.(PermissionFlagsBits.ManageMessages));
    if(!isOwner&&!canManage){
      const counts=await tradeTipCounts(i.guildId,callId);
      await i.reply({content:trackingSummary(counts),ephemeral:true});
      return true;
    }
    const rows=await query<any>(`SELECT status,user_id,updated_at FROM trade_tip_tracking WHERE guild_id=$1 AND trade_call_id=$2 ORDER BY status,updated_at`,[i.guildId,callId]);
    const body=Object.entries(trackerLabels).map(([key,label])=>{
      const users=rows.filter(r=>r.status===key).map(r=>`<@${r.user_id}>`);
      const visible=users.slice(0,25).join(", ");
      const extra=users.length>25?` (+${users.length-25} more)`:"";
      return `**${label} (${users.length})**\n${visible||"Nobody yet."}${extra}`;
    }).join("\n\n");
    await i.reply({embeds:[await guildEmbed(i.guildId,`Trackers: ${call.player}`,body,BRAND.colours.primary)],ephemeral:true});
    return true;
  }

  const actionKey=String(action||"");
  if(!(actionKey in trackerLabels))return false;
  await query(`INSERT INTO trade_tip_tracking(guild_id,trade_call_id,user_id,status,updated_at) VALUES($1,$2,$3,$4,now())
    ON CONFLICT(guild_id,trade_call_id,user_id) DO UPDATE SET status=$4,updated_at=now()`,[i.guildId,callId,i.user.id,actionKey]);
  await refreshTradeTipMessage(client,i.guildId,callId);
  await i.reply({content:`Logged you as **${trackerLabels[actionKey]}** for this tip.`,ephemeral:true});
  return true;
}

export async function handleCommand(client:Client,i:ChatInputCommandInteraction){
  if(!i.guildId||!i.guild)return;
  const guildId=i.guildId;

  if(i.commandName==="ping")return i.reply({content:`🏓 ${client.ws.ping}ms`,ephemeral:true});

  if(i.commandName==="announce"||i.commandName==="post"){
    if(!i.channel?.isTextBased())return i.reply({content:"Use this in the channel you want the bot to post in.",ephemeral:true});
    const message=i.options.getString("message",true).trim();
    if(!message)return i.reply({content:"Add a message to post.",ephemeral:true});
    const tag=i.options.getRole("tag");
    const content=tag?`${tag}\n${message}`:message;
    const sent=await (i.channel as TextChannel).send({
      content,
      allowedMentions:{parse:[],roles:tag?[tag.id]:[],users:[]}
    });
    await audit(guildId,i.user.id,"announcement.post",{command:i.commandName,channelId:i.channelId,messageId:sent.id,tagRoleId:tag?.id||null});
    return i.reply({content:`Posted in ${i.channel}.`,ephemeral:true});
  }

  if(i.commandName==="tradetip"){
    if(!i.channel?.isTextBased())return i.reply({content:"Use this in the channel you want the tip posted in.",ephemeral:true});
    const player=i.options.getString("player",true).trim();
    const buyPrice=i.options.getInteger("buy_price",true);
    const targetPrice=i.options.getInteger("target_price");
    const platform=i.options.getString("platform")||"All";
    const sellTime=i.options.getString("sell_time")||"Not specified";
    const reason=i.options.getString("reason")||"No extra notes.";
    const imageUrl=i.options.getString("image_url");
    const rows=await query<any>(`INSERT INTO trade_calls(guild_id,user_id,player,buy_price,target_price,reason,metadata) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb) RETURNING *`,[
      guildId,i.user.id,player,buyPrice,targetPrice,reason,JSON.stringify({channel_id:i.channelId,platform,sell_time:sellTime,image_url:imageUrl||null})
    ]);
    const call=rows[0]!;
    const embed=(await guildEmbed(guildId,`Trade Tip: ${player}`,`Posted by ${i.user}\n\nAll trades are at your own risk.`,BRAND.colours.success))
      .addFields(
        {name:"Buy price",value:`${buyPrice.toLocaleString("en-GB")} coins`,inline:true},
        {name:"Target",value:targetPrice?`${targetPrice.toLocaleString("en-GB")} coins`:"Not set",inline:true},
        {name:"Platform",value:platform,inline:true},
        {name:"Sell time",value:sellTime,inline:true},
        {name:"Reason",value:reason,inline:false},
        {name:"Tracking",value:trackingSummary({bought:0,watching:0,passed:0,sold:0}),inline:false}
      )
      .setFooter({text:`Tip ID: ${call.id}`});
    if(imageUrl&&/^https?:\/\//i.test(imageUrl))embed.setImage(imageUrl);
    const msg=await (i.channel as TextChannel).send({embeds:[embed],components:trackerButtons(call.id)});
    await query(`UPDATE trade_calls SET discord_message_id=$1,metadata=metadata||$2::jsonb WHERE id=$3 AND guild_id=$4`,[
      msg.id,JSON.stringify({message_url:msg.url}),call.id,guildId
    ]);
    await query(`INSERT INTO server_metrics_daily(guild_id,metric_date,trade_calls) VALUES($1,current_date,1) ON CONFLICT(guild_id,metric_date) DO UPDATE SET trade_calls=server_metrics_daily.trade_calls+1`,[guildId]).catch(()=>{});
    await audit(guildId,i.user.id,"trade_tip.post",{id:call.id,player,channelId:i.channelId});
    return i.reply({content:`Trade tip posted in ${i.channel}.`,ephemeral:true});
  }

  if(i.commandName==="kudos"){
    const feature=await getFeature(guildId,"reputation",{dailyLimit:5});
    if(!feature.enabled)return i.reply({content:"Kudos are currently disabled.",ephemeral:true});
    const member=i.options.getUser("member",true);
    if(member.bot)return i.reply({content:"Pick a real member.",ephemeral:true});
    const type=i.options.getString("type",true),note=i.options.getString("reason")||"";
    const reason=note?`${type}: ${note}`:type;
    try{
      await giveKudos(guildId,i.user.id,member.id,reason,Number(feature.config.dailyLimit||5));
      await recordEconomyEvent(guildId,i.user.id,"kudos_given",{sourceType:"kudos",sourceId:`${i.id}:${member.id}`,idempotencyBase:`kudos-given:${i.id}:${i.user.id}`});
      await audit(guildId,i.user.id,"reputation.kudos",{receiverId:member.id,type,note});
      return i.reply({embeds:[await guildEmbed(guildId,"👏 Kudos given",`${i.user} recognised ${member} for **${type.toLowerCase()}**${note?`\n“${note}”`:""}`,BRAND.colours.success)]});
    }catch(err:any){return i.reply({content:String(err?.message||err),ephemeral:true});}
  }

  if(i.commandName==="suggest"){
    const feature=await getFeature(guildId,"suggestions",{channelId:"",createThread:true});
    if(!feature.enabled)return i.reply({content:"Suggestions are disabled.",ephemeral:true});
    const body=i.options.getString("suggestion",true);
    const rows=await query<{id:number}>(`INSERT INTO suggestions(guild_id,user_id,body) VALUES($1,$2,$3) RETURNING id`,[guildId,i.user.id,body]);
    const embed=(await guildEmbed(guildId,`💡 Suggestion #${rows[0]!.id}`,body,BRAND.colours.primary)).setAuthor({name:i.user.username,iconURL:i.user.displayAvatarURL()});
    const channel=feature.config.channelId?await client.channels.fetch(String(feature.config.channelId)).catch(()=>null):i.channel;
    if(channel?.isTextBased()){
      const msg=await (channel as TextChannel).send({embeds:[embed]});
      await msg.react("👍");await msg.react("👎");
      if(feature.config.createThread)await msg.startThread({name:`Suggestion #${rows[0]!.id}`}).catch(()=>{});
      await query(`UPDATE suggestions SET discord_message_id=$1 WHERE id=$2`,[msg.id,rows[0]!.id]);
    }
    return i.reply({content:"Suggestion submitted.",ephemeral:true});
  }

  if(i.commandName==="warn"){
    const user=i.options.getUser("member",true),reason=i.options.getString("reason",true);
    await query(`INSERT INTO warnings(guild_id,user_id,moderator_id,reason) VALUES($1,$2,$3,$4)`,[guildId,user.id,i.user.id,reason]);
    await audit(guildId,i.user.id,"moderation.warn",{userId:user.id,reason});
    return i.reply({content:`⚠️ ${user} warned: ${reason}`,ephemeral:true});
  }

  if(i.commandName==="history"){
    const user=i.options.getUser("member",true);
    const rows=await query<any>(`SELECT moderator_id,reason,created_at FROM warnings WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC LIMIT 10`,[guildId,user.id]);
    const body=rows.length?rows.map((r,n)=>`${n+1}. ${new Date(r.created_at).toLocaleDateString("en-GB")} — ${r.reason}`).join("\n"):"No warnings.";
    return i.reply({content:`**Moderation history for ${user.username}**\n${body}`,ephemeral:true});
  }

  if(i.commandName==="ticket"){
    const feature=await getFeature(guildId,"tickets",{categoryId:"",staffRoleIds:[]});
    if(!feature.enabled)return i.reply({content:"Tickets are disabled.",ephemeral:true});
    const type=i.options.getString("type",true);
    const row=(await query<{id:number}>(`INSERT INTO tickets(guild_id,user_id,ticket_type) VALUES($1,$2,$3) RETURNING id`,[guildId,i.user.id,type]))[0]!;
    const overwrites:any[]=[
      {id:i.guild.roles.everyone.id,deny:[PermissionFlagsBits.ViewChannel]},
      {id:i.user.id,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]}
    ];
    for(const roleId of (feature.config.staffRoleIds as string[]||[]))overwrites.push({id:roleId,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]});
    const channel=await i.guild.channels.create({
      name:`ticket-${row.id}-${i.user.username}`.toLowerCase().replace(/[^a-z0-9-]/g,"").slice(0,90),
      type:ChannelType.GuildText,
      parent:feature.config.categoryId?String(feature.config.categoryId):undefined,
      permissionOverwrites:overwrites
    });
    await query(`UPDATE tickets SET channel_id=$1 WHERE id=$2`,[channel.id,row.id]);
    await channel.send({content:`${i.user}`,embeds:[await guildSystemEmbed(guildId,`🎫 ${type} ticket #${row.id}`,"Describe what you need help with below. A staff member will pick this up.",BRAND.colours.primary)]});
    return i.reply({content:`Ticket created: ${channel}`,ephemeral:true});
  }

  if(i.commandName==="serverbrand"){
    const row=await one<any>(`SELECT settings FROM guild_settings WHERE guild_id=$1`,[guildId]);
    const existing=row?.settings?.brand||{};
    const next={
      ...existing,
      ...(i.options.getString("name")!==null?{name:i.options.getString("name")}:{}),
      ...(i.options.getString("logo_url")!==null?{logoUrl:i.options.getString("logo_url")}:{}),
      ...(i.options.getString("banner_url")!==null?{bannerUrl:i.options.getString("banner_url")}:{}),
      ...(i.options.getString("footer")!==null?{footerText:i.options.getString("footer")}:{}),
      ...(i.options.getString("primary_colour")!==null?{primaryColour:i.options.getString("primary_colour")}:{}),
      ...(i.options.getString("premium_colour")!==null?{premiumColour:i.options.getString("premium_colour")}:{})
    };
    await query(`INSERT INTO guild_settings(guild_id,guild_name,settings,updated_at) VALUES($1,$2,jsonb_build_object('brand',$3::jsonb),now())
      ON CONFLICT(guild_id) DO UPDATE SET guild_name=$2,settings=jsonb_set(COALESCE(guild_settings.settings,'{}'::jsonb),'{brand}',$3::jsonb,true),updated_at=now()`,[guildId,i.guild.name,JSON.stringify(next)]);
    clearGuildBrandCache(guildId);
    await audit(guildId,i.user.id,"brand.update.command",{brand:next});
    return i.reply({embeds:[await guildEmbed(guildId,"Branding updated","Future premium, ticket and system embeds will use this server's branding.",undefined,{banner:true})],ephemeral:true});
  }
}
