import { db, one, query } from "./db.js";

export type EconomySettings={
  enabled:boolean;xp_per_message:number;coins_per_message:number;message_cooldown_seconds:number;
  daily_message_xp_cap:number;daily_message_coin_cap:number;daily_claim_coins:number;streak_bonus_per_day:number;
  streak_bonus_cap:number;helpful_xp:number;helpful_coins:number;referral_xp:number;referral_coins:number;
  trade_xp:number;trade_coins:number;join_xp:number;join_coins:number;
};

const defaults:EconomySettings={enabled:true,xp_per_message:4,coins_per_message:1,message_cooldown_seconds:60,daily_message_xp_cap:200,daily_message_coin_cap:40,daily_claim_coins:25,streak_bonus_per_day:5,streak_bonus_cap:50,helpful_xp:30,helpful_coins:15,referral_xp:250,referral_coins:500,trade_xp:20,trade_coins:5,join_xp:25,join_coins:25};

export function levelFromXp(xp:number){return Math.max(1,Math.min(100,Math.floor(Math.sqrt(Math.max(0,xp)/250))+1));}
export function xpForLevel(level:number){const l=Math.max(1,level);return 250*(l-1)*(l-1);}

export async function getEconomySettings(guildId:string):Promise<EconomySettings>{
  const row=await one<any>(`SELECT * FROM economy_settings WHERE guild_id=$1`,[guildId]);
  if(!row){await query(`INSERT INTO economy_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING`,[guildId]);return defaults;}
  return {...defaults,...row};
}

