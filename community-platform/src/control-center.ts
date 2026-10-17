import { Router } from "express";
import { client } from "./bot.js";
import { selectedGuildId, guildUi } from "./dashboard-context.js";
import { audit, one, query } from "./db.js";
import { moduleSetupGaps, modules } from "./modules.js";
import { levelFromXp } from "./economy-core.js";
import { createWebhookSecret } from "./social.js";
import { config } from "./config.js";

export const controlRouter=Router();
const auth=(req:any,res:any,next:any)=>req.session?.user?next():res.redirect("/login");
controlRouter.use(auth);

function featureNeedsSetup(key:string,cfg:any={}) {
  if(key==="welcome")return !cfg.channelId;
  if(key==="role_menus")return !cfg.channelId||!Array.isArray(cfg.groups)||!cfg.groups.some((g:any)=>g.name&&Array.isArray(g.roleIds)&&g.roleIds.length);
  if(key==="suggestions"||key==="starboard")return !cfg.channelId;
  if(key==="tickets"){
    const panels=Array.isArray(cfg.panels)?cfg.panels:[];
    const panelReady=panels.some((p:any)=>p.enabled!==false&&p.panelChannelId&&p.categoryId&&Array.isArray(p.staffRoleIds)&&p.staffRoleIds.length);
    const legacyReady=cfg.panelChannelId&&cfg.categoryId&&Array.isArray(cfg.staffRoleIds)&&cfg.staffRoleIds.length;
    return !panelReady&&!legacyReady;
  }
  if(key==="mod_tools")return !Array.isArray(cfg.staffRoleIds)||!cfg.staffRoleIds.length||!cfg.modLogChannelId;
  if(key==="join_security")return !cfg.alertChannelId;
  return false;
}

