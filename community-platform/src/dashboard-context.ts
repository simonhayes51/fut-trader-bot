import { PermissionFlagsBits } from "discord.js";
import { client } from "./bot.js";
import { config } from "./config.js";

export type DashboardGuild = {
  id:string;
  name:string;
  icon?:string|null;
  owner?:boolean;
  permissions?:string;
};

export type DashboardUser = {
  id:string;
  username:string;
  avatar?:string;
  permissions?:string;
  guilds?:DashboardGuild[];
};

export function canManageGuild(permissionString:string|undefined) {
  try { return (BigInt(permissionString||"0") & PermissionFlagsBits.ManageGuild)===PermissionFlagsBits.ManageGuild; }
  catch { return false; }
}

export function manageableGuildsFromDiscord(userId:string,guilds:any[]) {
  const admin=config.adminIds.has(userId);
  const botGuilds=new Map([...client.guilds.cache.values()].map(g=>[g.id,g]));
  const allowed=(guilds||[])
    .filter(g=>botGuilds.has(g.id)&&(admin||Boolean(g.owner)||canManageGuild(g.permissions)))
    .map(g=>({id:String(g.id),name:String(g.name||botGuilds.get(g.id)?.name||"Discord server"),icon:g.icon||null,owner:Boolean(g.owner),permissions:g.permissions}));
  if(admin) {
    for(const g of botGuilds.values()) {
      if(!allowed.some(x=>x.id===g.id)) allowed.push({id:g.id,name:g.name,icon:g.icon||null,owner:false,permissions:"0"});
    }
  }
  return allowed.sort((a,b)=>a.name.localeCompare(b.name));
}

export function dashboardGuilds(req:any) {
  const user=req.session?.user;
  const sessionGuilds:DashboardGuild[]=user?.guilds||[];
  const admin=Boolean(user?.id&&config.adminIds.has(user.id));
  if(admin) {
    const byId=new Map<string,DashboardGuild>();
    for(const g of sessionGuilds) if(client.guilds.cache.has(g.id)) byId.set(g.id,g);
    for(const g of client.guilds.cache.values()) byId.set(g.id,{id:g.id,name:g.name,icon:g.icon||null,owner:false,permissions:"0"});
    return [...byId.values()].sort((a,b)=>a.name.localeCompare(b.name));
  }
  return sessionGuilds.filter(g=>client.guilds.cache.has(g.id)).sort((a,b)=>a.name.localeCompare(b.name));
}

export function selectedGuildId(req:any) {
  const guilds=dashboardGuilds(req);
  const selected=String(req.session?.selectedGuildId||"");
  if(selected&&guilds.some(g=>g.id===selected)&&client.guilds.cache.has(selected)) return selected;
  const fallback=guilds.find(g=>g.id===config.targetGuildId&&client.guilds.cache.has(g.id))||guilds.find(g=>client.guilds.cache.has(g.id));
  if(fallback) {
    req.session.selectedGuildId=fallback.id;
    return fallback.id;
  }
  return config.targetGuildId;
}

export function selectedGuild(req:any) {
  return client.guilds.cache.get(selectedGuildId(req))||null;
}

export function requireSelectedGuild(req:any,res:any,next:any) {
  if(!req.session?.user) return res.redirect("/login");
  const guild=selectedGuild(req);
  if(!guild) return res.status(503).send("The bot is not connected to the selected Discord server.");
  next();
}

export async function guildUi(req:any) {
  const guild=selectedGuild(req);
  if(!guild) return {guild:null,channels:[],roles:[],members:[]};
  const fetched=await guild.members.fetch().catch(()=>guild.members.cache);
  const botHighest=guild.members.me?.roles.highest.position??0;
  return {
    guild,
    channels:[...guild.channels.cache.values()].map((c:any)=>({id:c.id,name:c.name,type:c.type})).sort((a,b)=>a.name.localeCompare(b.name)),
    roles:[...guild.roles.cache.values()].filter(r=>r.id!==guild.id&&!r.managed&&r.position<botHighest).sort((a,b)=>b.position-a.position).map(r=>({id:r.id,name:r.name})),
    members:[...fetched.values()].filter((m:any)=>!m.user.bot).sort((a,b)=>a.displayName.localeCompare(b.displayName)).map((m:any)=>({id:m.id,name:m.displayName,username:m.user.username,joinedAt:m.joinedAt}))
  };
}
