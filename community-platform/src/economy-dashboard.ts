import { Router } from "express";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, one, query } from "./db.js";
import { awardCurrency } from "./economy-core.js";
import { refundStoreRedemption, runEconomyTick } from "./economy.js";

export const economyRouter=Router();
const auth=(req:any,res:any,next:any)=>req.session?.user?next():res.redirect("/login");
economyRouter.use(auth);

async function guildUi(){
  const g=client.guilds.cache.get(config.targetGuildId);if(!g)return {roles:[],members:[]};
  const members=await g.members.fetch().catch(()=>g.members.cache),botHighest=g.members.me?.roles.highest.position??0;
  return {
    roles:[...g.roles.cache.values()].filter(r=>r.id!==g.id&&!r.managed&&r.position<botHighest).sort((a,b)=>b.position-a.position).map(r=>({id:r.id,name:r.name})),
    members:[...members.values()].filter(m=>!m.user.bot).sort((a,b)=>a.displayName.localeCompare(b.displayName)).map(m=>({id:m.id,name:m.displayName,username:m.user.username}))
  };
}

function int(v:any,min=0,max=1_000_000){const n=Math.trunc(Number(v||0));return Number.isFinite(n)?Math.max(min,Math.min(max,n)):min;}

export async function renderEconomyDashboard(req:any,res:any){
  const gid=config.targetGuildId;
  const [settings,metrics,top,quests,items,redemptions,ledger,seasons,queue,ui]=await Promise.all([
    one<any>(`SELECT * FROM economy_settings WHERE guild_id=$1`,[gid]),
    one<any>(`SELECT
      (SELECT count(*) FROM member_economy WHERE guild_id=$1) members,
      (SELECT COALESCE(sum(coins_balance),0) FROM member_economy WHERE guild_id=$1) circulating,
      (SELECT COALESCE(sum(lifetime_coins_earned),0) FROM member_economy WHERE guild_id=$1) earned,
      (SELECT count(*) FROM store_redemptions WHERE guild_id=$1 AND status='PENDING') pending,
      (SELECT count(*) FROM store_redemptions WHERE guild_id=$1 AND status='FULFILLED') fulfilled,
      (SELECT count(*) FROM member_quest_progress WHERE guild_id=$1 AND rewarded_at IS NOT NULL) quests_completed`,[gid]),
    query<any>(`SELECT e.*,s.current_streak FROM member_economy e LEFT JOIN member_streaks s ON s.guild_id=e.guild_id AND s.user_id=e.user_id WHERE e.guild_id=$1 ORDER BY e.xp_total DESC LIMIT 12`,[gid]),
    query<any>(`SELECT * FROM quest_definitions WHERE guild_id=$1 ORDER BY CASE cadence WHEN 'daily' THEN 1 WHEN 'weekly' THEN 2 WHEN 'season' THEN 3 ELSE 4 END,sort_order,id`,[gid]),
    query<any>(`SELECT * FROM store_items WHERE guild_id=$1 ORDER BY sort_order,name`,[gid]),
    query<any>(`SELECT * FROM store_redemptions WHERE guild_id=$1 ORDER BY CASE status WHEN 'PENDING' THEN 0 ELSE 1 END,created_at DESC LIMIT 100`,[gid]),
    query<any>(`SELECT * FROM economy_ledger WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 80`,[gid]),
    query<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 ORDER BY starts_at DESC LIMIT 12`,[gid]),
    one<any>(`SELECT count(*) FILTER(WHERE status IN ('PENDING','FAILED')) waiting,count(*) FILTER(WHERE status='FAILED') failed FROM economy_event_queue WHERE guild_id=$1`,[gid]),
    guildUi()
  ]);
  res.render("economy",{user:req.session.user,settings:settings||{},metrics:metrics||{},top,quests,items,redemptions,ledger,seasons,queue:queue||{},...ui,saved:req.query.saved==="1",error:req.query.error?String(req.query.error):""});
}

economyRouter.get("/economy",renderEconomyDashboard);

economyRouter.post("/economy/settings",async(req:any,res)=>{
  const gid=config.targetGuildId;
  await query(`INSERT INTO economy_settings(guild_id,enabled,xp_per_message,coins_per_message,message_cooldown_seconds,daily_message_xp_cap,daily_message_coin_cap,daily_claim_coins,streak_bonus_per_day,streak_bonus_cap,helpful_xp,helpful_coins,referral_xp,referral_coins,trade_xp,trade_coins,join_xp,join_coins,updated_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,now())
    ON CONFLICT(guild_id) DO UPDATE SET enabled=$2,xp_per_message=$3,coins_per_message=$4,message_cooldown_seconds=$5,daily_message_xp_cap=$6,daily_message_coin_cap=$7,daily_claim_coins=$8,streak_bonus_per_day=$9,streak_bonus_cap=$10,helpful_xp=$11,helpful_coins=$12,referral_xp=$13,referral_coins=$14,trade_xp=$15,trade_coins=$16,join_xp=$17,join_coins=$18,updated_at=now()`,[
      gid,req.body.enabled==="on",int(req.body.xp_per_message,0,1000),int(req.body.coins_per_message,0,1000),int(req.body.message_cooldown_seconds,10,3600),int(req.body.daily_message_xp_cap,0,100000),int(req.body.daily_message_coin_cap,0,100000),int(req.body.daily_claim_coins,0,100000),int(req.body.streak_bonus_per_day,0,100000),int(req.body.streak_bonus_cap,0,100000),int(req.body.helpful_xp,0,100000),int(req.body.helpful_coins,0,100000),int(req.body.referral_xp,0,100000),int(req.body.referral_coins,0,100000),int(req.body.trade_xp,0,100000),int(req.body.trade_coins,0,100000),int(req.body.join_xp,0,100000),int(req.body.join_coins,0,100000)
    ]);
  await audit(gid,req.session.user.id,"economy.settings.update",{});res.redirect("/economy?saved=1");
});

economyRouter.post("/economy/store",async(req:any,res)=>{
  const gid=config.targetGuildId,key=String(req.body.item_key||"").trim().toLowerCase().replace(/[^a-z0-9_-]+/g,"-").replace(/^-+|-+$/g,"");if(!key||!req.body.name)return res.redirect("/economy?error=Store+item+needs+a+key+and+name");
  const type=String(req.body.fulfillment_type||"custom");if(!["discord_premium","eafc_live","role","badge","custom"].includes(type))return res.redirect("/economy?error=Invalid+fulfilment+type");
  await query(`INSERT INTO store_items(guild_id,item_key,name,description,emoji,cost_coins,active,stock,per_user_limit,fulfillment_type,duration_days,role_id,billing_plan_slug,sort_order,updated_at)
    VALUES($1,$2,$3,$4,$5,$6,true,$7,$8,$9,$10,$11,$12,$13,now())
    ON CONFLICT(guild_id,item_key) DO UPDATE SET name=$3,description=$4,emoji=$5,cost_coins=$6,stock=$7,per_user_limit=$8,fulfillment_type=$9,duration_days=$10,role_id=$11,billing_plan_slug=$12,sort_order=$13,updated_at=now()`,[
      gid,key,String(req.body.name).trim(),String(req.body.description||"").trim(),String(req.body.emoji||"🎁").trim().slice(0,16),int(req.body.cost_coins,0,10_000_000),req.body.stock===""||req.body.stock===undefined?null:int(req.body.stock,0,1_000_000),req.body.per_user_limit===""||req.body.per_user_limit===undefined?null:int(req.body.per_user_limit,1,10_000),type,req.body.duration_days?int(req.body.duration_days,1,3650):null,req.body.role_id||null,String(req.body.billing_plan_slug||"").trim()||null,int(req.body.sort_order,0,10000)
    ]);
  await audit(gid,req.session.user.id,"economy.store.save",{key,type});res.redirect("/economy?saved=1");
});

economyRouter.post("/economy/store/:id/toggle",async(req:any,res)=>{await query(`UPDATE store_items SET active=NOT active,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);await audit(config.targetGuildId,req.session.user.id,"economy.store.toggle",{id:req.params.id});res.redirect("/economy");});

