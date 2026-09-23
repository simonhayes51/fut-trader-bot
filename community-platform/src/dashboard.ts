import express from "express";
import session from "express-session";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PermissionFlagsBits } from "discord.js";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, one, query } from "./db.js";
import { moduleMap, modules } from "./modules.js";
import { createWebhookSecret, deliverWebhook, deliverWebhookGroup } from "./social.js";
import { billingRouter } from "./billing-dashboard.js";
import { PostgresSessionStore } from "./session-store.js";
import { clearGuildBrandCache, defaultGuildBrand } from "./brand.js";
import { DashboardGuild, dashboardGuilds, guildUi, manageableGuildsFromDiscord, refreshDashboardGuilds, requireSelectedGuild, selectedGuild, selectedGuildId } from "./dashboard-context.js";
import { publishRoleMenusForGuild } from "./role-menu-publisher.js";
import { publishTicketPanelForGuild } from "./ticket-panel-publisher.js";

declare module "express-session" {
  interface SessionData { user?: { id:string; username:string; avatar?:string; permissions?:string; guilds?:DashboardGuild[] }; oauthState?: string; selectedGuildId?: string; guildRefreshAt?: number; }
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

app.use(async(req:any,_res:any,next:any)=>{
  try { if(req.session?.user) await refreshDashboardGuilds(req); }
  catch(err) { console.error("Dashboard guild refresh failed",err); }
  next();
});

function dashboardSidebar(pathname:string,user?:{username?:string;avatar?:string;guilds?:DashboardGuild[]},selectedId?:string) {
  const groups:Array<{label:string;items:Array<[string,string,string]>}>=[
    {label:"Overview",items:[["/control","⌂","Home"],["/control/members","◎","Members"],["/control/insights","▦","Insights"]]},
    {label:"Experience",items:[["/control/onboarding","◌","Onboarding"],["/control/community","◇","Community"],["/control/kudos","👏","Kudos & retention"],["/control/rewards","¤","Rewards"]]},
    {label:"Content & growth",items:[["/control/studio","✦","Message studio"],["/control/automation","↻","Automation"],["/control/growth","↗","Growth & partners"],["/discord","♢","Discord tools"]]},
    {label:"Operations",items:[["/control/security","◉","Security & health"],["/control/safety","⊘","Safety & support"],["/billing","◆","Premium"]]},
    {label:"Configuration",items:[["/branding","◈","Branding"],["/control/settings","⚙","Features"],["/commands","⌘","Command access"],["/audit","≡","Audit log"],["/invite","+","Add bot"]]}
  ];
  const activeFor=(href:string)=>href==="/control"?pathname==="/control":href==="/branding"?pathname==="/branding"||pathname==="/modules/server_branding":pathname===href||pathname.startsWith(`${href}/`);
  const nav=groups.map(group=>`<div class="nav-group"><div class="nav-label">${group.label}</div>${group.items.map(([href,icon,label])=>`<a class="${activeFor(href)?"active":""}" href="${href}"><span class="nav-icon">${icon}</span><span>${label}</span></a>`).join("")}</div>`).join("");
  const initial=(user?.username||"A").slice(0,1).toUpperCase();
  const guilds=user?.guilds||[];
  const onlyGuild=guilds[0];
  const addServerLink=`<a class="server-add-link" href="/invite">Add bot to another server</a>`;
  const selector=guilds.length>1?`<form class="server-switcher" method="post" action="/servers/select">
      <label>Server</label>
      <select name="guildId" onchange="this.form.submit()">${guilds.map(g=>`<option value="${g.id}" ${g.id===selectedId?"selected":""}>${g.name}</option>`).join("")}</select>
      ${addServerLink}
    </form>`:onlyGuild?`<div class="server-switcher readonly"><label>Server</label><strong>${onlyGuild.name}</strong>${addServerLink}</div>`:`<div class="server-switcher readonly"><label>Server</label>${addServerLink}</div>`;
  return `<aside class="sidebar">
    <a class="brand" href="/control"><span class="brand-mark">E</span><span class="brand-copy"><b>EAFC.Live</b><small>Discord Control</small></span></a>
    ${selector}
    <nav>${nav}</nav>
    <div class="sidebar-footer"><div class="admin-chip"><span class="admin-avatar">${initial}</span><span><b>${user?.username||"Administrator"}</b><small>Administrator</small></span></div><form method="post" action="/logout"><button class="icon-button" title="Log out">↪</button></form></div>
  </aside>`;
}

app.use((req:any,res:any,next:any)=>{
  const originalRender=res.render.bind(res);
  res.render=(view:string,options?:any,callback?:any)=>{
    if(typeof options==="function"){callback=options;options={};}
    return req.app.render(view,{...res.locals,...(options||{})},(err:any,html:string)=>{
      if(err){if(callback)return callback(err);return next(err);}
      let output=html;
      if(output.includes('<aside class="sidebar">')){
        const user=options?.user||req.session?.user;
        output=output.replace(/<aside class="sidebar">[\s\S]*?<\/aside>/,dashboardSidebar(req.path,user?{...user,guilds:dashboardGuilds(req)}:user,selectedGuildId(req)));
        if(output.includes('/style.css')&&!output.includes('/polish.css')) output=output.replace("</head>",'<link rel="stylesheet" href="/polish.css"></head>');
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

async function publishRoleMenus(req:any,cfg:any) {
  const guild=selectedGuild(req);
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
  const posted=await publishRoleMenusForGuild(guild,channel,groups);
  if(!posted) throw new Error("No assignable roles are selected. Move the bot role above the member roles you want it to manage.");
}

async function publishTicketPanel(req:any,cfg:any) {
  const guild=selectedGuild(req);
  if(!guild) throw new Error("Bot is not connected to Discord.");
  const channelId=String(cfg?.panelChannelId||"");
  if(!channelId) throw new Error("Choose a ticket panel channel first.");
  const channel=await client.channels.fetch(channelId).catch(()=>null);
  if(!channel?.isTextBased()) throw new Error("The selected ticket panel channel is not available to the bot.");
  const me=guild.members.me;
  if(!me) throw new Error("Bot member is not available in the server.");
  const permissions=(channel as any).permissionsFor?.(me);
  if(permissions && (!permissions.has(PermissionFlagsBits.ViewChannel)||!permissions.has(PermissionFlagsBits.SendMessages))) {
    throw new Error("The bot needs View Channel and Send Messages permission in the selected ticket panel channel.");
  }
  if(!cfg?.categoryId) throw new Error("Choose a ticket category before publishing.");
  if(!Array.isArray(cfg?.staffRoleIds)||!cfg.staffRoleIds.length) throw new Error("Choose at least one ticket staff role before publishing.");
  return publishTicketPanelForGuild(guild.id,channel,Array.isArray(cfg?.types)?cfg.types:[]);
}

app.get("/",(req,res)=>res.redirect(req.session.user?"/control":"/login"));
app.get("/health",async(_req,res)=>{
  let economy:any={ready:false};
  try{
    const [season,queue,pending]=await Promise.all([
      one<any>(`SELECT id,name,ends_at FROM economy_seasons WHERE guild_id=$1 AND active=true AND ends_at>now() ORDER BY starts_at DESC LIMIT 1`,[config.targetGuildId]),
      one<any>(`SELECT count(*) FILTER(WHERE status IN ('PENDING','FAILED')) waiting,count(*) FILTER(WHERE status='FAILED') failed FROM economy_event_queue WHERE guild_id=$1`,[config.targetGuildId]),
      one<any>(`SELECT count(*) total FROM store_redemptions WHERE guild_id=$1 AND status='PENDING'`,[config.targetGuildId])
    ]);
    economy={ready:true,season:season?.name||null,seasonEndsAt:season?.ends_at||null,queueWaiting:Number(queue?.waiting||0),queueFailed:Number(queue?.failed||0),pendingRedemptions:Number(pending?.total||0)};
  }catch(err:any){economy={ready:false,error:String(err?.message||err).slice(0,200)};}
  res.status(economy.ready?200:503).json({ok:economy.ready,discordReady:client.isReady(),stripeConfigured:Boolean(config.stripeSecretKey&&config.stripeWebhookSecret),economy,time:new Date().toISOString()});
});
app.get("/login",(_req,res)=>res.render("login",{clientId:config.clientId,redirectUri:config.redirectUri,guildId:config.targetGuildId}));

function discordBotInviteUrl() {
  const url=new URL("https://discord.com/oauth2/authorize");
  url.searchParams.set("client_id",config.clientId);
  url.searchParams.set("scope","bot applications.commands");
  url.searchParams.set("permissions",config.botInvitePermissions);
  return url.toString();
}

app.get("/invite",(_req,res)=>res.redirect(discordBotInviteUrl()));

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
    const manageable=manageableGuildsFromDiscord(user.id,guilds as any[]);
    if(!manageable.length) return res.status(403).send("You need Manage Server permission in a Discord server where this bot is installed.");
    const preferred=(manageable.find(g=>g.id===req.session.selectedGuildId)||manageable.find(g=>g.id===config.targetGuildId)||manageable[0])!;
    req.session.selectedGuildId=preferred.id;
    req.session.user={id:user.id,username:user.username,avatar:user.avatar,permissions:preferred.permissions,guilds:manageable};
    await refreshDashboardGuilds(req,true);
    await audit(preferred.id,user.id,"dashboard.login",{username:user.username});
    req.session.save(err=>{
      if(err) return res.status(500).send("Unable to save dashboard session.");
      res.redirect("/control");
    });
  } catch(err) { console.error(err); res.status(500).send("Discord login failed."); }
});

app.post("/logout",(req,res)=>req.session.destroy(()=>res.redirect("/login")));
app.post("/servers/select",requireAuth,(req:any,res)=>{
  const guildId=String(req.body.guildId||"");
  const allowed=dashboardGuilds(req).some((g:DashboardGuild)=>g.id===guildId);
  if(allowed&&client.guilds.cache.has(guildId)) req.session.selectedGuildId=guildId;
  res.redirect(String(req.headers.referer||"/control"));
});

app.get("/dashboard",requireAuth,(_req,res)=>res.redirect("/control"));
app.get("/branding",requireSelectedGuild,(_req,res)=>res.redirect("/modules/server_branding"));

app.use(["/modules","/social","/moderation","/trading","/tickets","/audit"],requireSelectedGuild);

app.get("/modules/:key",requireAuth,async(req,res)=>{
  const def=moduleMap.get(req.params.key);if(!def) return res.status(404).send("Unknown module");
  const gid=selectedGuildId(req);
  if(def.key==="server_branding"){
    const row=await one<any>(`SELECT settings FROM guild_settings WHERE guild_id=$1`,[gid]);
    const brand={...defaultGuildBrand(),...(row?.settings?.brand||{})};
    const ui=await guildUi(req);
    const savedBrand=row?.settings?.brand||{};
    const discordIconUrl=ui.guild?.iconURL({extension:"png",size:512})||"";
    const current={...def.defaults,...brand,logoUrl:savedBrand.logoUrl||discordIconUrl,botNickname:savedBrand.botNickname||ui.guild?.members.me?.nickname||""};
    return res.render("module",{user:req.session.user,def,enabled:true,current,saved:req.query.saved==="1",publishError:req.query.error?String(req.query.error):"",discordIconUrl,...ui});
  }
  const row=await one<any>(`SELECT enabled,config FROM feature_settings WHERE guild_id=$1 AND feature_key=$2`,[gid,def.key]);
  const ui=await guildUi(req);
  res.render("module",{user:req.session.user,def,enabled:row?.enabled??true,current:{...def.defaults,...(row?.config||{})},saved:req.query.saved==="1",publishError:req.query.error?String(req.query.error):"",...ui});
});
app.post("/modules/:key",requireAuth,async(req,res)=>{
  const def=moduleMap.get(req.params.key);if(!def) return res.status(404).send("Unknown module");
  const gid=selectedGuildId(req);
  let parsed:any;try{parsed=JSON.parse(req.body.config||"{}");}catch{return res.status(400).send("Config must be valid JSON.");}
  const enabled=req.body.enabled==="on";
  if(def.key==="server_branding"){
    const clean={
      name:String(parsed.name||"").trim(),
      botNickname:String(parsed.botNickname||"").trim().slice(0,32),
      url:String(parsed.url||"").trim(),
      footerText:String(parsed.footerText||"").trim(),
      logoUrl:String(parsed.logoUrl||"").trim(),
      bannerUrl:String(parsed.bannerUrl||"").trim(),
      primaryColour:String(parsed.primaryColour||"").trim(),
      premiumColour:String(parsed.premiumColour||"").trim(),
      successColour:String(parsed.successColour||"").trim(),
      warningColour:String(parsed.warningColour||"").trim(),
      dangerColour:String(parsed.dangerColour||"").trim(),
      neutralColour:String(parsed.neutralColour||"").trim(),
      coinsColour:String(parsed.coinsColour||"").trim()
    };
    await query(`INSERT INTO guild_settings(guild_id,settings,updated_at) VALUES($1,jsonb_build_object('brand',$2::jsonb),now())
      ON CONFLICT(guild_id) DO UPDATE SET settings=jsonb_set(COALESCE(guild_settings.settings,'{}'::jsonb),'{brand}',$2::jsonb,true),updated_at=now()`,[gid,JSON.stringify(clean)]);
    clearGuildBrandCache(gid);
    await audit(gid,req.session.user!.id,"brand.update",{brand:clean});
    if(clean.botNickname){
      const guild=selectedGuild(req);
      try{
        await guild?.members.me?.setNickname(clean.botNickname,`Branding updated by ${req.session.user!.username}`);
      }catch(err:any){
        console.error("Bot nickname update failed",err);
        return res.redirect(`/modules/${def.key}?saved=1&error=${encodeURIComponent("Saved branding, but I could not change the bot nickname. Check the bot role has permission and sits high enough.")}`);
      }
    }
    return res.redirect(`/modules/${def.key}?saved=1`);
  }
  await query(`INSERT INTO feature_settings(guild_id,feature_key,enabled,config,updated_at) VALUES($1,$2,$3,$4::jsonb,now()) ON CONFLICT(guild_id,feature_key) DO UPDATE SET enabled=$3,config=$4::jsonb,updated_at=now()`,[gid,def.key,enabled,JSON.stringify(parsed)]);
  await audit(gid,req.session.user!.id,"feature.update",{key:def.key,enabled,config:parsed});
  if(def.key==="role_menus"&&enabled){
    try{
      await publishRoleMenus(req,parsed);
      await audit(gid,req.session.user!.id,"role_menu.publish",{channelId:parsed.channelId,groups:Array.isArray(parsed.groups)?parsed.groups.length:0});
    }catch(err:any){
      console.error("Role menu publish failed",err);
      return res.redirect(`/modules/${def.key}?error=${encodeURIComponent(err?.message||"Could not publish role menu")}`);
    }
  }
  if(def.key==="tickets"&&enabled){
    try{
      const msg=await publishTicketPanel(req,parsed);
      await audit(gid,req.session.user!.id,"ticket_panel.publish",{channelId:parsed.panelChannelId,messageId:msg.id});
    }catch(err:any){
      console.error("Ticket panel publish failed",err);
      return res.redirect(`/modules/${def.key}?error=${encodeURIComponent(err?.message||"Could not publish ticket panel")}`);
    }
  }
  res.redirect(`/modules/${def.key}?saved=1`);
});

app.get("/social",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const feeds=await query<any>(`SELECT * FROM social_feeds WHERE guild_id=$1 ORDER BY id DESC`,[gid]);const ui=await guildUi(req);res.render("social",{user:req.session.user,feeds,...ui,baseUrl:config.baseUrl});});
app.post("/social",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const selectedProvider=String(req.body.provider||"rss");const provider=selectedProvider==="eafc_leaks"?"webhook":selectedProvider;const source=selectedProvider==="eafc_leaks"?"EAFC.Live leaks":String(req.body.source||"");const name=selectedProvider==="eafc_leaks"?"EAFC.Live leak feed":String(req.body.name||"Feed");const secret=provider==="webhook"?createWebhookSecret():null;await query(`INSERT INTO social_feeds(guild_id,name,provider,source,channel_id,enabled,include_keywords,exclude_keywords,mention_role_id,secret_key) VALUES($1,$2,$3,$4,$5,true,$6,$7,$8,$9)`,[gid,name,provider,source,String(req.body.channelId||""),String(req.body.includeKeywords||"").split(",").map((s:string)=>s.trim()).filter(Boolean),String(req.body.excludeKeywords||"").split(",").map((s:string)=>s.trim()).filter(Boolean),req.body.mentionRoleId||null,secret]);await audit(gid,req.session.user!.id,"social.create",{provider:selectedProvider,name});res.redirect("/social");});
app.post("/social/:id/toggle",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);await query(`UPDATE social_feeds SET enabled=NOT enabled,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,gid]);res.redirect("/social");});
app.post("/social/:id/delete",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);await query(`DELETE FROM social_feeds WHERE id=$1 AND guild_id=$2`,[req.params.id,gid]);await audit(gid,req.session.user!.id,"social.delete",{id:req.params.id});res.redirect("/social");});
app.post("/hooks/social/:secret",async(req,res)=>{const ok=await deliverWebhook(req.params.secret,req.body);res.status(ok?202:404).json({ok});});
app.post("/hooks/social/eafc-leaks/:secret",async(req,res)=>{if(!config.socialWebhookSecret||req.params.secret!==config.socialWebhookSecret) return res.status(404).json({ok:false});const ok=await deliverWebhookGroup("EAFC.Live leaks",req.body);res.status(ok?202:404).json({ok});});

app.get("/moderation",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const warnings=await query<any>(`SELECT * FROM warnings WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[gid]);const auditRows=await query<any>(`SELECT * FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[gid]);res.render("moderation",{user:req.session.user,warnings,auditRows});});
app.get("/trading",requireAuth,(_req,res)=>res.redirect("/control/engagement"));
app.post("/trading/:id/status",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const status=String(req.body.status||"LIVE");if(!["LIVE","HIT","PROFIT","MISS","EXPIRED"].includes(status)) return res.status(400).send("Invalid status");await query(`UPDATE trade_calls SET status=$1,closed_at=CASE WHEN $1='LIVE' THEN NULL ELSE now() END WHERE id=$2 AND guild_id=$3`,[status,req.params.id,gid]);await audit(gid,req.session.user!.id,"trade.status",{id:req.params.id,status});res.redirect("/trading");});
app.get("/tickets",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const tickets=await query<any>(`SELECT * FROM tickets WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 100`,[gid]);res.render("tickets",{user:req.session.user,tickets});});
app.post("/tickets/:id/close",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const ticket=await one<any>(`SELECT * FROM tickets WHERE id=$1 AND guild_id=$2`,[req.params.id,gid]);if(ticket?.channel_id){const ch=await client.channels.fetch(ticket.channel_id).catch(()=>null);if(ch) await (ch as any).delete(`Ticket closed from dashboard by ${req.session.user!.username}`).catch(()=>{});}await query(`UPDATE tickets SET status='CLOSED',closed_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,gid]);await audit(gid,req.session.user!.id,"ticket.close",{id:req.params.id});res.redirect("/tickets");});
app.get("/audit",requireAuth,async(req,res)=>{const gid=selectedGuildId(req);const rows=await query<any>(`SELECT * FROM audit_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 250`,[gid]);res.render("audit",{user:req.session.user,rows});});
