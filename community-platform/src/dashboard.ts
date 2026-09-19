import express from "express";
import session from "express-session";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, EmbedBuilder, PermissionFlagsBits, TextChannel } from "discord.js";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, one, query } from "./db.js";
import { moduleMap, modules } from "./modules.js";
import { createWebhookSecret, deliverWebhook } from "./social.js";
import { billingRouter } from "./billing-dashboard.js";
import { PostgresSessionStore } from "./session-store.js";

declare module "express-session" {
  interface SessionData { user?: { id:string; username:string; avatar?:string; permissions?:string }; oauthState?: string; }
}

const here=path.dirname(fileURLToPath(import.meta.url));
export const app=express();

app.set("trust proxy",1);
app.set("view engine","ejs");
app.set("views",path.join(here,"..","views"));
app.use(express.urlencoded({extended:true,limit:"1mb"}));
app.use(express.json({limit:"1mb",verify:(req:any,_res,buf)=>{req.rawBody=Buffer.from(buf);}}));
app.use(express.static(path.join(here,"..","public")));
app.use(session({
  store:new PostgresSessionStore(),
  secret:config.sessionSecret,
  resave:false,
  saveUninitialized:false,
  proxy:true,
  cookie:{httpOnly:true,sameSite:"lax",secure:process.env.NODE_ENV==="production",maxAge:7*24*60*60*1000}
}));

function dashboardSidebar(pathname:string) {
  const items:[string,string][]=[
    ["/dashboard","Overview"],["/setup","Setup"],["/members","Members"],["/economy","Economy"],["/analytics","Analytics"],
    ["/commands","Commands"],["/automation","Automation"],["/discord","Discord"],["/trading","Trade calls"],
    ["/tickets","Tickets"],["/social","Social feeds"],["/billing","Premium"],["/moderation","Moderation"],["/audit","Audit log"]
  ];
  const activeFor=(href:string)=>href==="/dashboard" ? pathname==="/dashboard" || pathname.startsWith("/modules/") : pathname===href || pathname.startsWith(`${href}/`);
  const links=items.map(([href,label])=>`<a class="${activeFor(href)?"active":""}" href="${href}">${label}</a>`).join("");
  return `<aside class="sidebar"><a class="brand" href="/dashboard"><span>EAFC.Live</span> Control</a><nav>${links}</nav><form method="post" action="/logout"><button class="ghost full">Log out</button></form></aside>`;
}

app.use((req:any,res:any,next:any)=>{
  const originalRender=res.render.bind(res);
  res.render=(view:string,options?:any,callback?:any)=>{
    if(typeof options==="function"){callback=options;options={};}
    return req.app.render(view,{...res.locals,...(options||{})},(err:any,html:string)=>{
      if(err){if(callback)return callback(err);return next(err);}
      let output=html;
      if(output.includes('<aside class="sidebar">')){
        output=output.replace(/<aside class="sidebar">[\s\S]*?<\/aside>/,dashboardSidebar(req.path));
        if(!output.includes('/polish.css')) output=output.replace("</head>",'<link rel="stylesheet" href="/polish.css"></head>');
      }
      if(callback)return callback(null,output);
      res.send(output);
    });
  };
  void originalRender;
  next();
});

app.use("/billing",billingRouter);

