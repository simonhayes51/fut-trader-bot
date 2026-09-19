import { Router } from "express";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, one, query } from "./db.js";
import { modules } from "./modules.js";
import { levelFromXp } from "./economy-core.js";

export const controlRouter=Router();
const auth=(req:any,res:any,next:any)=>req.session?.user?next():res.redirect("/login");
controlRouter.use(auth);

async function guildUi(){
  const guild=client.guilds.cache.get(config.targetGuildId);
  if(!guild)return {guild:null,channels:[],roles:[],members:[]};
  const fetched=await guild.members.fetch().catch(()=>guild.members.cache);
  const botHighest=guild.members.me?.roles.highest.position??0;
  return {
    guild,
    channels:[...guild.channels.cache.values()].filter(c=>c.isTextBased()||c.type===4).map(c=>({id:c.id,name:c.name,type:c.type})).sort((a,b)=>a.name.localeCompare(b.name)),
    roles:[...guild.roles.cache.values()].filter(r=>r.id!==guild.id&&!r.managed&&r.position<botHighest).map(r=>({id:r.id,name:r.name})).sort((a,b)=>a.name.localeCompare(b.name)),
    members:[...fetched.values()].filter(m=>!m.user.bot).map(m=>({id:m.id,name:m.displayName,username:m.user.username,joinedAt:m.joinedAt}))
  };
}

controlRouter.get("/control",async(req:any,res)=>{
  const gid=config.targetGuildId;
  const [ui,metrics,recent,kudos,season,features]=await Promise.all([
    guildUi(),
    one<any>(`SELECT
      (SELECT count(*) FROM member_stats WHERE guild_id=$1) tracked_members,
      (SELECT count(*) FROM member_stats WHERE guild_id=$1 AND last_message_at>now()-interval '7 days') active_7d,
      (SELECT count(*) FROM reputation_events WHERE guild_id=$1 AND created_at>now()-interval '7 days') kudos_7d,
      (SELECT count(*) FROM tickets WHERE guild_id=$1 AND status='OPEN') open_tickets,
      (SELECT count(*) FROM warnings WHERE guild_id=$1 AND created_at>now()-interval '7 days') warnings_7d,
      (SELECT count(*) FROM giveaways WHERE guild_id=$1 AND status='LIVE') live_giveaways,
      (SELECT count(*) FROM scheduled_messages WHERE guild_id=$1 AND enabled=true) schedules,
      (SELECT count(*) FROM social_feeds WHERE guild_id=$1 AND enabled=true) feeds,
      (SELECT count(DISTINCT discord_user_id) FROM entitlements WHERE guild_id=$1 AND active=true AND (expires_at IS NULL OR expires_at>now())) premium_members,
      (SELECT COALESCE(sum(coins_balance),0) FROM member_economy WHERE guild_id=$1) coins_circulating`,[gid]),
    query<any>(`SELECT action,details,created_at FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 8`,[gid]),
    query<any>(`SELECT user_id,thanks_received FROM member_stats WHERE guild_id=$1 AND thanks_received>0 ORDER BY thanks_received DESC LIMIT 5`,[gid]),
    one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]),
    query<any>(`SELECT feature_key,enabled FROM feature_settings WHERE guild_id=$1`,[gid])
  ]);
  const names=new Map<string,string>(ui.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  res.render("control-home",{user:req.session.user,...ui,metrics:metrics||{},recent,kudos:kudos.map(k=>({...k,name:names.get(k.user_id)||k.user_id})),season,features:new Map<string,boolean>(features.map(f=>[String(f.feature_key),Boolean(f.enabled)] as [string,boolean]))});
});

controlRouter.get("/control/members",async(req:any,res)=>{
  const gid=config.targetGuildId,q=String(req.query.q||"").trim().toLowerCase(),ui=await guildUi();
  let members=ui.members.filter(m=>!q||m.name.toLowerCase().includes(q)||m.username.toLowerCase().includes(q)).slice(0,150);
  const ids=members.map(m=>m.id);
  const [stats,economy,streaks,premium]=await Promise.all([
    ids.length?query<any>(`SELECT * FROM member_stats WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT * FROM member_economy WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT * FROM member_streaks WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT discord_user_id FROM entitlements WHERE guild_id=$1 AND active=true AND (expires_at IS NULL OR expires_at>now()) AND discord_user_id=ANY($2::text[])`,[gid,ids]):[]
  ]);
  const premiumSet=new Set(premium.map(p=>p.discord_user_id));
  members=members.map(m=>{const e=economy.find(x=>x.user_id===m.id),st=stats.find(x=>x.user_id===m.id),sk=streaks.find(x=>x.user_id===m.id);return {...m,xp:Number(e?.xp_total||0),coins:Number(e?.coins_balance||0),level:levelFromXp(Number(e?.xp_total||0)),kudos:Number(st?.thanks_received||0),messages:Number(st?.messages||0),streak:Number(sk?.current_streak||0),premium:premiumSet.has(m.id),lastActive:st?.last_message_at||null};});
  res.render("control-members",{user:req.session.user,...ui,members,q});
});