economyRouter.post("/economy/quests",async(req:any,res)=>{
  const gid=config.targetGuildId,key=String(req.body.quest_key||"").trim().toLowerCase().replace(/[^a-z0-9_-]+/g,"-").replace(/^-+|-+$/g,"");const cadence=String(req.body.cadence||"daily");if(!key||!req.body.name||!["daily","weekly","season","lifetime"].includes(cadence))return res.redirect("/economy?error=Invalid+quest");
  await query(`INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,premium_only,active,sort_order,updated_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,true,$11,now())
    ON CONFLICT(guild_id,quest_key) DO UPDATE SET name=$3,description=$4,cadence=$5,event_type=$6,target=$7,xp_reward=$8,coin_reward=$9,premium_only=$10,sort_order=$11,updated_at=now()`,[
      gid,key,String(req.body.name).trim(),String(req.body.description||"").trim(),cadence,String(req.body.event_type||"message").trim(),int(req.body.target,1,1_000_000),int(req.body.xp_reward,0,1_000_000),int(req.body.coin_reward,0,1_000_000),req.body.premium_only==="on",int(req.body.sort_order,0,10000)
    ]);
  await audit(gid,req.session.user.id,"economy.quest.save",{key,cadence});res.redirect("/economy?saved=1");
});

economyRouter.post("/economy/quests/:id/toggle",async(req:any,res)=>{await query(`UPDATE quest_definitions SET active=NOT active,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/economy");});

economyRouter.post("/economy/grant",async(req:any,res)=>{
  const gid=config.targetGuildId,userId=String(req.body.user_id||"").trim(),currency=String(req.body.currency||"coins") as "coins"|"xp",amount=Math.trunc(Number(req.body.amount||0)),reason=String(req.body.reason||"Admin adjustment").trim();if(!userId||!['coins','xp'].includes(currency)||!Number.isFinite(amount)||amount===0)return res.redirect("/economy?error=Invalid+adjustment");
  try{await awardCurrency({guildId:gid,userId,currency,amount,reason,sourceType:"admin",sourceId:req.session.user.id,idempotencyKey:`admin:${Date.now()}:${req.session.user.id}:${userId}:${currency}`});await audit(gid,req.session.user.id,"economy.admin.grant",{userId,currency,amount,reason});res.redirect("/economy?saved=1");}catch(err:any){res.redirect(`/economy?error=${encodeURIComponent(err?.message||"Adjustment failed")}`);}
});

economyRouter.post("/economy/redemptions/:id/fulfill",async(req:any,res)=>{
  const row=await one<any>(`SELECT * FROM store_redemptions WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);if(!row||row.status!=="PENDING")return res.redirect("/economy?error=Redemption+is+not+pending");
  await query(`UPDATE store_redemptions SET status='FULFILLED',fulfilled_by=$2,fulfilled_at=now(),fulfillment_notes=$3,updated_at=now() WHERE id=$1`,[req.params.id,req.session.user.id,String(req.body.notes||"Fulfilled manually")]);await audit(config.targetGuildId,req.session.user.id,"economy.redemption.fulfill",{id:req.params.id,userId:row.user_id});res.redirect("/economy?saved=1");
});

