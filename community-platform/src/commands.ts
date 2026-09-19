import {
  ChatInputCommandInteraction, Client, EmbedBuilder, PermissionFlagsBits,
  SlashCommandBuilder, TextChannel, ChannelType
} from "discord.js";
import { audit, getFeature, one, query } from "./db.js";
import { brandEmbed, BRAND } from "./brand.js";

export const commandData = [
  new SlashCommandBuilder().setName("tax").setDescription("Calculate EA tax")
    .addIntegerOption(o => o.setName("price").setDescription("Sale price").setRequired(true).setMinValue(1)),
  new SlashCommandBuilder().setName("profit").setDescription("Calculate trade profit")
    .addIntegerOption(o => o.setName("buy").setDescription("Buy price").setRequired(true).setMinValue(1))
    .addIntegerOption(o => o.setName("sell").setDescription("Sell price").setRequired(true).setMinValue(1))
    .addIntegerOption(o => o.setName("quantity").setDescription("Quantity").setMinValue(1)),
  new SlashCommandBuilder().setName("roi").setDescription("Calculate ROI after EA tax")
    .addIntegerOption(o => o.setName("buy").setDescription("Buy price").setRequired(true).setMinValue(1))
    .addIntegerOption(o => o.setName("sell").setDescription("Sell price").setRequired(true).setMinValue(1)),
  new SlashCommandBuilder().setName("breakeven").setDescription("Calculate minimum sale price to break even")
    .addIntegerOption(o => o.setName("buy").setDescription("Buy price").setRequired(true).setMinValue(1)),
  new SlashCommandBuilder().setName("call").setDescription("Post a structured trading call")
    .addStringOption(o => o.setName("player").setDescription("Player/card").setRequired(true).setMaxLength(100))
    .addIntegerOption(o => o.setName("buy").setDescription("Buy price").setRequired(true).setMinValue(1))
    .addIntegerOption(o => o.setName("target").setDescription("Target sale price").setRequired(true).setMinValue(1))
    .addStringOption(o => o.setName("reason").setDescription("Why this trade?").setRequired(true).setMaxLength(500)),
  new SlashCommandBuilder().setName("callclose").setDescription("Close one of your trading calls")
    .addIntegerOption(o => o.setName("id").setDescription("Call ID").setRequired(true))
    .addIntegerOption(o => o.setName("sale").setDescription("Actual sale price").setRequired(true).setMinValue(1)),
  new SlashCommandBuilder().setName("thanks").setDescription("Thank a helpful member")
    .addUserOption(o => o.setName("member").setDescription("Member").setRequired(true))
    .addStringOption(o => o.setName("reason").setDescription("What did they help with?").setMaxLength(200)),
  new SlashCommandBuilder().setName("suggest").setDescription("Make a server suggestion")
    .addStringOption(o => o.setName("suggestion").setDescription("Your suggestion").setRequired(true).setMaxLength(1000)),
  new SlashCommandBuilder().setName("wl").setDescription("Post a W/L vote")
    .addStringOption(o => o.setName("item").setDescription("Player/card/item").setRequired(true).setMaxLength(100))
    .addIntegerOption(o => o.setName("price").setDescription("Price paid").setRequired(true).setMinValue(1))
    .addAttachmentOption(o => o.setName("image").setDescription("Optional screenshot")),
  new SlashCommandBuilder().setName("warn").setDescription("Warn a member")
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName("member").setDescription("Member").setRequired(true))
    .addStringOption(o => o.setName("reason").setDescription("Reason").setRequired(true).setMaxLength(500)),
  new SlashCommandBuilder().setName("history").setDescription("View moderation history")
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName("member").setDescription("Member").setRequired(true)),
  new SlashCommandBuilder().setName("ticket").setDescription("Open a private support/report ticket")
    .addStringOption(o => o.setName("type").setDescription("Ticket type").setRequired(true)
      .addChoices(
        { name: "Support", value: "Support" },
        { name: "Trading", value: "Trading" },
        { name: "Scam report", value: "Scam report" },
        { name: "Appeal", value: "Appeal" },
        { name: "Partnership", value: "Partnership" }
      )),
  new SlashCommandBuilder().setName("ping").setDescription("Check bot latency")
].map(c => c.toJSON());