controlRouter.get("/control/engagement",async(req:any,res)=>{
  const gid=config.targetGuildId;
  const [ui,settings,season,quests,store,topKudos,achievements]=await Promise.all([
    guildUi(),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[gid,["reputation","levels","giveaways","starboard"]]),
    one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]),
    query<any>(`SELECT * FROM quest_definitions WHERE guild_id=$1 AND active=true ORDER BY cadence,sort_order`,[gid]),
    query<any>(`SELECT * FROM store_items WHERE guild_id=$1 ORDER BY sort_order,name`,[gid]),
    query<any>(`SELECT user_id,thanks_received FROM member_stats WHERE guild_id=$1 ORDER BY thanks_received DESC LIMIT 10`,[gid]),
    one<any>(`SELECT count(*) total FROM achievements WHERE guild_id=$1`,[gid])
  ]);
  const names=new Map<string,string>(ui.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  res.render("control-engagement",{user:req.session.user,...ui,settings:new Map<string,any>(settings.map(s=>[String(s.feature_key),s] as [string,any])),season,quests,store,topKudos:topKudos.map(k=>({...k,name:names.get(k.user_id)||k.user_id})),achievements:Number(achievements?.total||0)});
});

controlRouter.get("/control/community",async(req:any,res)=>{
  const gid=config.targetGuildId;
  const [ui,responses,stickies,settings]=await Promise.all([
    guildUi(),
    query<any>(`SELECT * FROM custom_responses WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[gid]),
    query<any>(`SELECT * FROM sticky_messages WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[gid]),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[gid,["welcome","role_menus","suggestions","tickets","starboard"]])
  ]);
  res.render("control-community",{user:req.session.user,...ui,responses,stickies,settings:new Map<string,any>(settings.map(s=>[String(s.feature_key),s] as [string,any])),saved:req.query.saved==="1"});
});

controlRouter.post("/control/community/responses",async(req:any,res)=>{
  const trigger=String(req.body.trigger||"").trim(),response=String(req.body.response||"").trim(),mode=String(req.body.matchMode||"contains");
  if(!trigger||!response)return res.redirect("/control/community");
  const channels=Array.isArray(req.body.channels)?req.body.channels:req.body.channels?[req.body.channels]:[];
  await query(`INSERT INTO custom_responses(guild_id,trigger,response,match_mode,channel_ids,cooldown_seconds) VALUES($1,$2,$3,$4,$5,$6)`,[config.targetGuildId,trigger,response,["exact","contains","starts_with"].includes(mode)?mode:"contains",channels,Math.max(5,Number(req.body.cooldownSeconds||30))]);
  await audit(config.targetGuildId,req.session.user.id,"community.response.create",{trigger,mode});res.redirect("/control/community?saved=1");
});
controlRouter.post("/control/community/responses/:id/toggle",async(req:any,res)=>{await query(`UPDATE custom_responses SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/control/community");});
controlRouter.post("/control/community/responses/:id/delete",async(req:any,res)=>{await query(`DELETE FROM custom_responses WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/control/community");});

controlRouter.post("/control/community/stickies",async(req:any,res)=>{
  const channelId=String(req.body.channelId||""),content=String(req.body.content||"").trim();if(!channelId||!content)return res.redirect("/control/community");
  await query(`INSERT INTO sticky_messages(guild_id,channel_id,content,min_interval_seconds,enabled) VALUES($1,$2,$3,$4,true)
    ON CONFLICT(guild_id,channel_id) DO UPDATE SET content=$3,min_interval_seconds=$4,enabled=true,updated_at=now()`,[config.targetGuildId,channelId,content,Math.max(60,Number(req.body.intervalSeconds||300))]);
  await audit(config.targetGuildId,req.session.user.id,"community.sticky.save",{channelId});res.redirect("/control/community?saved=1");
});
controlRouter.post("/control/community/stickies/:id/toggle",async(req:any,res)=>{await query(`UPDATE sticky_messages SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/control/community");});
controlRouter.post("/control/community/stickies/:id/delete",async(req:any,res)=>{await query(`DELETE FROM sticky_messages WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/control/community");});

controlRouter.get("/control/automation",async(req:any,res)=>{
  const [ui,scheduled,feeds,giveaways]=await Promise.all([
    guildUi(),
    query<any>(`SELECT * FROM scheduled_messages WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[config.targetGuildId]),
    query<any>(`SELECT * FROM social_feeds WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[config.targetGuildId]),
    query<any>(`SELECT * FROM giveaways WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 20`,[config.targetGuildId])
  ]);
  res.render("control-automation",{user:req.session.user,...ui,scheduled,feeds,giveaways});
});

controlRouter.get("/control/safety",async(req:any,res)=>{
  const [ui,warnings,reports,tickets,settings]=await Promise.all([
    guildUi(),
    query<any>(`SELECT * FROM warnings WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[config.targetGuildId]),
    query<any>(`SELECT * FROM scam_cases WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[config.targetGuildId]),
    query<any>(`SELECT * FROM tickets WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[config.targetGuildId]),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[config.targetGuildId,["automod","mod_tools","join_security","tickets"]])
  ]);
  res.render("control-safety",{user:req.session.user,...ui,warnings,reports,tickets,settings:new Map<string,any>(settings.map(s=>[String(s.feature_key),s] as [string,any]))});
});

controlRouter.get("/control/settings",async(req:any,res)=>{
  const [ui,rows]=await Promise.all([guildUi(),query<any>(`SELECT feature_key,enabled,config,updated_at FROM feature_settings WHERE guild_id=$1`,[config.targetGuildId])]);
  const map=new Map<string,any>(rows.map(r=>[String(r.feature_key),r] as [string,any]));
  res.render("control-settings",{user:req.session.user,...ui,modules:modules.map(m=>({...m,state:map.get(m.key)}))});
});
