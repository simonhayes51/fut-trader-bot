import crypto from "node:crypto";
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, ChatInputCommandInteraction, Client, EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { audit, db, one, query } from "./db.js";
import { awardCurrency, getEconomyProfile, getEconomySettings, levelFromXp, recordEconomyEvent, xpForLevel } from "./economy-core.js";
import { brandEmbed, BRAND, compactNumber, progressBar } from "./brand.js";
import { grantComp, listPlans } from "./billing.js";

export const economyCommandData=[
  new SlashCommandBuilder().setName("profile").setDescription("View your EAFC.Live community profile").addUserOption(o=>o.setName("member").setDescription("Member to view")),
  new SlashCommandBuilder().setName("wallet").setDescription("View your Live Coins balance and recent activity"),
  new SlashCommandBuilder().setName("daily").setDescription("Claim your daily Live Coins and streak reward"),
  new SlashCommandBuilder().setName("quests").setDescription("View your daily and weekly quests"),
  new SlashCommandBuilder().setName("shop").setDescription("Browse the EAFC.Live rewards store"),
  new SlashCommandBuilder().setName("redeem").setDescription("Spend Live Coins on a store reward").addStringOption(o=>o.setName("item").setDescription("Store item key").setRequired(true).setAutocomplete(true)),
  new SlashCommandBuilder().setName("season").setDescription("View the current FC27 community season")
].map(c=>c.toJSON());

function questPeriodKey(cadence:string,seasonId?:number){
  const d=new Date();if(cadence==="daily")return d.toISOString().slice(0,10);
  if(cadence==="weekly"){const x=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate()));const day=x.getUTCDay()||7;x.setUTCDate(x.getUTCDate()+4-day);const y=new Date(Date.UTC(x.getUTCFullYear(),0,1));return `${x.getUTCFullYear()}-W${String(Math.ceil((((x.getTime()-y.getTime())/86400000)+1)/7)).padStart(2,"0")}`;}
  if(cadence==="season")return `season:${seasonId||0}`;return "lifetime";
}

export async function handleEconomyAutocomplete(i:any){
  if(i.commandName!=="redeem"||!i.guildId)return false;
  const q=String(i.options.getFocused()||"").toLowerCase();
  const rows=await query<any>(`SELECT item_key,name,cost_coins FROM store_items WHERE guild_id=$1 AND active=true AND (stock IS NULL OR stock>0) AND (lower(item_key) LIKE $2 OR lower(name) LIKE $2) ORDER BY sort_order,name LIMIT 25`,[i.guildId,`%${q}%`]);
  await i.respond(rows.map(r=>({name:`${r.name} • ${compactNumber(r.cost_coins)} Live Coins`.slice(0,100),value:r.item_key})));return true;
}