async function currentSeason(client:any,guildId:string){
  let s=(await client.query(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true AND starts_at<=now() AND ends_at>now() ORDER BY starts_at DESC LIMIT 1`,[guildId])).rows[0];
  if(!s){
    const count=Number((await client.query(`SELECT count(*) c FROM economy_seasons WHERE guild_id=$1`,[guildId])).rows[0]?.c||0)+1;
    s=(await client.query(`INSERT INTO economy_seasons(guild_id,name,starts_at,ends_at) VALUES($1,$2,now(),now()+interval '30 days') RETURNING *`,[guildId,`FC27 Season ${count}`])).rows[0];
  }
  return s;
}

async function ensureMember(client:any,guildId:string,userId:string){
  await client.query(`INSERT INTO member_economy(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[guildId,userId]);
  await client.query(`INSERT INTO member_stats(guild_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING`,[guildId,userId]);
}

async function applyLedger(client:any,input:{guildId:string;userId:string;currency:"xp"|"coins";amount:number;reason:string;sourceType?:string;sourceId?:string;idempotencyKey?:string;metadata?:any}){
  await ensureMember(client,input.guildId,input.userId);
  if(!Number.isFinite(input.amount)||input.amount===0)return false;
  if(input.currency==="coins"&&input.amount<0){
    const wallet=(await client.query(`SELECT coins_balance FROM member_economy WHERE guild_id=$1 AND user_id=$2 FOR UPDATE`,[input.guildId,input.userId])).rows[0];
    if(Number(wallet?.coins_balance||0)<Math.abs(input.amount))throw new Error("Not enough Live Coins.");
  }
  const inserted=(await client.query(`INSERT INTO economy_ledger(guild_id,user_id,currency,amount,reason,source_type,source_id,idempotency_key,metadata)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
    ON CONFLICT(guild_id,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING id`,[
      input.guildId,input.userId,input.currency,Math.trunc(input.amount),input.reason,input.sourceType||null,input.sourceId||null,input.idempotencyKey||null,JSON.stringify(input.metadata||{})
    ])).rows[0];
  if(!inserted)return false;
  if(input.currency==="xp"){
    await client.query(`UPDATE member_economy SET xp_total=GREATEST(0,xp_total+$3),updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[input.guildId,input.userId,Math.trunc(input.amount)]);
    await client.query(`UPDATE member_stats SET xp=GREATEST(0,xp+$3) WHERE guild_id=$1 AND user_id=$2`,[input.guildId,input.userId,Math.trunc(input.amount)]);
  }else{
    await client.query(`UPDATE member_economy SET coins_balance=coins_balance+$3,lifetime_coins_earned=lifetime_coins_earned+CASE WHEN $3>0 THEN $3 ELSE 0 END,lifetime_coins_spent=lifetime_coins_spent+CASE WHEN $3<0 THEN -$3 ELSE 0 END,updated_at=now() WHERE guild_id=$1 AND user_id=$2`,[input.guildId,input.userId,Math.trunc(input.amount)]);
  }
  const season=await currentSeason(client,input.guildId);
  await client.query(`INSERT INTO season_member_stats(season_id,guild_id,user_id,xp_earned,coins_earned) VALUES($1,$2,$3,$4,$5)
    ON CONFLICT(season_id,user_id) DO UPDATE SET xp_earned=season_member_stats.xp_earned+$4,coins_earned=season_member_stats.coins_earned+$5`,[
      season.id,input.guildId,input.userId,input.currency==="xp"&&input.amount>0?Math.trunc(input.amount):0,input.currency==="coins"&&input.amount>0?Math.trunc(input.amount):0
    ]);
  return true;
}

export async function awardCurrency(input:{guildId:string;userId:string;currency:"xp"|"coins";amount:number;reason:string;sourceType?:string;sourceId?:string;idempotencyKey?:string;metadata?:any}){
  const client=await db.connect();try{await client.query("BEGIN");const changed=await applyLedger(client,input);await client.query("COMMIT");return changed;}catch(e){await client.query("ROLLBACK");throw e;}finally{client.release();}
}

function periodKey(cadence:string,seasonId?:number){
  const d=new Date();
  if(cadence==="daily")return d.toISOString().slice(0,10);
  if(cadence==="weekly"){
    const x=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate()));
    const day=x.getUTCDay()||7;x.setUTCDate(x.getUTCDate()+4-day);
    const yearStart=new Date(Date.UTC(x.getUTCFullYear(),0,1));
    const week=Math.ceil((((x.getTime()-yearStart.getTime())/86400000)+1)/7);
    return `${x.getUTCFullYear()}-W${String(week).padStart(2,"0")}`;
  }
  if(cadence==="season")return `season:${seasonId||0}`;
  return "lifetime";
}

async function progressQuests(client:any,guildId:string,userId:string,eventType:string,quantity:number){
  const season=await currentSeason(client,guildId);
  const quests=(await client.query(`SELECT * FROM quest_definitions WHERE guild_id=$1 AND active=true AND event_type=$2 ORDER BY sort_order,id`,[guildId,eventType])).rows;
  let completed=0;
  let premium:boolean|undefined;
  for(const q of quests){
    if(q.premium_only){
      if(premium===undefined){
        premium=Boolean((await client.query(`SELECT 1 FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND active=true AND (expires_at IS NULL OR expires_at>now()) LIMIT 1`,[guildId,userId])).rows[0]);
      }
      if(!premium)continue;
    }
    const key=periodKey(q.cadence,Number(season.id));
    const row=(await client.query(`INSERT INTO member_quest_progress(guild_id,user_id,quest_id,period_key,progress)
      VALUES($1,$2,$3,$4,$5)
      ON CONFLICT(guild_id,user_id,quest_id,period_key) DO UPDATE SET progress=LEAST($6,member_quest_progress.progress+$5),updated_at=now()
      RETURNING *`,[guildId,userId,q.id,key,Math.max(1,quantity),Number(q.target)])).rows[0];
    if(Number(row.progress)>=Number(q.target)&&!row.rewarded_at){
      const lock=(await client.query(`UPDATE member_quest_progress SET completed_at=COALESCE(completed_at,now()),rewarded_at=now() WHERE guild_id=$1 AND user_id=$2 AND quest_id=$3 AND period_key=$4 AND rewarded_at IS NULL RETURNING rewarded_at`,[guildId,userId,q.id,key])).rows[0];
      if(lock){
        if(Number(q.xp_reward)>0)await applyLedger(client,{guildId,userId,currency:"xp",amount:Number(q.xp_reward),reason:`Quest complete: ${q.name}`,sourceType:"quest",sourceId:String(q.id),idempotencyKey:`quest:${q.id}:${key}:${userId}:xp`});
        if(Number(q.coin_reward)>0)await applyLedger(client,{guildId,userId,currency:"coins",amount:Number(q.coin_reward),reason:`Quest complete: ${q.name}`,sourceType:"quest",sourceId:String(q.id),idempotencyKey:`quest:${q.id}:${key}:${userId}:coins`});
        await client.query(`UPDATE season_member_stats SET quests_completed=quests_completed+1 WHERE season_id=$1 AND user_id=$2`,[season.id,userId]);
        completed++;
      }
    }
  }
  return completed;
}

async function awardAchievement(client:any,guildId:string,userId:string,key:string){
  const def=(await client.query(`SELECT * FROM achievement_definitions WHERE guild_id=$1 AND achievement_key=$2 AND active=true`,[guildId,key])).rows[0];
  if(!def)return false;
  const inserted=(await client.query(`INSERT INTO achievements(guild_id,user_id,achievement_key) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING achievement_key`,[guildId,userId,key])).rows[0];
  if(!inserted)return false;
  if(Number(def.xp_reward)>0)await applyLedger(client,{guildId,userId,currency:"xp",amount:Number(def.xp_reward),reason:`Achievement: ${def.name}`,sourceType:"achievement",sourceId:key,idempotencyKey:`achievement:${key}:${userId}:xp`});
  if(Number(def.coin_reward)>0)await applyLedger(client,{guildId,userId,currency:"coins",amount:Number(def.coin_reward),reason:`Achievement: ${def.name}`,sourceType:"achievement",sourceId:key,idempotencyKey:`achievement:${key}:${userId}:coins`});
  return true;
}

async function evaluateAchievements(client:any,guildId:string,userId:string){
  const [eco,streak,stats,trades]=await Promise.all([
    client.query(`SELECT * FROM member_economy WHERE guild_id=$1 AND user_id=$2`,[guildId,userId]),
    client.query(`SELECT * FROM member_streaks WHERE guild_id=$1 AND user_id=$2`,[guildId,userId]),
    client.query(`SELECT * FROM member_stats WHERE guild_id=$1 AND user_id=$2`,[guildId,userId]),
    client.query(`SELECT count(*) total FROM trade_journal WHERE guild_id=$1 AND user_id=$2 AND status='CLOSED'`,[guildId,userId])
  ]);
  const e=eco.rows[0]||{},s=streak.rows[0]||{},m=stats.rows[0]||{},t=Number(trades.rows[0]?.total||0),level=levelFromXp(Number(e.xp_total||0));
  const keys:string[]=[];
  if(level>=5)keys.push("level_5");if(level>=10)keys.push("level_10");if(level>=25)keys.push("level_25");
  if(Number(s.current_streak||0)>=7)keys.push("streak_7");if(Number(s.current_streak||0)>=30)keys.push("streak_30");
  if(Number(m.thanks_received||0)>=10)keys.push("helpful_10");if(t>=10)keys.push("trader_10");
  for(const key of keys)await awardAchievement(client,guildId,userId,key);
}

export async function recordEconomyEvent(guildId:string,userId:string,eventType:string,options:{quantity?:number;sourceType?:string;sourceId?:string;idempotencyBase?:string;metadata?:any}={}){
  const settings=await getEconomySettings(guildId);if(!settings.enabled)return {awarded:false,completed:0};
  const qty=Math.max(1,Number(options.quantity||1));
  const rewards:{xp:number;coins:number}={xp:0,coins:0};
  if(eventType==="helpful_received"){rewards.xp=settings.helpful_xp;rewards.coins=settings.helpful_coins;}
  if(eventType==="trade_logged"){rewards.xp=settings.trade_xp;rewards.coins=settings.trade_coins;}
  if(eventType==="referral_conversion"){rewards.xp=settings.referral_xp;rewards.coins=settings.referral_coins;}
  if(eventType==="join"){rewards.xp=settings.join_xp;rewards.coins=settings.join_coins;}
  if(eventType==="investment_join"){rewards.xp=5;rewards.coins=2;}
  const client=await db.connect();
  try{
    await client.query("BEGIN");await ensureMember(client,guildId,userId);
    const base=options.idempotencyBase||`${eventType}:${options.sourceType||"event"}:${options.sourceId||Date.now()}:${userId}`;
    let changed=false;
    if(rewards.xp>0)changed=(await applyLedger(client,{guildId,userId,currency:"xp",amount:rewards.xp*qty,reason:eventType.replaceAll("_"," "),sourceType:options.sourceType||eventType,sourceId:options.sourceId,idempotencyKey:`${base}:xp`,metadata:options.metadata}))||changed;
    if(rewards.coins>0)changed=(await applyLedger(client,{guildId,userId,currency:"coins",amount:rewards.coins*qty,reason:eventType.replaceAll("_"," "),sourceType:options.sourceType||eventType,sourceId:options.sourceId,idempotencyKey:`${base}:coins`,metadata:options.metadata}))||changed;
    const season=await currentSeason(client,guildId);
    if(eventType==="helpful_received"){
      await client.query(`UPDATE season_member_stats SET helpful_actions=helpful_actions+$3 WHERE season_id=$1 AND user_id=$2`,[season.id,userId,qty]);
    }
    if(eventType==="trade_logged"){
      await client.query(`UPDATE season_member_stats SET trades_logged=trades_logged+$3 WHERE season_id=$1 AND user_id=$2`,[season.id,userId,qty]);
    }
    const completed=await progressQuests(client,guildId,userId,eventType,qty);
    await evaluateAchievements(client,guildId,userId);
    await client.query("COMMIT");return {awarded:changed,completed};
  }catch(e){await client.query("ROLLBACK");throw e;}finally{client.release();}
}

export async function rewardReferralConversion(guildId:string,referralCode:string,convertedUserId:string,sourceId:string){
  const ref=await one<any>(`SELECT * FROM referral_codes WHERE guild_id=$1 AND lower(code)=lower($2) AND active=true`,[guildId,referralCode]);
  if(!ref?.owner_discord_user_id||ref.owner_discord_user_id===convertedUserId)return false;
  await recordEconomyEvent(guildId,ref.owner_discord_user_id,"referral_conversion",{sourceType:"stripe_checkout",sourceId,idempotencyBase:`referral:${sourceId}:${ref.owner_discord_user_id}`,metadata:{referralCode,convertedUserId}});
  return true;
}

export async function getEconomyProfile(guildId:string,userId:string){
  const [eco,streak,rank,achievements,season]=await Promise.all([
    one<any>(`SELECT * FROM member_economy WHERE guild_id=$1 AND user_id=$2`,[guildId,userId]),
    one<any>(`SELECT * FROM member_streaks WHERE guild_id=$1 AND user_id=$2`,[guildId,userId]),
    one<any>(`SELECT 1+count(*) rank FROM member_economy WHERE guild_id=$1 AND xp_total>(SELECT COALESCE(xp_total,0) FROM member_economy WHERE guild_id=$1 AND user_id=$2)`,[guildId,userId]),
    query<any>(`SELECT a.achievement_key,a.awarded_at,d.name,d.icon FROM achievements a LEFT JOIN achievement_definitions d ON d.guild_id=a.guild_id AND d.achievement_key=a.achievement_key WHERE a.guild_id=$1 AND a.user_id=$2 ORDER BY a.awarded_at DESC LIMIT 8`,[guildId,userId]),
    one<any>(`SELECT s.id,s.name,s.ends_at,COALESCE(m.xp_earned,0) xp_earned FROM economy_seasons s LEFT JOIN season_member_stats m ON m.season_id=s.id AND m.user_id=$2 WHERE s.guild_id=$1 AND s.active=true ORDER BY s.starts_at DESC LIMIT 1`,[guildId,userId])
  ]);
  const xp=Number(eco?.xp_total||0),level=levelFromXp(xp),floor=xpForLevel(level),next=xpForLevel(Math.min(100,level+1));
  return {eco:eco||{xp_total:0,coins_balance:0,lifetime_coins_earned:0,lifetime_coins_spent:0},streak:streak||{current_streak:0,longest_streak:0},rank:Number(rank?.rank||1),achievements,season,level,levelFloor:floor,nextLevelXp:next};
}