economyRouter.post("/economy/redemptions/:id/refund",async(req:any,res)=>{try{await refundStoreRedemption(Number(req.params.id),req.session.user.id);res.redirect("/economy?saved=1");}catch(err:any){res.redirect(`/economy?error=${encodeURIComponent(err?.message||"Refund failed")}`);}});

economyRouter.post("/economy/season",async(req:any,res)=>{
  const gid=config.targetGuildId,name=String(req.body.name||"").trim()||"FC27 Season",days=int(req.body.days,1,365);
  const rewards={"1":int(req.body.first_reward,0,10_000_000),"2":int(req.body.second_reward,0,10_000_000),"3":int(req.body.third_reward,0,10_000_000)};
  const current=await one<any>(`SELECT id,name FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]);
  if(current){await query(`UPDATE economy_seasons SET ends_at=now() WHERE id=$1`,[current.id]);await runEconomyTick(client);}
  const next=await one<any>(`SELECT id FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]);
  if(next)await query(`UPDATE economy_seasons SET name=$2,starts_at=now(),ends_at=now()+($3||' days')::interval,rewards=$4::jsonb WHERE id=$1`,[next.id,name,String(days),JSON.stringify(rewards)]);
  else await query(`INSERT INTO economy_seasons(guild_id,name,starts_at,ends_at,rewards) VALUES($1,$2,now(),now()+($3||' days')::interval,$4::jsonb)`,[gid,name,String(days),JSON.stringify(rewards)]);
  await audit(gid,req.session.user.id,"economy.season.start",{name,days,rewards,closedSeasonId:current?.id||null});res.redirect("/economy?saved=1");
});