async function profileEmbed(guildId:string,user:any){
  const p=await getEconomyProfile(guildId,user.id),xp=Number(p.eco.xp_total||0),level=p.level;
  const next=level>=100?xp:Number(p.nextLevelXp),into=xp-Number(p.levelFloor),span=Math.max(1,next-Number(p.levelFloor));
  const [premium,calls,trades,stats]=await Promise.all([
    one<any>(`SELECT 1 FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND active=true AND (expires_at IS NULL OR expires_at>now())`,[guildId,user.id]),
    one<any>(`SELECT count(*) FILTER(WHERE status<>'LIVE') total,count(*) FILTER(WHERE status IN ('HIT','PROFIT')) wins FROM trade_calls WHERE guild_id=$1 AND user_id=$2`,[guildId,user.id]),
    one<any>(`SELECT count(*) total,COALESCE(sum(profit),0) profit FROM trade_journal WHERE guild_id=$1 AND user_id=$2 AND status='CLOSED'`,[guildId,user.id]),
    one<any>(`SELECT thanks_received,messages FROM member_stats WHERE guild_id=$1 AND user_id=$2`,[guildId,user.id])
  ]);
  const callTotal=Number(calls?.total||0),callWins=Number(calls?.wins||0),thanks=Number(stats?.thanks_received||0),journal=Number(trades?.total||0);
  const accuracy=callTotal?callWins/callTotal:0;
  const rep=Math.min(100,Math.round(Math.min(30,callTotal*3)+Math.min(30,accuracy*30)+Math.min(20,thanks*2)+Math.min(10,journal)+Math.min(10,Number(stats?.messages||0)/100)));
  const repTier=rep>=80?"Elite":rep>=60?"Trusted":rep>=40?"Established":rep>=20?"Contributor":"Newcomer";
  const e=brandEmbed(`${user.username} • Community profile`,undefined,premium?BRAND.colours.premium:BRAND.colours.primary).setThumbnail(user.displayAvatarURL());
  e.addFields(
    {name:`Level ${level}`,value:`${progressBar(into,span)}\n${compactNumber(xp)} XP • #${p.rank} server rank`,inline:false},
    {name:"🪙 Live Coins",value:compactNumber(p.eco.coins_balance||0),inline:true},
    {name:"🔥 Streak",value:`${compactNumber(p.streak.current_streak||0)} days`,inline:true},
    {name:"💎 Access",value:premium?"Premium":"Standard",inline:true},
    {name:"📊 Trader reputation",value:`**${rep}/100 • ${repTier}**\n${callTotal} verified calls • ${callTotal?Math.round(accuracy*100):0}% hit rate • ${thanks} helpful votes`,inline:false}
  );
  if(p.season)e.addFields({name:`🏆 ${p.season.name}`,value:`${compactNumber(p.season.xp_earned||0)} season XP • ends <t:${Math.floor(new Date(p.season.ends_at).getTime()/1000)}:R>`,inline:false});
  if(p.achievements.length)e.addFields({name:"Latest achievements",value:p.achievements.slice(0,6).map((a:any)=>`${a.icon||"🏅"} ${a.name||String(a.achievement_key).replaceAll("_"," ")}`).join(" • "),inline:false});
  return e;
}

async function claimDaily(guildId:string,userId:string){
  const settings=await getEconomySettings(guildId);if(!settings.enabled)throw new Error("Community rewards are currently disabled.");
  const client=await db.connect();
  try{
    await client.query("BEGIN");
    await client.query(`INSERT INTO member_streaks(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[guildId,userId]);
    const s=(await client.query(`SELECT * FROM member_streaks WHERE guild_id=$1 AND user_id=$2 FOR UPDATE`,[guildId,userId])).rows[0];
    const today=new Date().toISOString().slice(0,10);if(s.last_claim_date&&new Date(s.last_claim_date).toISOString().slice(0,10)===today)throw new Error("You've already claimed today's reward.");
    const yesterday=new Date(Date.now()-86400000).toISOString().slice(0,10),last=s.last_claim_date?new Date(s.last_claim_date).toISOString().slice(0,10):null;
    const streak=last===yesterday?Number(s.current_streak||0)+1:1;
    await client.query(`UPDATE member_streaks SET current_streak=$3,longest_streak=GREATEST(longest_streak,$3),last_claim_date=current_date,last_activity_date=current_date,updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[guildId,userId,streak]);
    await client.query("COMMIT");
    const bonus=Math.min(settings.streak_bonus_cap,Math.max(0,(streak-1)*settings.streak_bonus_per_day)),coins=settings.daily_claim_coins+bonus;
    await awardCurrency({guildId,userId,currency:"coins",amount:coins,reason:`Daily reward • ${streak}-day streak`,sourceType:"daily",sourceId:today,idempotencyKey:`daily:${today}:${userId}:coins`});
    await recordEconomyEvent(guildId,userId,"daily_claim",{sourceType:"daily",sourceId:today,idempotencyBase:`dailyquest:${today}:${userId}`});
    return {streak,coins,bonus};
  }catch(e){await client.query("ROLLBACK").catch(()=>{});throw e;}finally{client.release();}
}