controlRouter.get("/control",async(req:any,res)=>{
  const gid=selectedGuildId(req);
  const [ui,metrics,recent,kudos,season,features,widgets]=await Promise.all([
    guildUi(req),
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
      (SELECT COALESCE(sum(coins_balance),0) FROM member_economy WHERE guild_id=$1) coins_circulating,
      (SELECT COALESCE(sum(conversions),0) FROM referral_codes WHERE guild_id=$1) referral_conversions,
      (SELECT count(*) FROM partnerships WHERE guild_id=$1 AND status='active') active_partners,
      (SELECT count(*) FROM health_findings WHERE guild_id=$1 AND active=true) health_findings,
      (SELECT count(*) FROM usage_events WHERE guild_id=$1 AND created_at>=now()-interval '7 days') feature_events_7d`,[gid]),
    query<any>(`SELECT action,details,created_at FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 8`,[gid]),
    query<any>(`SELECT user_id,thanks_received FROM member_stats WHERE guild_id=$1 AND thanks_received>0 ORDER BY thanks_received DESC LIMIT 5`,[gid]),
    one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]),
    query<any>(`SELECT feature_key,enabled FROM feature_settings WHERE guild_id=$1`,[gid]),
    query<any>(`SELECT widget_key FROM dashboard_widgets WHERE guild_id=$1 AND admin_user_id=$2 AND enabled=true ORDER BY sort_order,widget_key`,[gid,req.session.user.id])
  ]);
  const names=new Map<string,string>(ui.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  res.render("control-home",{user:req.session.user,...ui,metrics:metrics||{},recent,kudos:kudos.map(k=>({...k,name:names.get(k.user_id)||k.user_id})),season,widgets:widgets.map(w=>String(w.widget_key)),features:new Map<string,boolean>(features.map(f=>[String(f.feature_key),Boolean(f.enabled)] as [string,boolean]))});
});

controlRouter.get("/control/members",async(req:any,res)=>{
  const gid=selectedGuildId(req),q=String(req.query.q||"").trim().toLowerCase(),ui=await guildUi(req);
  const matching=ui.members.filter(m=>!q||m.name.toLowerCase().includes(q)||m.username.toLowerCase().includes(q));
  const pageSize=50,pageCount=Math.max(1,Math.ceil(matching.length/pageSize));
  const page=Math.min(pageCount,Math.max(1,Number.parseInt(String(req.query.page||"1"),10)||1));
  let members=matching.slice((page-1)*pageSize,page*pageSize);
  const ids=members.map(m=>m.id);
  const [stats,economy,streaks,premium]=await Promise.all([
    ids.length?query<any>(`SELECT * FROM member_stats WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT * FROM member_economy WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT * FROM member_streaks WHERE guild_id=$1 AND user_id=ANY($2::text[])`,[gid,ids]):[],
    ids.length?query<any>(`SELECT discord_user_id FROM entitlements WHERE guild_id=$1 AND active=true AND (expires_at IS NULL OR expires_at>now()) AND discord_user_id=ANY($2::text[])`,[gid,ids]):[]
  ]);
  const premiumSet=new Set(premium.map(p=>p.discord_user_id));
  members=members.map(m=>{const e=economy.find(x=>x.user_id===m.id),st=stats.find(x=>x.user_id===m.id),sk=streaks.find(x=>x.user_id===m.id);return {...m,xp:Number(e?.xp_total||0),coins:Number(e?.coins_balance||0),level:levelFromXp(Number(e?.xp_total||0)),kudos:Number(st?.thanks_received||0),messages:Number(st?.messages||0),streak:Number(sk?.current_streak||0),premium:premiumSet.has(m.id),lastActive:st?.last_message_at||null,statsTracked:Boolean(st),economyTracked:Boolean(e),streakTracked:Boolean(sk)};});
  res.render("control-members",{user:req.session.user,...ui,members,q,page,pageSize,pageCount,totalMembers:matching.length});
});

controlRouter.get("/control/engagement",async(req:any,res)=>{
  const gid=selectedGuildId(req);
  const [ui,settings,season,quests,store,topKudos,achievements]=await Promise.all([
    guildUi(req),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[gid,["reputation","levels","giveaways","starboard"]]),
    one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid]),
    query<any>(`SELECT * FROM quest_definitions WHERE guild_id=$1 AND active=true ORDER BY cadence,sort_order`,[gid]),
    query<any>(`SELECT * FROM store_items WHERE guild_id=$1 ORDER BY sort_order,name`,[gid]),
    query<any>(`SELECT user_id,thanks_received FROM member_stats WHERE guild_id=$1 ORDER BY thanks_received DESC LIMIT 10`,[gid]),
    one<any>(`SELECT count(*) total FROM achievements WHERE guild_id=$1`,[gid])
  ]);
  const names=new Map<string,string>(ui.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  const settingsMap=new Map<string,any>();for(const key of ["reputation","levels","giveaways","starboard"]){const state=settings.find(s=>s.feature_key===key),status=state?.enabled===false?"Off":moduleSetupGaps(key,state?.config||{},Boolean(state)).length?"Needs setup":"On";settingsMap.set(key,{...state,enabled:state?.enabled!==false,status});}
  res.render("control-engagement",{user:req.session.user,...ui,settings:settingsMap,season,quests,store,topKudos:topKudos.map(k=>({...k,name:names.get(k.user_id)||k.user_id})),achievements:Number(achievements?.total||0)});
});

controlRouter.get("/control/community",async(req:any,res)=>{
  const gid=selectedGuildId(req);
  const [ui,responses,stickies,settings]=await Promise.all([
    guildUi(req),
    query<any>(`SELECT * FROM custom_responses WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[gid]),
    query<any>(`SELECT * FROM sticky_messages WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[gid]),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[gid,["welcome","role_menus","suggestions","tickets","starboard"]])
  ]);
  res.render("control-community",{user:req.session.user,...ui,responses,stickies,settings:new Map<string,any>(settings.map(s=>[String(s.feature_key),{...s,status:s.enabled===false?"Off":moduleSetupGaps(String(s.feature_key),s.config||{},true).length?"Needs setup":"On"}] as [string,any])),saved:req.query.saved==="1",error:String(req.query.error||"")});
});

controlRouter.post("/control/community/responses",async(req:any,res)=>{
  const trigger=String(req.body.trigger||"").trim(),response=String(req.body.response||"").trim(),mode=String(req.body.matchMode||"contains");
  const cooldown=Number(req.body.cooldownSeconds||30),channels=Array.isArray(req.body.channels)?req.body.channels:req.body.channels?[req.body.channels]:[];
  if(trigger.length<2||trigger.length>80||!response||response.length>1800)return res.redirect("/control/community?error="+encodeURIComponent("A reply needs a trigger (2–80 characters) and response (up to 1,800 characters)."));
  if(!["exact","contains","starts_with"].includes(mode)||!Number.isInteger(cooldown)||cooldown<5||cooldown>3600)return res.redirect("/control/community?error="+encodeURIComponent("Choose a valid match type and cooldown between 5 and 3,600 seconds."));
  const available=new Set((await guildUi(req)).channels.filter((c:any)=>c.type!==4).map((c:any)=>c.id));if(channels.some((id:string)=>!available.has(String(id))))return res.redirect("/control/community?error="+encodeURIComponent("One of the selected channels is no longer available. Reload and choose again."));
  await query(`INSERT INTO custom_responses(guild_id,trigger,response,match_mode,channel_ids,cooldown_seconds) VALUES($1,$2,$3,$4,$5,$6)`,[selectedGuildId(req),trigger,response,mode,channels,cooldown]);
  await audit(selectedGuildId(req),req.session.user.id,"community.response.create",{trigger,mode});res.redirect("/control/community?saved=1");
});
controlRouter.post("/control/community/responses/:id/toggle",async(req:any,res)=>{await query(`UPDATE custom_responses SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/community");});
controlRouter.post("/control/community/responses/:id/delete",async(req:any,res)=>{await query(`DELETE FROM custom_responses WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/community");});

controlRouter.post("/control/community/stickies",async(req:any,res)=>{
  const channelId=String(req.body.channelId||""),content=String(req.body.content||"").trim(),interval=Number(req.body.intervalSeconds||300);
  const available=new Set((await guildUi(req)).channels.filter((c:any)=>c.type!==4).map((c:any)=>c.id));
  if(!available.has(channelId)||!content||content.length>1800||!Number.isInteger(interval)||interval<60||interval>86400)return res.redirect("/control/community?error="+encodeURIComponent("Choose a text channel, enter reminder text up to 1,800 characters, and set an interval from 60 to 86,400 seconds."));
  await query(`INSERT INTO sticky_messages(guild_id,channel_id,content,min_interval_seconds,enabled) VALUES($1,$2,$3,$4,true)
    ON CONFLICT(guild_id,channel_id) DO UPDATE SET content=$3,min_interval_seconds=$4,enabled=true,updated_at=now()`,[selectedGuildId(req),channelId,content,interval]);
  await audit(selectedGuildId(req),req.session.user.id,"community.sticky.save",{channelId});res.redirect("/control/community?saved=1");
});
controlRouter.post("/control/community/stickies/:id/toggle",async(req:any,res)=>{await query(`UPDATE sticky_messages SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/community");});
controlRouter.post("/control/community/stickies/:id/delete",async(req:any,res)=>{await query(`DELETE FROM sticky_messages WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/community");});

controlRouter.get("/control/automation",async(req:any,res)=>{
  const [ui,scheduled,feeds,giveaways,timezoneRow]=await Promise.all([
    guildUi(req),
    query<any>(`SELECT * FROM scheduled_messages WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[selectedGuildId(req)]),
    query<any>(`SELECT * FROM social_feeds WHERE guild_id=$1 ORDER BY enabled DESC,id DESC`,[selectedGuildId(req)]),
    query<any>(`SELECT * FROM giveaways WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 20`,[selectedGuildId(req)]),
    one<any>(`SELECT config->>'timezone' timezone FROM feature_settings WHERE guild_id=$1 AND feature_key='scheduled_messages'`,[selectedGuildId(req)])
  ]);
  res.render("control-automation",{user:req.session.user,...ui,scheduled,feeds,giveaways,timezone:timezoneRow?.timezone||"Europe/London",baseUrl:config.baseUrl,hasXBearerToken:Boolean(config.xBearerToken),saved:req.query.saved==="1",error:String(req.query.error||"")});
});

controlRouter.post("/control/automation/scheduled",async(req:any,res)=>{
  const days=Array.isArray(req.body.days)?req.body.days:req.body.days?[req.body.days]:[];
  const name=String(req.body.name||"").trim(),channelId=String(req.body.channelId||""),content=String(req.body.content||"").trim(),hour=Number(req.body.hour),minute=Number(req.body.minute);
  const allowedDays=new Set(["0","1","2","3","4","5","6"]),available=new Set((await guildUi(req)).channels.filter((c:any)=>c.type!==4).map((c:any)=>c.id));
  if(!name||name.length>80||!available.has(channelId)||!content||content.length>2000||!Number.isInteger(hour)||hour<0||hour>23||!Number.isInteger(minute)||minute<0||minute>59||days.some((d:string)=>!allowedDays.has(String(d))))return res.redirect("/control/automation?error="+encodeURIComponent("Enter a name (up to 80 characters), a valid text channel, a message (up to 2,000 characters), a time and valid days."));
  const dow=days.length?[...new Set(days.map(String))].join(","):"*";
  await query(`INSERT INTO scheduled_messages(guild_id,name,channel_id,cron_expression,content,enabled) VALUES($1,$2,$3,$4,$5,true)`,[selectedGuildId(req),name,channelId,`${minute} ${hour} * * ${dow}`,content]);
  await audit(selectedGuildId(req),req.session.user.id,"automation.schedule.create",{name,channelId});res.redirect("/control/automation?saved=1");
});
controlRouter.post("/control/automation/scheduled/:id/toggle",async(req:any,res)=>{await query(`UPDATE scheduled_messages SET enabled=NOT enabled WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/automation?saved=1");});
controlRouter.post("/control/automation/scheduled/:id/delete",async(req:any,res)=>{await query(`DELETE FROM scheduled_messages WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/automation?saved=1");});

controlRouter.post("/control/automation/feeds",async(req:any,res)=>{
  const selectedProvider=String(req.body.provider||"rss");
  const allowedProviders=new Set(["eafc_leaks","rss","reddit","youtube","x","webhook"]);
  const available=await guildUi(req),channelId=String(req.body.channelId||""),mentionRoleId=String(req.body.mentionRoleId||"");
  const sourceInput=String(req.body.source||"").trim(),nameInput=String(req.body.name||"").trim();
  if(!allowedProviders.has(selectedProvider)||!available.channels.some((c:any)=>c.id===channelId)||!nameInput||nameInput.length>80||(mentionRoleId&&!available.roles.some((r:any)=>r.id===mentionRoleId)))return res.redirect("/control/automation?error="+encodeURIComponent("Choose a valid feed type, name, available destination channel and optional role."));
  if(selectedProvider!=="eafc_leaks"&&selectedProvider!=="webhook"&&!sourceInput)return res.redirect("/control/automation?error="+encodeURIComponent("Enter the account or feed URL for this source."));
  if(["rss","reddit","youtube"].includes(selectedProvider)){
    try{const url=new URL(sourceInput);if(!["http:","https:"].includes(url.protocol))throw new Error();}catch{return res.redirect("/control/automation?error="+encodeURIComponent("Feed source must be a valid http or https URL."));}
  }
  if(selectedProvider==="x"&&!/^@?[A-Za-z0-9_]{1,15}$/.test(sourceInput))return res.redirect("/control/automation?error="+encodeURIComponent("Enter an X username, with or without @."));
  const provider=selectedProvider==="eafc_leaks"?"webhook":selectedProvider;
  const source=selectedProvider==="eafc_leaks"?"EAFC.Live leaks":sourceInput;
  const name=selectedProvider==="eafc_leaks"?"EAFC.Live leak feed":nameInput;
  const secret=provider==="webhook"?createWebhookSecret():null;
  await query(`INSERT INTO social_feeds(guild_id,name,provider,source,channel_id,enabled,include_keywords,exclude_keywords,mention_role_id,secret_key) VALUES($1,$2,$3,$4,$5,true,$6,$7,$8,$9)`,[
    selectedGuildId(req),name,provider,source,channelId,
    String(req.body.includeKeywords||"").split(",").map((x:string)=>x.trim()).filter(Boolean),
    String(req.body.excludeKeywords||"").split(",").map((x:string)=>x.trim()).filter(Boolean),
    mentionRoleId||null,secret
  ]);
  await audit(selectedGuildId(req),req.session.user.id,"social.create",{name,provider:selectedProvider});res.redirect("/control/automation?saved=1");
});
controlRouter.post("/control/automation/feeds/:id/toggle",async(req:any,res)=>{await query(`UPDATE social_feeds SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/automation?saved=1");});
controlRouter.post("/control/automation/feeds/:id/delete",async(req:any,res)=>{await query(`DELETE FROM social_feeds WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/automation?saved=1");});

controlRouter.get("/control/safety",async(req:any,res)=>{
  const [ui,warnings,reports,tickets,settings]=await Promise.all([
    guildUi(req),
    query<any>(`SELECT * FROM warnings WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[selectedGuildId(req)]),
    query<any>(`SELECT * FROM scam_cases WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[selectedGuildId(req)]),
    query<any>(`SELECT * FROM tickets WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[selectedGuildId(req)]),
    query<any>(`SELECT feature_key,enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=ANY($2::text[])`,[selectedGuildId(req),["automod","mod_tools","join_security","tickets"]])
  ]);
  res.render("control-safety",{user:req.session.user,...ui,warnings,reports,tickets,settings:new Map<string,any>(settings.map(s=>[String(s.feature_key),s] as [string,any]))});
});

controlRouter.get("/control/settings",async(req:any,res)=>{
  const gid=selectedGuildId(req),[ui,rows,feeds,schedules]=await Promise.all([guildUi(req),query<any>(`SELECT feature_key,enabled,config,updated_at FROM feature_settings WHERE guild_id=$1`,[gid]),query<any>(`SELECT provider,enabled FROM social_feeds WHERE guild_id=$1`,[gid]),one<any>(`SELECT count(*) FILTER(WHERE enabled)::int active FROM scheduled_messages WHERE guild_id=$1`,[gid])]);
  const map=new Map<string,any>(rows.map(r=>[String(r.feature_key),r] as [string,any]));
  const featureRows=modules.map(m=>{
    const state=map.get(m.key),enabled=state?.enabled!==false;let gaps=moduleSetupGaps(m.key,state?.config||{},Boolean(state));
    if(m.key==="social_feeds"&&feeds.some(f=>f.enabled)){
      gaps=gaps.filter(g=>!g.startsWith("Add an active feed"));
      if(feeds.some(f=>f.enabled&&f.provider==="x")&&!config.xBearerToken)gaps.push("Add the X API bearer token to the platform configuration.");
    }
    if(m.key==="scheduled_messages"&&Number(schedules?.active||0)>0)gaps=gaps.filter(g=>!g.startsWith("Add a post"));
    if(m.key==="premium_billing"&&(!config.stripeSecretKey||!config.stripeWebhookSecret))gaps.push("Connect Stripe and set its webhook secret before enabling memberships.");
    const status=!enabled?"Off":gaps.length?"Needs setup":"On";
    return {...m,state,status,gaps};
  });
  res.render("control-settings",{user:req.session.user,...ui,modules:featureRows,botRemoved:req.query.botRemoved==="1"});
});

controlRouter.post("/control/settings/remove-bot",async(req:any,res)=>{
  const guildId=selectedGuildId(req);
  const guild=client.guilds.cache.get(guildId);
  if(!guild)return res.status(404).send("The bot is not connected to the selected server.");
  if(String(req.body.guildId||"")!==guild.id)return res.status(409).send("The selected server changed. Reload the settings page and try again.");
  if(String(req.body.confirmation||"").trim()!==guild.name)return res.status(400).send("Type the selected server's exact name to confirm removal.");

  const actor=req.session.user!;
  const details={guildId:guild.id,guildName:guild.name,requestedBy:actor.id};
  await audit(guild.id,actor.id,"bot.leave.requested",details);
  try{
    await guild.leave();
  }catch(err:any){
    await audit(guild.id,actor.id,"bot.leave.failed",{...details,error:String(err?.message||err).slice(0,300)}).catch(()=>{});
    console.error("Dashboard bot removal failed",guild.id,err);
    return res.status(502).send("Discord could not remove the bot from this server. No server content was deleted.");
  }

  await audit(guild.id,actor.id,"bot.leave.completed",details).catch(err=>console.error("Bot removal audit failed",err));
  if(req.session.user?.guilds)req.session.user.guilds=req.session.user.guilds.filter((item: any)=>item.id!==guild.id);
  if(req.session.selectedGuildId===guild.id)delete req.session.selectedGuildId;
  res.redirect("/control/settings?botRemoved=1");
});
