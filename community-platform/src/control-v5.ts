import { Router } from "express";
import { client } from "./bot.js";
import { selectedGuildId } from "./dashboard-context.js";
import { audit, getFeature, one, query } from "./db.js";
import {
  applyHealthFix, inspectMemberPermission, publishDailyPanel, publishFlashDrop, publishOnboardingPanel,
  publishRolePanel, publishTemplate, scanHealth
} from "./community-suite-v5.js";

export const v5ControlRouter=Router();
const auth=(req:any,res:any,next:any)=>req.session?.user?next():res.redirect("/login");
v5ControlRouter.use(auth);

const arr=(v:any)=>Array.isArray(v)?v:v?[v]:[];
const num=(v:any,fallback=0)=>Number.isFinite(Number(v))?Number(v):fallback;
const bool=(v:any)=>v==="on"||v==="true"||v===true;

async function ui(req:any){
  const guild=client.guilds.cache.get(selectedGuildId(req));
  if(!guild)return {guild:null,channels:[],roles:[],members:[]};
  const members=await guild.members.fetch().catch(()=>guild.members.cache),botHighest=guild.members.me?.roles.highest.position??0;
  return {
    guild,
    channels:[...guild.channels.cache.values()].filter((c:any)=>c.isTextBased()||c.type===2).map((c:any)=>({id:c.id,name:c.name,type:c.type})).sort((a,b)=>a.name.localeCompare(b.name)),
    roles:[...guild.roles.cache.values()].filter((r:any)=>r.id!==guild.id&&!r.managed&&r.position<botHighest).map((r:any)=>({id:r.id,name:r.name})).sort((a,b)=>a.name.localeCompare(b.name)),
    members:[...members.values()].filter((m:any)=>!m.user.bot).map((m:any)=>({id:m.id,name:m.displayName,username:m.user.username}))
  };
}

v5ControlRouter.get("/control/onboarding",async(req:any,res)=>{
  const gid=selectedGuildId(req),[base,onboarding,birthday,counting,counters]=await Promise.all([
    ui(req),one<any>(`SELECT * FROM onboarding_configs WHERE guild_id=$1`,[gid]),
    getFeature(gid,"birthdays",{channelId:"",roleId:"",xpReward:50,coinReward:100}),
    one<any>(`SELECT * FROM counting_configs WHERE guild_id=$1`,[gid]),
    query<any>(`SELECT * FROM server_counters WHERE guild_id=$1 ORDER BY id`,[gid])
  ]);
  res.render("control-onboarding",{user:req.session.user,...base,onboarding:onboarding||{},birthday,counting:counting||{},counters,saved:req.query.saved==="1"});
});

v5ControlRouter.post("/control/onboarding",async(req:any,res)=>{
  const gid=selectedGuildId(req),platformRoles:any={},interestRoles:any={},notificationRoles:any={};
  for(const key of ["PlayStation","Xbox","PC"]){const v=req.body[`platform_${key.replace(/[^A-Za-z]/g,"")}`];if(v)platformRoles[key]=v;}
  for(const key of ["EAFC.Live","Ultimate Team","SBCs & Objectives","Gameplay","Community"]){const field=`interest_${key.replace(/[^A-Za-z]/g,"")}`,v=req.body[field];if(v)interestRoles[key]=v;}
  for(const key of ["Announcements","Giveaways","Events","Premium"]){const v=req.body[`notification_${key}`];if(v)notificationRoles[key]=v;}
  const questions=String(req.body.questions||"").split("\n").map((x:string)=>x.trim()).filter(Boolean).slice(0,5).map((label:string,n:number)=>({key:`q${n+1}`,label}));
  await query(`INSERT INTO onboarding_configs(guild_id,enabled,channel_id,verified_role_id,quarantine_role_id,platform_roles,interest_roles,notification_roles,questions,min_account_age_hours,welcome_title,welcome_body)
    VALUES($1,true,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8::jsonb,$9,$10,$11)
    ON CONFLICT(guild_id) DO UPDATE SET enabled=true,channel_id=$2,verified_role_id=$3,quarantine_role_id=$4,platform_roles=$5::jsonb,interest_roles=$6::jsonb,notification_roles=$7::jsonb,questions=$8::jsonb,min_account_age_hours=$9,welcome_title=$10,welcome_body=$11,updated_at=now()`,
    [gid,req.body.channelId||null,req.body.verifiedRoleId||null,req.body.quarantineRoleId||null,JSON.stringify(platformRoles),JSON.stringify(interestRoles),JSON.stringify(notificationRoles),JSON.stringify(questions),Math.max(0,num(req.body.minAccountAgeHours,24)),String(req.body.welcomeTitle||"Welcome to EAFC.Live"),String(req.body.welcomeBody||"Verify your account, choose your platform and personalise your community experience.")]);
  await audit(gid,req.session.user.id,"onboarding.settings.update",{channelId:req.body.channelId});res.redirect("/control/onboarding?saved=1");
});