async function questRows(guildId:string,userId:string){
  const season=await one<any>(`SELECT id FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[guildId]);
  const defs=await query<any>(`SELECT * FROM quest_definitions WHERE guild_id=$1 AND active=true ORDER BY CASE cadence WHEN 'daily' THEN 1 WHEN 'weekly' THEN 2 WHEN 'season' THEN 3 ELSE 4 END,sort_order,id`,[guildId]);
  const out=[] as any[];for(const q of defs){const key=questPeriodKey(q.cadence,season?.id);const p=await one<any>(`SELECT * FROM member_quest_progress WHERE guild_id=$1 AND user_id=$2 AND quest_id=$3 AND period_key=$4`,[guildId,userId,q.id,key]);out.push({...q,period_key:key,progress:Number(p?.progress||0),rewarded:Boolean(p?.rewarded_at)});}return out;
}

async function redeemItem(client:Client,guildId:string,userId:string,itemKey:string,interactionId:string){
  const dbc=await db.connect();let redemption:any,item:any;
  try{
    await dbc.query("BEGIN");
    item=(await dbc.query(`SELECT * FROM store_items WHERE guild_id=$1 AND lower(item_key)=lower($2) AND active=true FOR UPDATE`,[guildId,itemKey])).rows[0];
    if(!item)throw new Error("That reward isn't available.");if(item.stock!==null&&Number(item.stock)<=0)throw new Error("That reward is sold out.");
    if(item.per_user_limit){const c=Number((await dbc.query(`SELECT count(*) c FROM store_redemptions WHERE guild_id=$1 AND user_id=$2 AND store_item_id=$3 AND status IN ('PENDING','FULFILLED')`,[guildId,userId,item.id])).rows[0]?.c||0);if(c>=Number(item.per_user_limit))throw new Error("You've reached the redemption limit for that reward.");}
    await dbc.query(`INSERT INTO member_economy(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[guildId,userId]);
    const wallet=(await dbc.query(`SELECT coins_balance FROM member_economy WHERE guild_id=$1 AND user_id=$2 FOR UPDATE`,[guildId,userId])).rows[0];
    if(Number(wallet?.coins_balance||0)<Number(item.cost_coins))throw new Error(`You need ${compactNumber(item.cost_coins)} Live Coins for this reward.`);
    const claim=crypto.randomBytes(4).toString("hex").toUpperCase();
    redemption=(await dbc.query(`INSERT INTO store_redemptions(guild_id,user_id,store_item_id,item_key,item_name,cost_coins,claim_code) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *`,[guildId,userId,item.id,item.item_key,item.name,item.cost_coins,claim])).rows[0];
    const led=(await dbc.query(`INSERT INTO economy_ledger(guild_id,user_id,currency,amount,reason,source_type,source_id,idempotency_key) VALUES($1,$2,'coins',$3,$4,'store_redemption',$5,$6) ON CONFLICT(guild_id,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING id`,[guildId,userId,-Number(item.cost_coins),`Store: ${item.name}`,String(redemption.id),`redeem:${interactionId}`])).rows[0];
    if(!led)throw new Error("This redemption has already been processed.");
    await dbc.query(`UPDATE member_economy SET coins_balance=coins_balance-$3,lifetime_coins_spent=lifetime_coins_spent+$3,updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[guildId,userId,Number(item.cost_coins)]);
    if(item.stock!==null)await dbc.query(`UPDATE store_items SET stock=stock-1,updated_at=now() WHERE id=$1`,[item.id]);
    await dbc.query("COMMIT");
  }catch(e){await dbc.query("ROLLBACK");throw e;}finally{dbc.release();}

  try{
    if(item.fulfillment_type==="discord_premium"){
      const plans=await listPlans(guildId,true);const plan=(item.billing_plan_slug?plans.find(p=>p.slug===item.billing_plan_slug):null)||plans[0];if(!plan)throw new Error("Premium plan is not configured.");
      await grantComp(guildId,userId,plan.id,Math.max(1,Number(item.duration_days||30)),"store");
      await query(`UPDATE store_redemptions SET status='FULFILLED',fulfilled_by='system',fulfilled_at=now(),fulfillment_notes=$2,updated_at=now() WHERE id=$1`,[redemption.id,`${item.duration_days||30} days ${plan.name}`]);
      return {...redemption,status:"FULFILLED",automatic:true};
    }
    if(item.fulfillment_type==="role"){
      if(!item.role_id)throw new Error("Reward role is not configured.");const guild=client.guilds.cache.get(guildId),member=guild?await guild.members.fetch(userId):null;if(!member)throw new Error("Member not found in Discord.");await member.roles.add(item.role_id,"EAFC.Live store redemption");
      await query(`UPDATE store_redemptions SET status='FULFILLED',fulfilled_by='system',fulfilled_at=now(),updated_at=now() WHERE id=$1`,[redemption.id]);return {...redemption,status:"FULFILLED",automatic:true};
    }
    if(item.fulfillment_type==="badge"){
      const key=String(item.metadata?.achievement_key||item.item_key);await query(`INSERT INTO achievements(guild_id,user_id,achievement_key) VALUES($1,$2,$3) ON CONFLICT DO NOTHING`,[guildId,userId,key]);await query(`UPDATE store_redemptions SET status='FULFILLED',fulfilled_by='system',fulfilled_at=now(),updated_at=now() WHERE id=$1`,[redemption.id]);return {...redemption,status:"FULFILLED",automatic:true};
    }
    return {...redemption,status:"PENDING",automatic:false};
  }catch(err:any){
    await awardCurrency({guildId,userId,currency:"coins",amount:Number(item.cost_coins),reason:`Refund: ${item.name}`,sourceType:"store_refund",sourceId:String(redemption.id),idempotencyKey:`store-refund:${redemption.id}`}).catch(()=>{});
    await query(`UPDATE store_redemptions SET status='REFUNDED',fulfillment_notes=$2,updated_at=now() WHERE id=$1`,[redemption.id,String(err?.message||err)]);if(item.stock!==null)await query(`UPDATE store_items SET stock=stock+1 WHERE id=$1`,[item.id]);throw err;
  }
}

export async function handleEconomyCommand(client:Client,i:ChatInputCommandInteraction){
  if(!i.guildId||!["profile","wallet","daily","quests","shop","redeem","season"].includes(i.commandName))return false;
  const gid=i.guildId,uid=i.user.id;
  if(i.commandName==="profile"){const u=i.options.getUser("member")||i.user;await i.reply({embeds:[await profileEmbed(gid,u)]});return true;}
  if(i.commandName==="wallet"){const p=await getEconomyProfile(gid,uid),rows=await query<any>(`SELECT * FROM economy_ledger WHERE guild_id=$1 AND user_id=$2 AND currency='coins' ORDER BY created_at DESC LIMIT 8`,[gid,uid]);const e=brandEmbed("🪙 Your Live Coins",`**${compactNumber(p.eco.coins_balance)}** available\n${compactNumber(p.eco.lifetime_coins_earned)} earned • ${compactNumber(p.eco.lifetime_coins_spent)} spent`,BRAND.colours.coins);if(rows.length)e.addFields({name:"Recent activity",value:rows.map(r=>`${Number(r.amount)>0?"+":""}${compactNumber(r.amount)} • ${r.reason}`).join("\n")});await i.reply({embeds:[e],ephemeral:true});return true;}
  if(i.commandName==="daily"){try{const r=await claimDaily(gid,uid),e=brandEmbed("🔥 Daily reward claimed",`**+${compactNumber(r.coins)} Live Coins**\n${r.streak}-day streak${r.bonus?` • ${compactNumber(r.bonus)} streak bonus`:""}`,BRAND.colours.coins);await i.reply({embeds:[e]});}catch(err:any){await i.reply({embeds:[brandEmbed("Daily reward",String(err?.message||err),BRAND.colours.warning)],ephemeral:true});}return true;}
  if(i.commandName==="quests"){const rows=await questRows(gid,uid);const daily=rows.filter(r=>r.cadence==="daily"),weekly=rows.filter(r=>r.cadence==="weekly");const fmt=(r:any)=>`${r.rewarded?"✅":"▫️"} **${r.name}** • ${Math.min(r.progress,r.target)}/${r.target}\n↳ ${r.xp_reward} XP + ${r.coin_reward} 🪙`;const e=brandEmbed("🎯 Quests","Complete useful activity to earn XP and Live Coins.").addFields({name:"Today",value:daily.map(fmt).join("\n")||"No daily quests.",inline:false},{name:"This week",value:weekly.map(fmt).join("\n")||"No weekly quests.",inline:false});await i.reply({embeds:[e],ephemeral:true});return true;}
  if(i.commandName==="shop"){const p=await getEconomyProfile(gid,uid),items=await query<any>(`SELECT * FROM store_items WHERE guild_id=$1 AND active=true AND (stock IS NULL OR stock>0) ORDER BY sort_order,name`,[gid]);const e=brandEmbed("🛍️ EAFC.Live Rewards Store",`Balance: **${compactNumber(p.eco.coins_balance)} 🪙**\nEarn Live Coins by contributing, completing quests and keeping your streak.`,BRAND.colours.coins);for(const x of items.slice(0,12))e.addFields({name:`${x.emoji||"🎁"} ${x.name} • ${compactNumber(x.cost_coins)} 🪙`,value:`${x.description}\nKey: \`${x.item_key}\`${x.stock!==null?` • ${x.stock} left`:""}`,inline:false});const row=new ActionRowBuilder<ButtonBuilder>().addComponents(new ButtonBuilder().setCustomId("economy:shop-refresh").setLabel("Refresh store").setStyle(ButtonStyle.Secondary));await i.reply({embeds:[e],components:[row],ephemeral:true});return true;}
  if(i.commandName==="redeem"){const key=i.options.getString("item",true);await i.deferReply({ephemeral:true});try{const r=await redeemItem(client,gid,uid,key,i.id);const msg=r.status==="FULFILLED"?`**${r.item_name}** is active now.`:`**${r.item_name}** has been queued for fulfilment.\nClaim code: \`${r.claim_code}\``;await i.editReply({embeds:[brandEmbed("✅ Reward redeemed",msg,BRAND.colours.success)]});}catch(err:any){await i.editReply({embeds:[brandEmbed("Couldn't redeem reward",String(err?.message||err),BRAND.colours.danger)]});}return true;}
  if(i.commandName==="season"){const season=await one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]);const top=season?await query<any>(`SELECT user_id,xp_earned,quests_completed FROM season_member_stats WHERE season_id=$1 ORDER BY xp_earned DESC LIMIT 10`,[season.id]):[];const p=await getEconomyProfile(gid,uid);const e=brandEmbed(`🏆 ${season?.name||"FC27 Season"}`,season?`Ends <t:${Math.floor(new Date(season.ends_at).getTime()/1000)}:R>\nYour season XP: **${compactNumber(p.season?.xp_earned||0)}**`:"Season data is being prepared.",BRAND.colours.premium);if(top.length)e.addFields({name:"Leaderboard",value:top.map((r,n)=>`${n+1}. <@${r.user_id}> • **${compactNumber(r.xp_earned)} XP** • ${r.quests_completed} quests`).join("\n")});await i.reply({embeds:[e]});return true;}
  return false;
}

