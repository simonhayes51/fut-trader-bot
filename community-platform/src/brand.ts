import { EmbedBuilder } from "discord.js";

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

export function brandEmbed(title:string, description?:string, colour:number=BRAND.colours.primary) {
  const e=new EmbedBuilder()
    .setColor(colour)
    .setTitle(title)
    .setFooter({text:"EAFC.Live • FC27 Community"})
    .setTimestamp();
  if(description) e.setDescription(description);
  return e;
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