v5ControlRouter.post("/control/onboarding/publish",async(req:any,res)=>{try{await publishOnboardingPanel(selectedGuildId(req),String(req.body.channelId||""));await audit(selectedGuildId(req),req.session.user.id,"onboarding.panel.publish",{channelId:req.body.channelId});res.redirect("/control/onboarding?saved=1");}catch(e:any){res.status(400).send(e.message);}});

v5ControlRouter.post("/control/onboarding/birthday",async(req:any,res)=>{
  const cfg={channelId:req.body.channelId||"",roleId:req.body.roleId||"",xpReward:Math.max(0,num(req.body.xpReward,50)),coinReward:Math.max(0,num(req.body.coinReward,100))};
  await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config) VALUES($1,'birthdays',$2,$3::jsonb) ON CONFLICT(guild_id,feature_key) DO UPDATE SET enabled=$2,config=$3::jsonb,updated_at=now()`,[selectedGuildId(req),bool(req.body.enabled),JSON.stringify(cfg)]);
  res.redirect("/control/onboarding?saved=1");
});

v5ControlRouter.post("/control/onboarding/counting",async(req:any,res)=>{
  await query(`INSERT INTO counting_configs(guild_id,channel_id,next_number,enabled,reward_every) VALUES($1,$2,$3,$4,$5) ON CONFLICT(guild_id) DO UPDATE SET channel_id=$2,next_number=$3,last_user_id=NULL,last_message_id=NULL,enabled=$4,reward_every=$5,updated_at=now()`,
    [selectedGuildId(req),req.body.channelId||null,Math.max(1,num(req.body.nextNumber,1)),bool(req.body.enabled),Math.max(0,num(req.body.rewardEvery,100))]);
  res.redirect("/control/onboarding?saved=1");
});

v5ControlRouter.post("/control/onboarding/counters",async(req:any,res)=>{
  if(!req.body.channelId)return res.redirect("/control/onboarding");
  await query(`INSERT INTO server_counters(guild_id,channel_id,metric,label,enabled) VALUES($1,$2,$3,$4,true) ON CONFLICT(guild_id,channel_id) DO UPDATE SET metric=$3,label=$4,enabled=true,updated_at=now()`,
    [selectedGuildId(req),req.body.channelId,String(req.body.metric||"members"),String(req.body.label||"Members: {count}")]);
  res.redirect("/control/onboarding?saved=1");
});
v5ControlRouter.post("/control/onboarding/counters/:id/delete",async(req:any,res)=>{await query(`DELETE FROM server_counters WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/onboarding");});

v5ControlRouter.get("/control/security",async(req:any,res)=>{
  const gid=selectedGuildId(req),base=await ui(req),feature=await getFeature(gid,"security_suite",{antiAlt:true,minAccountAgeHours:24,antiRaid:true,joinsPerMinute:8,quarantineOnRaid:true,antiNuke:true,actionWindowSeconds:60,maxDestructiveActions:4,trustedRoleIds:[],trustedUserIds:[]});
  const findings=await query<any>(`SELECT * FROM health_findings WHERE guild_id=$1 AND active=true ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,id`,[gid]);
  const events=await query<any>(`SELECT * FROM security_events WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 50`,[gid]);
  let inspector:any=null;if(req.query.memberId&&req.query.channelId)try{inspector=await inspectMemberPermission(gid,String(req.query.memberId),String(req.query.channelId));}catch(e:any){inspector={error:e.message};}
  const score=Math.max(0,100-findings.reduce((n:any,f:any)=>n+(f.severity==="critical"?20:f.severity==="warning"?8:2),0));
  res.render("control-security",{user:req.session.user,...base,feature,findings,events,inspector,score,requestedMember:String(req.query.memberId||""),requestedChannel:String(req.query.channelId||""),saved:req.query.saved==="1"});
});

v5ControlRouter.post("/control/security",async(req:any,res)=>{
  const cfg={antiAlt:bool(req.body.antiAlt),minAccountAgeHours:Math.max(0,num(req.body.minAccountAgeHours,24)),antiRaid:bool(req.body.antiRaid),joinsPerMinute:Math.max(2,num(req.body.joinsPerMinute,8)),quarantineOnRaid:bool(req.body.quarantineOnRaid),antiNuke:bool(req.body.antiNuke),actionWindowSeconds:Math.max(10,num(req.body.actionWindowSeconds,60)),maxDestructiveActions:Math.max(1,num(req.body.maxDestructiveActions,4)),trustedRoleIds:arr(req.body.trustedRoleIds),trustedUserIds:arr(req.body.trustedUserIds)};
  await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config) VALUES($1,'security_suite',true,$2::jsonb) ON CONFLICT(guild_id,feature_key) DO UPDATE SET enabled=true,config=$2::jsonb,updated_at=now()`,[selectedGuildId(req),JSON.stringify(cfg)]);
  await audit(selectedGuildId(req),req.session.user.id,"security.settings.update",cfg);res.redirect("/control/security?saved=1");
});
v5ControlRouter.post("/control/security/rescan",async(req:any,res)=>{await scanHealth(client,selectedGuildId(req));res.redirect("/control/security");});
v5ControlRouter.post("/control/security/fix/:id",async(req:any,res)=>{try{await applyHealthFix(selectedGuildId(req),Number(req.params.id));res.redirect("/control/security");}catch(e:any){res.status(400).send(e.message);}});

v5ControlRouter.get("/control/studio",async(req:any,res)=>{
  const [base,templates,panels,reactions]=await Promise.all([ui(req),query<any>(`SELECT * FROM message_templates WHERE guild_id=$1 ORDER BY updated_at DESC`,[selectedGuildId(req)]),query<any>(`SELECT * FROM role_panels WHERE guild_id=$1 ORDER BY updated_at DESC`,[selectedGuildId(req)]),query<any>(`SELECT * FROM reaction_roles WHERE guild_id=$1 ORDER BY message_id,emoji`,[selectedGuildId(req)])]);
  res.render("control-studio",{user:req.session.user,...base,templates,panels,reactions,saved:req.query.saved==="1"});
});

v5ControlRouter.post("/control/studio/templates",async(req:any,res)=>{
  const buttons:any[]=[];for(let i=1;i<=5;i++){const label=String(req.body[`button${i}Label`]||"").trim();if(!label)continue;const url=String(req.body[`button${i}Url`]||"").trim(),roleId=String(req.body[`button${i}Role`]||"").trim();buttons.push({label,url:url||undefined,roleId:roleId||undefined});}
  const opts:any[]=[];for(let i=1;i<=5;i++){const label=String(req.body[`option${i}Label`]||"").trim();if(!label)continue;opts.push({label,value:`option-${i}`,roleId:req.body[`option${i}Role`]||undefined,response:req.body[`option${i}Response`]||undefined});}
  const select=opts.length?{placeholder:String(req.body.selectPlaceholder||"Choose an option"),options:opts}:{};
  await query(`INSERT INTO message_templates(guild_id,name,template_type,title,body,colour,image_url,thumbnail_url,mention_role_id,button_config,select_config,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12)`,
    [selectedGuildId(req),String(req.body.name||"Announcement"),String(req.body.templateType||"announcement"),req.body.title||null,String(req.body.body||""),req.body.colour?parseInt(String(req.body.colour).replace("#",""),16)||null:null,req.body.imageUrl||null,req.body.thumbnailUrl||null,req.body.mentionRoleId||null,JSON.stringify(buttons),JSON.stringify(select),req.session.user.id]);
  res.redirect("/control/studio?saved=1");
});
v5ControlRouter.post("/control/studio/templates/:id/publish",async(req:any,res)=>{try{await publishTemplate(client,selectedGuildId(req),Number(req.params.id),String(req.body.channelId||""));await recordStudioAudit(req,"studio.template.publish",{id:req.params.id,channelId:req.body.channelId});res.redirect("/control/studio?saved=1");}catch(e:any){res.status(400).send(e.message);}});
v5ControlRouter.post("/control/studio/templates/:id/delete",async(req:any,res)=>{await query(`DELETE FROM message_templates WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/studio");});

v5ControlRouter.post("/control/studio/panels",async(req:any,res)=>{
  const roles:any[]=[];for(let i=1;i<=10;i++){const roleId=String(req.body[`role${i}Id`]||"");if(roleId)roles.push({roleId,label:String(req.body[`role${i}Label`]||"Role")});}
  const row=(await query<any>(`INSERT INTO role_panels(guild_id,name,channel_id,panel_type,roles,title,body) VALUES($1,$2,$3,$4,$5::jsonb,$6,$7) RETURNING id`,[selectedGuildId(req),String(req.body.name||"Role panel"),String(req.body.channelId||""),String(req.body.panelType||"buttons"),JSON.stringify(roles),String(req.body.title||"Choose your roles"),String(req.body.body||"Use the controls below to manage your roles.")]))[0];
  if(bool(req.body.publishNow))await publishRolePanel(client,selectedGuildId(req),row.id);
  res.redirect("/control/studio?saved=1");
});
v5ControlRouter.post("/control/studio/panels/:id/publish",async(req:any,res)=>{try{await publishRolePanel(client,selectedGuildId(req),Number(req.params.id));res.redirect("/control/studio?saved=1");}catch(e:any){res.status(400).send(e.message);}});

v5ControlRouter.post("/control/studio/reaction-role",async(req:any,res)=>{
  await query(`INSERT INTO reaction_roles(guild_id,message_id,channel_id,emoji,role_id,enabled) VALUES($1,$2,$3,$4,$5,true) ON CONFLICT(guild_id,message_id,emoji) DO UPDATE SET role_id=$5,channel_id=$3,enabled=true`,[selectedGuildId(req),String(req.body.messageId||""),String(req.body.channelId||""),String(req.body.emoji||"⭐"),String(req.body.roleId||"")]);
  res.redirect("/control/studio?saved=1");
});
v5ControlRouter.post("/control/studio/reaction-role/delete",async(req:any,res)=>{await query(`DELETE FROM reaction_roles WHERE guild_id=$1 AND message_id=$2 AND emoji=$3`,[selectedGuildId(req),req.body.messageId,req.body.emoji]);res.redirect("/control/studio");});

async function recordStudioAudit(req:any,action:string,details:any){await audit(selectedGuildId(req),req.session.user.id,action,details);}

v5ControlRouter.get("/control/kudos",async(req:any,res)=>{
  const gid=selectedGuildId(req),[base,milestones,leaders,categories,recognition,recaps,workflows]=await Promise.all([
    ui(req),query<any>(`SELECT * FROM kudos_milestones WHERE guild_id=$1 ORDER BY milestone`,[gid]),
    query<any>(`SELECT receiver_id user_id,count(*)::int value FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '7 days' GROUP BY receiver_id ORDER BY value DESC LIMIT 20`,[gid]),
    query<any>(`SELECT category,count(*)::int value FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '30 days' GROUP BY category ORDER BY value DESC`,[gid]),
    one<any>(`SELECT * FROM recognition_role_settings WHERE guild_id=$1`,[gid]),one<any>(`SELECT * FROM recap_settings WHERE guild_id=$1`,[gid]),query<any>(`SELECT * FROM level_workflows WHERE guild_id=$1 ORDER BY level`,[gid])
  ]);
  const names=new Map<string,string>(base.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  res.render("control-kudos",{user:req.session.user,...base,milestones,leaders:leaders.map(x=>({...x,name:names.get(x.user_id)||x.user_id})),categories,recognition:recognition||{},recaps:recaps||{},workflows,saved:req.query.saved==="1"});
});
v5ControlRouter.post("/control/kudos/milestones",async(req:any,res)=>{
  await query(`INSERT INTO kudos_milestones(guild_id,milestone,role_id,xp_reward,coin_reward,badge_key,enabled) VALUES($1,$2,$3,$4,$5,$6,true) ON CONFLICT(guild_id,milestone) DO UPDATE SET role_id=$3,xp_reward=$4,coin_reward=$5,badge_key=$6,enabled=true`,[selectedGuildId(req),Math.max(1,num(req.body.milestone,10)),req.body.roleId||null,Math.max(0,num(req.body.xpReward)),Math.max(0,num(req.body.coinReward)),req.body.badgeKey||null]);res.redirect("/control/kudos?saved=1");
});
v5ControlRouter.post("/control/kudos/recognition",async(req:any,res)=>{
  await query(`INSERT INTO recognition_role_settings(guild_id,weekly_role_id,season_role_id) VALUES($1,$2,$3) ON CONFLICT(guild_id) DO UPDATE SET weekly_role_id=$2,season_role_id=$3,updated_at=now()`,[selectedGuildId(req),req.body.weeklyRoleId||null,req.body.seasonRoleId||null]);res.redirect("/control/kudos?saved=1");
});
v5ControlRouter.post("/control/kudos/recaps",async(req:any,res)=>{
  await query(`INSERT INTO recap_settings(guild_id,weekly_enabled,weekly_channel_id,weekly_day,weekly_hour,personal_weekly_enabled,monthly_enabled,monthly_channel_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(guild_id) DO UPDATE SET weekly_enabled=$2,weekly_channel_id=$3,weekly_day=$4,weekly_hour=$5,personal_weekly_enabled=$6,monthly_enabled=$7,monthly_channel_id=$8,updated_at=now()`,[selectedGuildId(req),bool(req.body.weeklyEnabled),req.body.weeklyChannelId||null,num(req.body.weeklyDay,0),num(req.body.weeklyHour,19),bool(req.body.personalWeeklyEnabled),bool(req.body.monthlyEnabled),req.body.monthlyChannelId||null]);res.redirect("/control/kudos?saved=1");
});
v5ControlRouter.post("/control/kudos/level-workflow",async(req:any,res)=>{
  await query(`INSERT INTO level_workflows(guild_id,level,role_id,coin_reward,message,announce_channel_id,enabled) VALUES($1,$2,$3,$4,$5,$6,true) ON CONFLICT(guild_id,level) DO UPDATE SET role_id=$3,coin_reward=$4,message=$5,announce_channel_id=$6,enabled=true`,[selectedGuildId(req),Math.max(1,num(req.body.level,5)),req.body.roleId||null,Math.max(0,num(req.body.coinReward)),req.body.message||null,req.body.channelId||null]);res.redirect("/control/kudos?saved=1");
});

v5ControlRouter.get("/control/growth",async(req:any,res)=>{
  const gid=selectedGuildId(req),[base,inviteLeaders,inviteMilestones,partners,boosterMilestones]=await Promise.all([
    ui(req),query<any>(`SELECT inviter_id user_id,count(*) FILTER(WHERE retained_7d)::int retained,count(*)::int total FROM invite_joins WHERE guild_id=$1 AND inviter_id IS NOT NULL GROUP BY inviter_id ORDER BY retained DESC,total DESC LIMIT 30`,[gid]),
    query<any>(`SELECT * FROM invite_milestones WHERE guild_id=$1 ORDER BY retained_invites`,[gid]),query<any>(`SELECT p.*,
      (SELECT count(*) FROM invite_joins i WHERE i.guild_id=p.guild_id AND i.invite_code=p.invite_code) joins,
      (SELECT count(*) FROM invite_joins i WHERE i.guild_id=p.guild_id AND i.invite_code=p.invite_code AND i.retained_7d) retained,
      (SELECT count(*) FROM invite_joins i JOIN member_stats s ON s.guild_id=i.guild_id AND s.user_id=i.user_id WHERE i.guild_id=p.guild_id AND i.invite_code=p.invite_code AND s.last_message_at>now()-interval '7 days') active_7d,
      (SELECT count(DISTINCT i.user_id) FROM invite_joins i JOIN billing_subscriptions b ON b.guild_id=i.guild_id AND b.discord_user_id=i.user_id WHERE i.guild_id=p.guild_id AND i.invite_code=p.invite_code AND b.status IN ('active','past_due','comped','gifted')) premium
      FROM partnerships p WHERE p.guild_id=$1 ORDER BY p.status,p.partner_name`,[gid]),
    query<any>(`SELECT * FROM booster_milestones WHERE guild_id=$1 ORDER BY months`,[gid])
  ]);
  const names=new Map<string,string>(base.members.map(m=>[String(m.id),String(m.name)] as [string,string]));
  res.render("control-growth",{user:req.session.user,...base,inviteLeaders:inviteLeaders.map(x=>({...x,name:names.get(x.user_id)||x.user_id})),inviteMilestones,partners,boosterMilestones,saved:req.query.saved==="1"});
});
v5ControlRouter.post("/control/growth/partners",async(req:any,res)=>{
  await query(`INSERT INTO partnerships(guild_id,partner_name,server_id,contact_name,contact_discord_id,invite_code,notes,status,started_at,review_at) VALUES($1,$2,$3,$4,$5,$6,$7,'active',$8,$9)`,[selectedGuildId(req),String(req.body.partnerName||"Partner"),req.body.serverId||null,req.body.contactName||null,req.body.contactDiscordId||null,req.body.inviteCode||null,req.body.notes||null,req.body.startedAt||null,req.body.reviewAt||null]);res.redirect("/control/growth?saved=1");
});
v5ControlRouter.post("/control/growth/partners/:id/toggle",async(req:any,res)=>{await query(`UPDATE partnerships SET status=CASE WHEN status='active' THEN 'paused' ELSE 'active' END,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/growth");});
v5ControlRouter.post("/control/growth/invite-milestone",async(req:any,res)=>{await query(`INSERT INTO invite_milestones(guild_id,retained_invites,role_id,xp_reward,coin_reward,premium_days,enabled) VALUES($1,$2,$3,$4,$5,$6,true) ON CONFLICT(guild_id,retained_invites) DO UPDATE SET role_id=$3,xp_reward=$4,coin_reward=$5,premium_days=$6,enabled=true`,[selectedGuildId(req),Math.max(1,num(req.body.retainedInvites)),req.body.roleId||null,Math.max(0,num(req.body.xpReward)),Math.max(0,num(req.body.coinReward)),Math.max(0,num(req.body.premiumDays))]);res.redirect("/control/growth?saved=1");});
v5ControlRouter.post("/control/growth/booster-milestone",async(req:any,res)=>{await query(`INSERT INTO booster_milestones(guild_id,months,role_id,xp_reward,coin_reward,enabled) VALUES($1,$2,$3,$4,$5,true) ON CONFLICT(guild_id,months) DO UPDATE SET role_id=$3,xp_reward=$4,coin_reward=$5,enabled=true`,[selectedGuildId(req),Math.max(1,num(req.body.months)),req.body.roleId||null,Math.max(0,num(req.body.xpReward)),Math.max(0,num(req.body.coinReward))]);res.redirect("/control/growth?saved=1");});

v5ControlRouter.get("/control/insights",async(req:any,res)=>{
  const gid=selectedGuildId(req),[base,funnel,engagement,premium,referrals,commands,features,widgets]=await Promise.all([
    ui(req),
    one<any>(`SELECT count(*) joins,count(*) FILTER(WHERE verified_at IS NOT NULL) verified,count(*) FILTER(WHERE first_active_at IS NOT NULL) activated,count(*) FILTER(WHERE retained_1d) retained1,count(*) FILTER(WHERE retained_7d) retained7,count(*) FILTER(WHERE retained_30d) retained30 FROM member_funnel WHERE guild_id=$1`,[gid]),
    one<any>(`SELECT (SELECT count(*) FROM reputation_events WHERE guild_id=$1 AND created_at>=now()-interval '30 days') kudos,(SELECT count(*) FROM member_quest_progress WHERE guild_id=$1 AND rewarded_at>=now()-interval '30 days') quests,(SELECT count(*) FROM member_streaks WHERE guild_id=$1 AND current_streak>0) streaks,(SELECT count(*) FROM giveaway_entries ge JOIN giveaways g ON g.id=ge.giveaway_id WHERE g.guild_id=$1 AND ge.created_at>=now()-interval '30 days') giveaway_entries`,[gid]),
    one<any>(`SELECT count(*) FILTER(WHERE source='stripe') total,count(*) FILTER(WHERE source='stripe' AND status IN ('active','past_due')) active,count(*) FILTER(WHERE source='stripe' AND status IN ('canceled','revoked')) churned,count(*) FILTER(WHERE source='stripe' AND created_at>=now()-interval '30 days') conversions30 FROM billing_subscriptions WHERE guild_id=$1`,[gid]),
    one<any>(`SELECT count(*) codes,COALESCE(sum(clicks),0) clicks,COALESCE(sum(conversions),0) conversions FROM referral_codes WHERE guild_id=$1`,[gid]),
    query<any>(`SELECT feature_key,count(*)::int uses,count(DISTINCT user_id)::int users FROM usage_events WHERE guild_id=$1 AND event_type='command' AND created_at>=now()-interval '30 days' GROUP BY feature_key ORDER BY uses DESC LIMIT 20`,[gid]),
    query<any>(`SELECT feature_key,count(*)::int uses,max(created_at) last_used FROM usage_events WHERE guild_id=$1 AND created_at>=now()-interval '30 days' GROUP BY feature_key ORDER BY uses DESC`,[gid]),
    query<any>(`SELECT * FROM dashboard_widgets WHERE guild_id=$1 AND admin_user_id=$2 ORDER BY sort_order,widget_key`,[gid,req.session.user.id])
  ]);
  const configured=await query<any>(`SELECT feature_key,enabled FROM feature_settings WHERE guild_id=$1 AND enabled=true`,[gid]),usageMap=new Map(features.map(x=>[x.feature_key,x]));
  const dead=configured.map(x=>({feature_key:x.feature_key,...(usageMap.get(x.feature_key)||{uses:0,last_used:null})})).filter(x=>Number(x.uses||0)===0);
  res.render("control-insights",{user:req.session.user,...base,funnel:funnel||{},engagement:engagement||{},premium:premium||{},referrals:referrals||{},commands,features,dead,widgets,saved:req.query.saved==="1"});
});
v5ControlRouter.post("/control/insights/widgets",async(req:any,res)=>{await query(`DELETE FROM dashboard_widgets WHERE guild_id=$1 AND admin_user_id=$2`,[selectedGuildId(req),req.session.user.id]);let n=0;for(const key of arr(req.body.widgets))await query(`INSERT INTO dashboard_widgets(guild_id,admin_user_id,widget_key,sort_order) VALUES($1,$2,$3,$4)`,[selectedGuildId(req),req.session.user.id,key,n++]);res.redirect("/control/insights?saved=1");});

v5ControlRouter.get("/control/rewards",async(req:any,res)=>{
  const gid=selectedGuildId(req),[base,items,drops,season]=await Promise.all([ui(req),query<any>(`SELECT * FROM store_items WHERE guild_id=$1 ORDER BY active DESC,sort_order,name`,[gid]),query<any>(`SELECT d.*,(SELECT count(*) FROM flash_drop_claims c WHERE c.drop_id=d.id) claims FROM flash_drops d WHERE d.guild_id=$1 ORDER BY d.created_at DESC LIMIT 30`,[gid]),one<any>(`SELECT * FROM economy_seasons WHERE guild_id=$1 AND active=true ORDER BY starts_at DESC LIMIT 1`,[gid])]);
  res.render("control-rewards",{user:req.session.user,...base,items,drops,season,saved:req.query.saved==="1"});
});
v5ControlRouter.post("/control/rewards/store",async(req:any,res)=>{
  const type=String(req.body.fulfillmentType||"role"),key=String(req.body.itemKey||"").trim().toLowerCase().replace(/[^a-z0-9-]+/g,"-")||`reward-${Date.now()}`;
  const metadata:any={};if(type==="custom"){metadata.cosmetic_key=req.body.cosmeticKey||"title";metadata.value=req.body.cosmeticValue||req.body.name;}if(type==="badge"){metadata.achievement_key=req.body.badgeKey||key;}
  await query(`INSERT INTO store_items(guild_id,item_key,name,description,emoji,cost_coins,active,stock,per_user_limit,fulfillment_type,duration_days,role_id,metadata,sort_order,available_from,available_until,season_id,cosmetic) VALUES($1,$2,$3,$4,$5,$6,true,$7,$8,$9,$10,$11,$12::jsonb,$13,$14,$15,$16,$17) ON CONFLICT(guild_id,item_key) DO UPDATE SET name=$3,description=$4,emoji=$5,cost_coins=$6,active=true,stock=$7,per_user_limit=$8,fulfillment_type=$9,duration_days=$10,role_id=$11,metadata=$12::jsonb,sort_order=$13,available_from=$14,available_until=$15,season_id=$16,cosmetic=$17,updated_at=now()`,
    [selectedGuildId(req),key,String(req.body.name||"Reward"),String(req.body.description||""),String(req.body.emoji||"🎁"),Math.max(0,num(req.body.costCoins)),req.body.stock?Math.max(0,num(req.body.stock)):null,req.body.perUserLimit?Math.max(1,num(req.body.perUserLimit)):null,type,req.body.durationDays?Math.max(1,num(req.body.durationDays)):null,req.body.roleId||null,JSON.stringify(metadata),num(req.body.sortOrder),req.body.availableFrom||null,req.body.availableUntil||null,bool(req.body.seasonal)&&req.body.seasonId?num(req.body.seasonId):null,type==="role"||type==="custom"]);
  res.redirect("/control/rewards?saved=1");
});
v5ControlRouter.post("/control/rewards/store/:id/toggle",async(req:any,res)=>{await query(`UPDATE store_items SET active=NOT active,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,selectedGuildId(req)]);res.redirect("/control/rewards");});
v5ControlRouter.post("/control/rewards/drop",async(req:any,res)=>{try{await publishFlashDrop(client,selectedGuildId(req),String(req.body.channelId||""),String(req.body.name||"Live Drop"),Math.max(0,num(req.body.coins)),Math.max(0,num(req.body.xp)),Math.max(1,num(req.body.durationMinutes,15)),req.body.maxClaims?Math.max(1,num(req.body.maxClaims)):null,req.session.user.id);res.redirect("/control/rewards?saved=1");}catch(e:any){res.status(400).send(e.message);}});
v5ControlRouter.post("/control/rewards/daily-panel",async(req:any,res)=>{try{await publishDailyPanel(client,selectedGuildId(req),String(req.body.channelId||""));res.redirect("/control/rewards?saved=1");}catch(e:any){res.status(400).send(e.message);}});