export async function handleEconomyComponent(_client:Client,i:any){
  if(!i.guildId||!i.isButton()||!String(i.customId).startsWith("economy:"))return false;
  if(i.customId==="economy:shop-refresh"){const p=await getEconomyProfile(i.guildId,i.user.id),items=await query<any>(`SELECT * FROM store_items WHERE guild_id=$1 AND active=true AND (stock IS NULL OR stock>0) ORDER BY sort_order,name`,[i.guildId]);const e=brandEmbed("🛍️ EAFC.Live Rewards Store",`Balance: **${compactNumber(p.eco.coins_balance)} 🪙**`,BRAND.colours.coins);for(const x of items.slice(0,12))e.addFields({name:`${x.emoji||"🎁"} ${x.name} • ${compactNumber(x.cost_coins)} 🪙`,value:`${x.description}\nKey: \`${x.item_key}\``,inline:false});await i.update({embeds:[e]});return true;}return false;
}

export async function onEconomyMessage(message:any){
  if(!message.guildId||message.author?.bot||message.deleted||!message.content||String(message.content).trim().length<8)return;
  const settings=await getEconomySettings(message.guildId);if(!settings.enabled)return;
  const client=await db.connect();let xp=0,coins=0;
  try{
    await client.query("BEGIN");
    await client.query(`INSERT INTO economy_cooldowns(guild_id,user_id,cooldown_key,next_at) VALUES($1,$2,'message',now()) ON CONFLICT DO NOTHING`,[message.guildId,message.author.id]);
    const cd=(await client.query(`SELECT * FROM economy_cooldowns WHERE guild_id=$1 AND user_id=$2 AND cooldown_key='message' FOR UPDATE`,[message.guildId,message.author.id])).rows[0];
    if(cd?.next_at&&new Date(cd.next_at).getTime()>Date.now()){await client.query("ROLLBACK");return;}
    await client.query(`UPDATE economy_cooldowns SET next_at=now()+($3||' seconds')::interval WHERE guild_id=$1 AND user_id=$2 AND cooldown_key='message'`,[message.guildId,message.author.id,String(settings.message_cooldown_seconds)]);
    await client.query(`INSERT INTO economy_daily_caps(guild_id,user_id,cap_date) VALUES($1,$2,current_date) ON CONFLICT DO NOTHING`,[message.guildId,message.author.id]);
    const cap=(await client.query(`SELECT * FROM economy_daily_caps WHERE guild_id=$1 AND user_id=$2 AND cap_date=current_date FOR UPDATE`,[message.guildId,message.author.id])).rows[0];
    xp=Math.max(0,Math.min(settings.xp_per_message,settings.daily_message_xp_cap-Number(cap.message_xp||0)));coins=Math.max(0,Math.min(settings.coins_per_message,settings.daily_message_coin_cap-Number(cap.message_coins||0)));
    await client.query(`UPDATE economy_daily_caps SET message_xp=message_xp+$3,message_coins=message_coins+$4,rewarded_messages=rewarded_messages+1 WHERE guild_id=$1 AND user_id=$2 AND cap_date=current_date`,[message.guildId,message.author.id,xp,coins]);
    await client.query("COMMIT");
  }catch(e){await client.query("ROLLBACK").catch(()=>{});throw e;}finally{client.release();}
  if(xp>0)await awardCurrency({guildId:message.guildId,userId:message.author.id,currency:"xp",amount:xp,reason:"Community activity",sourceType:"message",sourceId:message.id,idempotencyKey:`message:${message.id}:xp`});
  if(coins>0)await awardCurrency({guildId:message.guildId,userId:message.author.id,currency:"coins",amount:coins,reason:"Community activity",sourceType:"message",sourceId:message.id,idempotencyKey:`message:${message.id}:coins`});
  await recordEconomyEvent(message.guildId,message.author.id,"message",{sourceType:"message",sourceId:message.id,idempotencyBase:`message-quest:${message.id}`});
}