function money(n: number) { return Math.round(n).toLocaleString("en-GB"); }
function net(sell: number, taxPercent: number) { return Math.floor(sell * (1 - taxPercent / 100)); }

export async function handleCommand(client: Client, i: ChatInputCommandInteraction) {
  if (!i.guildId || !i.guild) return;
  const guildId = i.guildId;

  if (i.commandName === "ping") {
    return i.reply({ content: `🏓 ${client.ws.ping}ms`, ephemeral: true });
  }

  if (["tax","profit","roi","breakeven"].includes(i.commandName)) {
    const feature = await getFeature(guildId, "trading_tools", { taxPercent: 5, ephemeralCalculators: true });
    if (!feature.enabled) return i.reply({ content: "Trading calculators are currently disabled.", ephemeral: true });
    const tax = Number(feature.config.taxPercent || 5);
    const buy = i.options.getInteger("buy") || 0;
    const sell = i.options.getInteger("sell") || i.options.getInteger("price") || 0;
    const qty = i.options.getInteger("quantity") || 1;
    let text = "";
    if (i.commandName === "tax") text = `Sale: **${money(sell)}** • EA tax (${tax}%): **${money(sell - net(sell, tax))}** • Net: **${money(net(sell, tax))}**`;
    if (i.commandName === "profit") text = `Buy: **${money(buy)}** • Sell: **${money(sell)}** • Qty: **${qty}** • Profit after tax: **${money((net(sell,tax)-buy)*qty)}**`;
    if (i.commandName === "roi") text = `ROI after tax: **${(((net(sell,tax)-buy)/buy)*100).toFixed(2)}%**`;
    if (i.commandName === "breakeven") text = `Minimum break-even sale: **${money(Math.ceil(buy/(1-tax/100)))}**`;
    return i.reply({ embeds:[brandEmbed("🧮 Trading calculator",text,BRAND.colours.neutral)], ephemeral: Boolean(feature.config.ephemeralCalculators) });
  }

  if (i.commandName === "thanks") {
    const feature = await getFeature(guildId, "reputation", { dailyLimit: 3 });
    if (!feature.enabled) return i.reply({ content: "Reputation is disabled.", ephemeral: true });
    const member = i.options.getUser("member", true);
    if (member.id === i.user.id || member.bot) return i.reply({ content: "Pick another real member.", ephemeral: true });
    const count = await one<{ count: string }>(
      `SELECT count(*)::text count FROM reputation_events WHERE guild_id=$1 AND giver_id=$2 AND created_at > now()-interval '24 hours'`,
      [guildId, i.user.id]
    );
    if (Number(count?.count || 0) >= Number(feature.config.dailyLimit || 3)) return i.reply({ content: "You've reached today's thanks limit.", ephemeral: true });
    const reason = i.options.getString("reason") || "";
    await query(`INSERT INTO reputation_events(guild_id,giver_id,receiver_id,reason) VALUES($1,$2,$3,$4)`, [guildId,i.user.id,member.id,reason]);
    await query(`INSERT INTO member_stats(guild_id,user_id,thanks_received) VALUES($1,$2,1)
      ON CONFLICT(guild_id,user_id) DO UPDATE SET thanks_received=member_stats.thanks_received+1`, [guildId, member.id]);
    await query(`INSERT INTO member_stats(guild_id,user_id,thanks_given) VALUES($1,$2,1)
      ON CONFLICT(guild_id,user_id) DO UPDATE SET thanks_given=member_stats.thanks_given+1`, [guildId, i.user.id]);
    await audit(guildId, i.user.id, "reputation.thanks", { receiverId: member.id, reason });
    return i.reply(`💚 ${i.user} thanked ${member}${reason ? ` — ${reason}` : ""}`);
  }


  if (i.commandName === "call") {
    const feature = await getFeature(guildId, "trade_calls", { channelId:"", allowedRoleIds:[], autoThread:true });
    if (!feature.enabled) return i.reply({ content:"Trade calls are disabled.", ephemeral:true });
    const member = await i.guild.members.fetch(i.user.id);
    const allowed = (feature.config.allowedRoleIds as string[] || []);
    if (allowed.length && !member.roles.cache.some(r => allowed.includes(r.id))) return i.reply({ content:"You don't have a trader role allowed to post calls.", ephemeral:true });
    const player = i.options.getString("player",true), buy=i.options.getInteger("buy",true), target=i.options.getInteger("target",true), reason=i.options.getString("reason",true);
    const rows = await query<{id:number}>(`INSERT INTO trade_calls(guild_id,user_id,player,buy_price,target_price,reason) VALUES($1,$2,$3,$4,$5,$6) RETURNING id`, [guildId,i.user.id,player,buy,target,reason]);
    const id = rows[0]!.id;
    const embed = brandEmbed(`📈 Trade Call #${id} • ${player}`,reason,BRAND.colours.success)
      .addFields({name:"Buy",value:money(buy),inline:true},{name:"Target",value:money(target),inline:true},{name:"Potential ROI",value:`${(((target*.95-buy)/buy)*100).toFixed(1)}%`,inline:true})
      .setAuthor({name:i.user.username,iconURL:i.user.displayAvatarURL()});
    await i.reply({ embeds:[embed] });
    const msg = await i.fetchReply();
    await query(`UPDATE trade_calls SET discord_message_id=$1 WHERE id=$2`, [msg.id,id]);
    if (feature.config.autoThread && "startThread" in msg) await (msg as any).startThread({name:`Trade #${id} • ${player}`}).catch(()=>{});
    return;
  }

  if (i.commandName === "callclose") {
    const id=i.options.getInteger("id",true), sale=i.options.getInteger("sale",true);
    const call = await one<any>(`SELECT * FROM trade_calls WHERE id=$1 AND guild_id=$2`,[id,guildId]);
    if (!call || (call.user_id !== i.user.id && !i.memberPermissions?.has(PermissionFlagsBits.ModerateMembers))) return i.reply({content:"Call not found or not yours.",ephemeral:true});
    const status = sale >= Number(call.target_price || Infinity) ? "HIT" : sale > Number(call.buy_price) ? "PROFIT" : "MISS";
    await query(`UPDATE trade_calls SET status=$1,result_price=$2,closed_at=now() WHERE id=$3`,[status,sale,id]);
    return i.reply({embeds:[brandEmbed(`Trade #${id} • ${status}`,`Closed at **${money(sale)}** coins.`,status==="MISS"?BRAND.colours.danger:status==="HIT"?BRAND.colours.success:BRAND.colours.warning)]});
  }

  if (i.commandName === "suggest") {
    const feature=await getFeature(guildId,"suggestions",{channelId:"",createThread:true});
    if(!feature.enabled) return i.reply({content:"Suggestions are disabled.",ephemeral:true});
    const body=i.options.getString("suggestion",true);
    const rows=await query<{id:number}>(`INSERT INTO suggestions(guild_id,user_id,body) VALUES($1,$2,$3) RETURNING id`,[guildId,i.user.id,body]);
    const embed=brandEmbed(`💡 Suggestion #${rows[0]!.id}`,body,BRAND.colours.primary).setAuthor({name:i.user.username,iconURL:i.user.displayAvatarURL()});
    const channel = feature.config.channelId ? await client.channels.fetch(String(feature.config.channelId)).catch(()=>null) : i.channel;
    if (channel?.isTextBased()) {
      const msg=await (channel as TextChannel).send({embeds:[embed]});
      await msg.react("👍"); await msg.react("👎");
      if(feature.config.createThread) await msg.startThread({name:`Suggestion #${rows[0]!.id}`}).catch(()=>{});
      await query(`UPDATE suggestions SET discord_message_id=$1 WHERE id=$2`,[msg.id,rows[0]!.id]);
    }
    return i.reply({content:"Suggestion submitted.",ephemeral:true});
  }

  if (i.commandName === "wl") {
    const feature=await getFeature(guildId,"wl_votes",{channelId:""});
    if(!feature.enabled) return i.reply({content:"W/L voting is disabled.",ephemeral:true});
    const item=i.options.getString("item",true), price=i.options.getInteger("price",true), image=i.options.getAttachment("image");
    const embed=brandEmbed(`⚖️ W or L? • ${item}`,`Bought for **${money(price)}** coins`,BRAND.colours.warning).setAuthor({name:i.user.username,iconURL:i.user.displayAvatarURL()});
    if(image?.contentType?.startsWith("image/")) embed.setImage(image.url);
    const channel=feature.config.channelId ? await client.channels.fetch(String(feature.config.channelId)).catch(()=>null) : i.channel;
    if(!channel?.isTextBased()) return i.reply({content:"W/L channel is not configured.",ephemeral:true});
    const msg=await (channel as TextChannel).send({embeds:[embed]});
    for(const r of ["🔥","✅","➖","❌","💀"]) await msg.react(r);
    return i.reply({content:`Posted your W/L vote in ${msg.channel}.`,ephemeral:true});
  }

  if (i.commandName === "warn") {
    const user=i.options.getUser("member",true), reason=i.options.getString("reason",true);
    await query(`INSERT INTO warnings(guild_id,user_id,moderator_id,reason) VALUES($1,$2,$3,$4)`,[guildId,user.id,i.user.id,reason]);
    await audit(guildId,i.user.id,"moderation.warn",{userId:user.id,reason});
    return i.reply({content:`⚠️ ${user} warned: ${reason}`,ephemeral:true});
  }

  if (i.commandName === "history") {
    const user=i.options.getUser("member",true);
    const rows=await query<any>(`SELECT moderator_id,reason,created_at FROM warnings WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC LIMIT 10`,[guildId,user.id]);
    const body=rows.length ? rows.map((r,n)=>`${n+1}. ${new Date(r.created_at).toLocaleDateString("en-GB")} — ${r.reason}`).join("\n") : "No warnings.";
    return i.reply({content:`**Moderation history for ${user.username}**\n${body}`,ephemeral:true});
  }

  if (i.commandName === "ticket") {
    const feature=await getFeature(guildId,"tickets",{categoryId:"",staffRoleIds:[]});
    if(!feature.enabled) return i.reply({content:"Tickets are disabled.",ephemeral:true});
    const type=i.options.getString("type",true);
    const row=(await query<{id:number}>(`INSERT INTO tickets(guild_id,user_id,ticket_type) VALUES($1,$2,$3) RETURNING id`,[guildId,i.user.id,type]))[0]!;
    const overwrites:any[]=[
      {id:i.guild.roles.everyone.id,deny:[PermissionFlagsBits.ViewChannel]},
      {id:i.user.id,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]}
    ];
    for(const roleId of (feature.config.staffRoleIds as string[]||[])) overwrites.push({id:roleId,allow:[PermissionFlagsBits.ViewChannel,PermissionFlagsBits.SendMessages,PermissionFlagsBits.ReadMessageHistory]});
    const channel=await i.guild.channels.create({
      name:`ticket-${row.id}-${i.user.username}`.toLowerCase().replace(/[^a-z0-9-]/g,"").slice(0,90),
      type:ChannelType.GuildText,
      parent:feature.config.categoryId ? String(feature.config.categoryId) : undefined,
      permissionOverwrites:overwrites
    });
    await query(`UPDATE tickets SET channel_id=$1 WHERE id=$2`,[channel.id,row.id]);
    await channel.send({content:`${i.user}`,embeds:[brandEmbed(`🎫 ${type} ticket #${row.id}`,"Describe what you need help with below. A staff member will pick this up.",BRAND.colours.primary)]});
    return i.reply({content:`Ticket created: ${channel}`,ephemeral:true});
  }
}
