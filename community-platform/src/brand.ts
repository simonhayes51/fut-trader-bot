import { EmbedBuilder } from "discord.js";
import { one } from "./db.js";

export const BRAND = {
  name: "EAFC.Live",
  url: "https://eafc.live",
  colours: {
    primary: 0x22d3ee,
    premium: 0x8b5cf6,
    success: 0x22c55e,
    warning: 0xf59e0b,
    danger: 0xef4444,
    neutral: 0x64748b,
    coins: 0xf5b942
  }
} as const;

export type GuildBrand = {
  name: string;
  url: string;
  footerText: string;
  logoUrl: string;
  bannerUrl: string;
  colours: Record<keyof typeof BRAND.colours, number>;
};

const brandCache = new Map<string, { brand: GuildBrand; loadedAt: number }>();
const cacheMs = 60_000;

function colour(value: unknown, fallback: number) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const raw = String(value || "").trim().replace(/^#/, "");
  return /^[0-9a-f]{6}$/i.test(raw) ? parseInt(raw, 16) : fallback;
}

function text(value: unknown, fallback: string, max = 120) {
  const raw = String(value || "").trim();
  return (raw || fallback).slice(0, max);
}

function url(value: unknown, fallback = "") {
  const raw = String(value || "").trim();
  return /^https?:\/\//i.test(raw) ? raw.slice(0, 500) : fallback;
}

export function clearGuildBrandCache(guildId?: string) {
  if (guildId) brandCache.delete(guildId);
  else brandCache.clear();
}

export function defaultGuildBrand(): GuildBrand {
  return {
    name: BRAND.name,
    url: BRAND.url,
    footerText: `${BRAND.name} • FC27 Community`,
    logoUrl: process.env.SYSTEM_LOGO_URL || "",
    bannerUrl: process.env.SYSTEM_BANNER_URL || "",
    colours: { ...BRAND.colours }
  };
}

export async function getGuildBrand(guildId?: string | null): Promise<GuildBrand> {
  if (!guildId) return defaultGuildBrand();
  const cached = brandCache.get(guildId);
  if (cached && Date.now() - cached.loadedAt < cacheMs) return cached.brand;

  const row = await one<{ settings: any }>(`SELECT settings FROM guild_settings WHERE guild_id=$1`, [guildId]);
  const settings = row?.settings || {};
  const cfg = settings.brand || {};
  const base = defaultGuildBrand();
  const brand: GuildBrand = {
    name: text(cfg.name, base.name),
    url: url(cfg.url, base.url),
    footerText: text(cfg.footerText, cfg.name ? `${String(cfg.name).trim()} • FC27 Community` : base.footerText),
    logoUrl: url(cfg.logoUrl, base.logoUrl),
    bannerUrl: url(cfg.bannerUrl, base.bannerUrl),
    colours: {
      primary: colour(cfg.primaryColour, base.colours.primary),
      premium: colour(cfg.premiumColour, base.colours.premium),
      success: colour(cfg.successColour, base.colours.success),
      warning: colour(cfg.warningColour, base.colours.warning),
      danger: colour(cfg.dangerColour, base.colours.danger),
      neutral: colour(cfg.neutralColour, base.colours.neutral),
      coins: colour(cfg.coinsColour, base.colours.coins)
    }
  };
  brandCache.set(guildId, { brand, loadedAt: Date.now() });
  return brand;
}

function applyBrand(e: EmbedBuilder, brand: GuildBrand, options: { system?: boolean; banner?: boolean } = {}) {
  e.setFooter({ text: options.system ? `${brand.name} | ${new Date().toLocaleString("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}` : brand.footerText });
  if (brand.logoUrl) e.setThumbnail(brand.logoUrl);
  if (options.banner && brand.bannerUrl) e.setImage(brand.bannerUrl);
  return e;
}

export function brandEmbed(title:string, description?:string, colour:number=BRAND.colours.primary) {
  const e=new EmbedBuilder()
    .setColor(colour)
    .setTitle(title)
    .setFooter({text:"EAFC.Live • FC27 Community"})
    .setTimestamp();
  if(description) e.setDescription(description);
  return e;
}

export async function guildEmbed(guildId:string|undefined|null,title:string,description?:string,colour?:number,options:{banner?:boolean}={}) {
  const brand=await getGuildBrand(guildId);
  const e=new EmbedBuilder()
    .setColor(colour ?? brand.colours.primary)
    .setTitle(title)
    .setTimestamp();
  if(description) e.setDescription(description);
  return applyBrand(e,brand,{banner:options.banner});
}

export function systemEmbed(title:string, description?:string, colour:number=BRAND.colours.primary) {
  const e=brandEmbed(title,description,colour).setFooter({text:`${BRAND.name} | ${new Date().toLocaleString("en-GB",{timeZone:"Europe/London",day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})}`});
  if(process.env.SYSTEM_LOGO_URL)e.setThumbnail(process.env.SYSTEM_LOGO_URL);
  if(process.env.SYSTEM_BANNER_URL)e.setImage(process.env.SYSTEM_BANNER_URL);
  return e;
}

export async function guildSystemEmbed(guildId:string|undefined|null,title:string,description?:string,colour?:number,options:{banner?:boolean}={}) {
  const brand=await getGuildBrand(guildId);
  const e=new EmbedBuilder()
    .setColor(colour ?? brand.colours.primary)
    .setTitle(title)
    .setTimestamp();
  if(description) e.setDescription(description);
  return applyBrand(e,brand,{system:true,banner:options.banner ?? true});
}

export function compactNumber(value:number|bigint) {
  return Number(value||0).toLocaleString("en-GB");
}

export function progressBar(current:number,target:number,width=10) {
  const safeTarget=Math.max(1,target);
  const pct=Math.max(0,Math.min(1,current/safeTarget));
  const filled=Math.round(pct*width);
  return `${"▰".repeat(filled)}${"▱".repeat(Math.max(0,width-filled))}`;
}