async function discordToken(code:string) {
  const body=new URLSearchParams({client_id:config.clientId,client_secret:config.clientSecret,grant_type:"authorization_code",code,redirect_uri:config.redirectUri});
  const res=await fetch("https://discord.com/api/v10/oauth2/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});
  if(!res.ok) throw new Error(`Discord OAuth failed ${res.status}`);
  return res.json() as Promise<any>;
}
async function discordGet(pathname:string,token:string) {
  const res=await fetch(`https://discord.com/api/v10${pathname}`,{headers:{Authorization:`Bearer ${token}`}});
  if(!res.ok) throw new Error(`Discord API failed ${res.status}`);
  return res.json() as Promise<any>;
}
function requireAuth(req:any,res:any,next:any) { if(!req.session.user) return res.redirect("/login"); next(); }
function canManageGuild(permissionString:string|undefined) {
  try { return (BigInt(permissionString||"0") & PermissionFlagsBits.ManageGuild)===PermissionFlagsBits.ManageGuild; }
  catch { return false; }
}
async function getGuildUi() {
  const guild=client.guilds.cache.get(config.targetGuildId);
  if(!guild) return {channels:[],roles:[]};
  const channels=[...guild.channels.cache.values()].filter(c=>c.isTextBased()||c.type===4).map(c=>({id:c.id,name:c.name,type:c.type})).sort((a,b)=>a.name.localeCompare(b.name));
  const botHighest=guild.members.me?.roles.highest.position ?? 0;
  const roles=[...guild.roles.cache.values()]
    .filter(r=>r.id!==guild.id&&!r.managed&&r.position<botHighest)
    .map(r=>({id:r.id,name:r.name})).sort((a,b)=>b.name.localeCompare(a.name));
  return {channels,roles};
}

async function publishRoleMenus(cfg:any) {
  const guild=client.guilds.cache.get(config.targetGuildId);
  if(!guild) throw new Error("Bot is not connected to Discord.");
  const channelId=String(cfg?.channelId||"");
  if(!channelId) throw new Error("Choose a role selection channel first.");
  const channel=await client.channels.fetch(channelId).catch(()=>null);
  if(!channel?.isTextBased()) throw new Error("The selected role channel is not available to the bot.");
  const me=guild.members.me;
  if(!me) throw new Error("Bot member is not available in the server.");
  const permissions=(channel as any).permissionsFor?.(me);
  if(permissions && (!permissions.has(PermissionFlagsBits.ViewChannel)||!permissions.has(PermissionFlagsBits.SendMessages))) {
    throw new Error("The bot needs View Channel and Send Messages permission in the selected role channel.");
  }
  const groups=Array.isArray(cfg?.groups)?cfg.groups:[];
  if(!groups.length) throw new Error("Add at least one role group before publishing.");
  for(const group of groups){
    const buttons=(Array.isArray(group.roleIds)?group.roleIds:[]).map((id:string)=>{
      const role=guild.roles.cache.get(id);
      if(!role||role.managed||role.position>=me.roles.highest.position) return null;
      return new ButtonBuilder().setCustomId(`role:${id}`).setLabel(role.name.slice(0,80)).setStyle(ButtonStyle.Secondary);
    }).filter((b):b is ButtonBuilder=>Boolean(b));
    if(!buttons.length) continue;
    const rows:ActionRowBuilder<ButtonBuilder>[]=[];
    for(let i=0;i<buttons.length;i+=5) rows.push(new ActionRowBuilder<ButtonBuilder>().addComponents(...buttons.slice(i,i+5)));
    await (channel as TextChannel).send({
      embeds:[new EmbedBuilder().setTitle(String(group.name||"Choose roles").slice(0,256)).setDescription(Number(group.maxSelect||1)===1?"Choose one role below. Click again to remove it.":"Choose any roles that apply to you. Click again to remove a role.")],
      components:rows.slice(0,5)
    });
  }
}

app.get("/",(req,res)=>res.redirect(req.session.user?"/dashboard":"/login"));
app.get("/health",(_req,res)=>res.json({ok:true,discordReady:client.isReady(),stripeConfigured:Boolean(config.stripeSecretKey&&config.stripeWebhookSecret),time:new Date().toISOString()}));
app.get("/login",(_req,res)=>res.render("login",{clientId:config.clientId,redirectUri:config.redirectUri,guildId:config.targetGuildId}));

app.get("/auth/discord",(req,res)=>{
  const state=Math.random().toString(36).slice(2);
  req.session.oauthState=state;
  const url=new URL("https://discord.com/oauth2/authorize");
  url.searchParams.set("client_id",config.clientId);url.searchParams.set("redirect_uri",config.redirectUri);url.searchParams.set("response_type","code");url.searchParams.set("scope","identify guilds");url.searchParams.set("state",state);
  req.session.save(err=>{
    if(err) return res.status(500).send("Unable to start Discord login.");
    res.redirect(url.toString());
  });
});

app.get("/auth/discord/callback",async(req,res)=>{
  try {
    if(!req.query.code) return res.status(400).send("Missing OAuth code");
    if(!req.query.state || String(req.query.state)!==req.session.oauthState) return res.status(400).send("Invalid OAuth state.");
    delete req.session.oauthState;
    const token=await discordToken(String(req.query.code));
    const [user,guilds]=await Promise.all([discordGet("/users/@me",token.access_token),discordGet("/users/@me/guilds",token.access_token)]);
    const guild=(guilds as any[]).find(g=>g.id===config.targetGuildId);
    const allowed=config.adminIds.has(user.id)||Boolean(guild?.owner)||canManageGuild(guild?.permissions);
    if(!allowed) return res.status(403).send("You need Manage Server permission for this Discord server.");
    req.session.user={id:user.id,username:user.username,avatar:user.avatar,permissions:guild?.permissions};
    await audit(config.targetGuildId,user.id,"dashboard.login",{username:user.username});
    req.session.save(err=>{
      if(err) return res.status(500).send("Unable to save dashboard session.");
      res.redirect("/dashboard");
    });
  } catch(err) { console.error(err); res.status(500).send("Discord login failed."); }
});

app.post("/logout",(req,res)=>req.session.destroy(()=>res.redirect("/login")));

app.get("/dashboard",requireAuth,async(req,res)=>{
  const settings=await query<any>(`SELECT feature_key,enabled,config,updated_at FROM feature_settings WHERE guild_id=$1`,[config.targetGuildId]);
  const byKey=new Map(settings.map(s=>[s.feature_key,s]));
  const stats=await one<any>(`SELECT
    (SELECT count(*) FROM member_stats WHERE guild_id=$1) members_tracked,
    (SELECT count(*) FROM trade_calls WHERE guild_id=$1) trade_calls,
    (SELECT count(*) FROM tickets WHERE guild_id=$1 AND status='OPEN') open_tickets,
    (SELECT count(*) FROM social_feeds WHERE guild_id=$1 AND enabled=true) active_feeds,
    (SELECT count(*) FROM warnings WHERE guild_id=$1) warnings,
    (SELECT count(*) FROM billing_subscriptions WHERE guild_id=$1 AND status IN ('active','trialing','past_due','comped','gifted')) premium_members`,[config.targetGuildId]);
  res.render("dashboard",{user:req.session.user,modules,moduleSettings:byKey,stats:stats||{},guild:client.guilds.cache.get(config.targetGuildId)});
});

app.get("/modules/:key",requireAuth,async(req,res)=>{
  const def=moduleMap.get(req.params.key);if(!def) return res.status(404).send("Unknown module");
  const row=await one<any>(`SELECT enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=$2`,[config.targetGuildId,def.key]);
  const ui=await getGuildUi();
  res.render("module",{user:req.session.user,def,enabled:row?.enabled??true,current:{...def.defaults,...(row?.config||{})},saved:req.query.saved==="1",publishError:req.query.error?String(req.query.error):"",...ui});
});
app.post("/modules/:key",requireAuth,async(req,res)=>{
  const def=moduleMap.get(req.params.key);if(!def) return res.status(404).send("Unknown module");
  let parsed:any;try{parsed=JSON.parse(req.body.config||"{}");}catch{return res.status(400).send("Config must be valid JSON.");}
  const enabled=req.body.enabled==="on";
  await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config,updated_at) VALUES($1,$2,$3,$4::jsonb,now()) ON CONFLICT(guild_id,feature_key) DO UPDATE SET enabled=$3,config=$4::jsonb,updated_at=now()`,[config.targetGuildId,def.key,enabled,JSON.stringify(parsed)]);
  await audit(config.targetGuildId,req.session.user!.id,"feature.update",{key:def.key,enabled,config:parsed});
  if(def.key==="role_menus"&&enabled){
    try{
      await publishRoleMenus(parsed);
      await audit(config.targetGuildId,req.session.user!.id,"role_menu.publish",{channelId:parsed.channelId,groups:Array.isArray(parsed.groups)?parsed.groups.length:0});
    }catch(err:any){
      console.error("Role menu publish failed",err);
      return res.redirect(`/modules/${def.key}?error=${encodeURIComponent(err?.message||"Could not publish role menu")}`);
    }
  }
  res.redirect(`/modules/${def.key}?saved=1`);
});

app.get("/social",requireAuth,async(req,res)=>{const feeds=await query<any>(`SELECT * FROM social_feeds WHERE guild_id=$1 ORDER BY id DESC`,[config.targetGuildId]);const ui=await getGuildUi();res.render("social",{user:req.session.user,feeds,...ui,baseUrl:config.baseUrl});});
app.post("/social",requireAuth,async(req,res)=>{const provider=String(req.body.provider||"rss");const secret=provider==="webhook"?createWebhookSecret():null;await query(`INSERT INTO social_feeds(guild_id,name,provider,source,channel_id,enabled,include_keywords,exclude_keywords,mention_role_id,secret_key) VALUES($1,$2,$3,$4,$5,true,$6,$7,$8,$9)`,[config.targetGuildId,String(req.body.name||"Feed"),provider,String(req.body.source||""),String(req.body.channelId||""),String(req.body.includeKeywords||"").split(",").map((s:string)=>s.trim()).filter(Boolean),String(req.body.excludeKeywords||"").split(",").map((s:string)=>s.trim()).filter(Boolean),req.body.mentionRoleId||null,secret]);await audit(config.targetGuildId,req.session.user!.id,"social.create",{provider,name:req.body.name});res.redirect("/social");});
app.post("/social/:id/toggle",requireAuth,async(req,res)=>{await query(`UPDATE social_feeds SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);res.redirect("/social");});
app.post("/social/:id/delete",requireAuth,async(req,res)=>{await query(`DELETE FROM social_feeds WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);await audit(config.targetGuildId,req.session.user!.id,"social.delete",{id:req.params.id});res.redirect("/social");});
app.post("/hooks/social/:secret",async(req,res)=>{const ok=await deliverWebhook(req.params.secret,req.body);res.status(ok?202:404).json({ok});});

app.get("/moderation",requireAuth,async(req,res)=>{const warnings=await query<any>(`SELECT * FROM warnings WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[config.targetGuildId]);const auditRows=await query<any>(`SELECT * FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[config.targetGuildId]);res.render("moderation",{user:req.session.user,warnings,auditRows});});
app.get("/trading",requireAuth,async(req,res)=>{const calls=await query<any>(`SELECT * FROM trade_calls WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[config.targetGuildId]);res.render("trading",{user:req.session.user,calls});});
app.post("/trading/:id/status",requireAuth,async(req,res)=>{const status=String(req.body.status||"LIVE");if(!["LIVE","HIT","PROFIT","MISS","EXPIRED"].includes(status)) return res.status(400).send("Invalid status");await query(`UPDATE trade_calls SET status=$1,closed_at=CASE WHEN $1='LIVE' THEN NULL ELSE now() END WHERE id=$2 AND guild_id=$3`,[status,req.params.id,config.targetGuildId]);await audit(config.targetGuildId,req.session.user!.id,"trade.status",{id:req.params.id,status});res.redirect("/trading");});
app.get("/tickets",requireAuth,async(req,res)=>{const tickets=await query<any>(`SELECT * FROM tickets WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[config.targetGuildId]);res.render("tickets",{user:req.session.user,tickets});});
app.post("/tickets/:id/close",requireAuth,async(req,res)=>{const ticket=await one<any>(`SELECT * FROM tickets WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);if(ticket?.channel_id){const ch=await client.channels.fetch(ticket.channel_id).catch(()=>null);if(ch) await (ch as any).delete(`Ticket closed from dashboard by ${req.session.user!.username}`).catch(()=>{});}await query(`UPDATE tickets SET status='CLOSED',closed_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);await audit(config.targetGuildId,req.session.user!.id,"ticket.close",{id:req.params.id});res.redirect("/tickets");});
app.get("/audit",requireAuth,async(req,res)=>{const rows=await query<any>(`SELECT * FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 250`,[config.targetGuildId]);res.render("audit",{user:req.session.user,rows});});