export async function onEconomyJoin(guildId:string,userId:string){
  await recordEconomyEvent(guildId,userId,"join",{sourceType:"discord_join",sourceId:userId,idempotencyBase:`join:${guildId}:${userId}`});
  const def=await one<any>(`SELECT * FROM achievement_definitions WHERE guild_id=$1 AND achievement_key='welcome_aboard'`,[guildId]);if(def){const inserted=await query<any>(`INSERT INTO achievements(guild_id,user_id,achievement_key) VALUES($1,$2,'welcome_aboard') ON CONFLICT DO NOTHING RETURNING achievement_key`,[guildId,userId]);if(inserted.length){if(Number(def.xp_reward)>0)await awardCurrency({guildId,userId,currency:"xp",amount:Number(def.xp_reward),reason:`Achievement: ${def.name}`,sourceType:"achievement",sourceId:"welcome_aboard",idempotencyKey:`achievement:welcome_aboard:${userId}:xp`});if(Number(def.coin_reward)>0)await awardCurrency({guildId,userId,currency:"coins",amount:Number(def.coin_reward),reason:`Achievement: ${def.name}`,sourceType:"achievement",sourceId:"welcome_aboard",idempotencyKey:`achievement:welcome_aboard:${userId}:coins`});}}
}

export async function runEconomyTick(_client:Client){
  const ended=await query<any>(`SELECT * FROM economy_seasons WHERE active=true AND ends_at<=now() ORDER BY ends_at FOR UPDATE SKIP LOCKED`);
  for(const season of ended){
    const leaders=await query<any>(`SELECT user_id,xp_earned FROM season_member_stats WHERE season_id=$1 ORDER BY xp_earned DESC,user_id LIMIT 10`,[season.id]);
    const rewards=season.rewards||{"1":2000,"2":1000,"3":500};
    for(let n=0;n<leaders.length;n++){
      const amount=Number(rewards[String(n+1)]||0);if(amount<=0)continue;
      await awardCurrency({guildId:season.guild_id,userId:leaders[n].user_id,currency:"coins",amount,reason:`${season.name} • #${n+1} reward`,sourceType:"season_reward",sourceId:String(season.id),idempotencyKey:`season:${season.id}:rank:${n+1}:${leaders[n].user_id}`});
    }
    await query(`UPDATE economy_seasons SET active=false,rewards_paid_at=COALESCE(rewards_paid_at,now()) WHERE id=$1`,[season.id]);
  }
  const guilds=await query<any>(`SELECT guild_id FROM guild_settings`);for(const g of guilds){const active=await one<any>(`SELECT id FROM economy_seasons WHERE guild_id=$1 AND active=true AND ends_at>now()`,[g.guild_id]);if(!active){const n=Number((await one<any>(`SELECT count(*) c FROM economy_seasons WHERE guild_id=$1`,[g.guild_id]))?.c||0)+1;await query(`INSERT INTO economy_seasons(guild_id,name,starts_at,ends_at) VALUES($1,$2,now(),now()+interval '30 days')`,[g.guild_id,`FC27 Season ${n}`]);}}
  const due=await query<any>(`UPDATE economy_event_queue SET status='PROCESSING',attempts=attempts+1 WHERE id IN (SELECT id FROM economy_event_queue WHERE status IN ('PENDING','FAILED') AND available_at<=now() ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED) RETURNING *`);
  for(const e of due){try{await recordEconomyEvent(e.guild_id,e.user_id,e.event_type,{quantity:e.quantity,sourceType:e.source_type,sourceId:e.source_id,idempotencyBase:`queue:${e.id}`,metadata:e.metadata});await query(`UPDATE economy_event_queue SET status='DONE',processed_at=now(),last_error=NULL WHERE id=$1`,[e.id]);}catch(err:any){await query(`UPDATE economy_event_queue SET status='FAILED',last_error=$2,available_at=now()+interval '5 minutes' WHERE id=$1`,[e.id,String(err?.message||err).slice(0,1000)]);}}
}

export async function refundStoreRedemption(id:number,actorId:string){
  const r=await one<any>(`SELECT r.*,i.stock FROM store_redemptions r LEFT JOIN store_items i ON i.id=r.store_item_id WHERE r.id=$1`,[id]);if(!r||!['PENDING','FAILED','REJECTED'].includes(r.status))throw new Error("Redemption cannot be refunded.");
  await awardCurrency({guildId:r.guild_id,userId:r.user_id,currency:"coins",amount:Number(r.cost_coins),reason:`Refund: ${r.item_name}`,sourceType:"store_refund",sourceId:String(id),idempotencyKey:`store-refund:${id}`});
  await query(`UPDATE store_redemptions SET status='REFUNDED',fulfilled_by=$2,fulfilled_at=now(),updated_at=now() WHERE id=$1`,[id,actorId]);if(r.stock!==null)await query(`UPDATE store_items SET stock=stock+1 WHERE id=$1`,[r.store_item_id]);await audit(r.guild_id,actorId,"economy.redemption.refund",{id,userId:r.user_id,cost:r.cost_coins});
}
