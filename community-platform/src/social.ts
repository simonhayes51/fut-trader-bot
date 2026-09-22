import crypto from "node:crypto";
import { XMLParser } from "fast-xml-parser";
import { TextChannel } from "discord.js";
import { client } from "./bot.js";
import { config } from "./config.js";
import { one, query } from "./db.js";
import { brandEmbed, BRAND } from "./brand.js";

type Feed = {
  id:number; guild_id:string; name:string; provider:string; source:string; channel_id:string;
  include_keywords:string[]; exclude_keywords:string[]; mention_role_id:string|null; last_item_id:string|null;
  secret_key:string|null; config:Record<string,any>;
};

const parser=new XMLParser({ignoreAttributes:false,attributeNamePrefix:"@"});

function arr<T>(v:T|T[]|undefined):T[] { return v===undefined?[]:Array.isArray(v)?v:[v]; }
function allowed(feed:Feed,text:string) {
  const value=text.toLowerCase();
  if(feed.include_keywords?.length && !feed.include_keywords.some(k=>value.includes(k.toLowerCase()))) return false;
  if(feed.exclude_keywords?.some(k=>value.includes(k.toLowerCase()))) return false;
  return true;
}
async function post(feed:Feed,item:{id:string;title:string;url?:string;description?:string;author?:string;image?:string}) {
  if(!allowed(feed,`${item.title} ${item.description||""}`)) return;
  const ch=await client.channels.fetch(feed.channel_id).catch(()=>null);
  if(!ch?.isTextBased()) return;
  const embed=brandEmbed(item.title.slice(0,256),undefined,BRAND.colours.primary).setAuthor({name:item.author||feed.name});
  if(item.url) embed.setURL(item.url);
  if(item.description) embed.setDescription(item.description.slice(0,3900));
  if(item.image) embed.setImage(item.image);
  const content=feed.mention_role_id?`<@&${feed.mention_role_id}>`:"";
  await (ch as TextChannel).send({content,embeds:[embed],allowedMentions:{roles:feed.mention_role_id?[feed.mention_role_id]:[]}});
  await query(`UPDATE social_feeds SET last_item_id=$1,updated_at=now() WHERE id=$2`,[item.id,feed.id]);
}

async function pollRss(feed:Feed) {
  const res=await fetch(feed.source,{headers:{"user-agent":"EAFCLiveCommunityBot/1.0"}});
  if(!res.ok) throw new Error(`${feed.name}: HTTP ${res.status}`);
  const xml=parser.parse(await res.text());
  const raw=arr(xml?.rss?.channel?.item ?? xml?.feed?.entry);
  if(!raw.length) return;
  const items=raw.slice(0,10).map((x:any)=>({
    id:String(x.guid?.["#text"]||x.guid||x.id||x.link?.["@href"]||x.link||x.title),
    title:String(x.title?.["#text"]||x.title||"New post"),
    url:String(x.link?.["@href"]||x.link||""),
    description:String(x.description||x.summary||x["content:encoded"]||"").replace(/<[^>]+>/g," ").replace(/\s+/g," ").trim(),
    author:String(x.author?.name||x["dc:creator"]||feed.name)
  }));
  const unseen=feed.last_item_id ? items.slice(0,Math.max(0,items.findIndex(i=>i.id===feed.last_item_id))).reverse() : items.slice(0,1);
  for(const item of unseen) await post(feed,item);
}

async function pollX(feed:Feed) {
  if(!config.xBearerToken) return;
  let userId=feed.config?.userId as string|undefined;
  if(!userId) {
    const username=feed.source.replace(/^@/,"");
    const r=await fetch(`https://api.x.com/2/users/by/username/${encodeURIComponent(username)}`,{headers:{Authorization:`Bearer ${config.xBearerToken}`}});
    const json:any=await r.json();
    userId=json?.data?.id;
    if(!userId) return;
    feed.config={...feed.config,userId};
    await query(`UPDATE social_feeds SET config=$1::jsonb WHERE id=$2`,[JSON.stringify(feed.config),feed.id]);
  }
  const r=await fetch(`https://api.x.com/2/users/${userId}/tweets?max_results=5&exclude=retweets,replies&tweet.fields=created_at`,{headers:{Authorization:`Bearer ${config.xBearerToken}`}});
  if(!r.ok) return;
  const json:any=await r.json();
  const tweets=arr<any>(json?.data);
  const unseen=feed.last_item_id?tweets.slice(0,Math.max(0,tweets.findIndex(t=>t.id===feed.last_item_id))).reverse():tweets.slice(0,1);
  for(const t of unseen) await post(feed,{id:t.id,title:`New post from @${feed.source.replace(/^@/,"")}`,description:t.text,url:`https://x.com/${feed.source.replace(/^@/,"")}/status/${t.id}`,author:`@${feed.source.replace(/^@/,"")}`});
}

export async function pollSocialFeeds() {
  const feeds=await query<Feed>(`SELECT * FROM social_feeds WHERE guild_id=$1 AND enabled=true AND provider <> 'webhook' ORDER BY id`,[config.targetGuildId]);
  for(const feed of feeds) {
    try {
      if(["rss","reddit","youtube"].includes(feed.provider)) await pollRss(feed);
      if(feed.provider==="x") await pollX(feed);
    } catch(err) { console.error("Social feed error",feed.name,err); }
  }
}

export function createWebhookSecret() { return crypto.randomBytes(24).toString("hex"); }

export async function deliverWebhook(secret:string,payload:any) {
  const feed=await one<Feed>(`SELECT * FROM social_feeds WHERE secret_key=$1 AND enabled=true AND provider='webhook'`,[secret]);
  if(!feed) return false;
  const webhookGroup=(feed.source||feed.name||"").trim();
  const feeds=webhookGroup
    ? await query<Feed>(`SELECT * FROM social_feeds WHERE provider='webhook' AND enabled=true AND COALESCE(NULLIF(btrim(source),''),btrim(name))=$1 ORDER BY id`,[webhookGroup])
    : [feed];
  const id=String(payload.id||payload.url||Date.now());
  const item={
    id,
    title:String(payload.title||payload.text||"New update"),
    description:String(payload.description||payload.text||""),
    url:payload.url?String(payload.url):undefined,
    author:payload.author?String(payload.author):feed.name,
    image:payload.image?String(payload.image):undefined
  };
  for(const target of feeds) await post(target,item);
  return true;
}
