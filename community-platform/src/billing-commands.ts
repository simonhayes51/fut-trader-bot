import { ActionRowBuilder, AutocompleteInteraction, ButtonBuilder, ButtonStyle, ChatInputCommandInteraction, Client, SlashCommandBuilder } from "discord.js";
import { createCheckout, createPortal, getMemberBilling, listPlans, reconcileMemberBilling } from "./billing.js";
import { getFeature, query } from "./db.js";
import { guildEmbed, BRAND } from "./brand.js";

export const billingCommandData = [
  new SlashCommandBuilder().setName("premium").setDescription("View premium plans or subscribe")
    .addStringOption(o=>o.setName("plan").setDescription("Choose a premium plan").setAutocomplete(true))
    .addStringOption(o=>o.setName("referral").setDescription("Choose a referral code (optional)").setAutocomplete(true)),
  new SlashCommandBuilder().setName("subscription").setDescription("View or manage your premium subscription")
].map(c=>c.toJSON());

const activeStatuses=new Set(["active","trialing","past_due","unpaid","paused","comped","gifted"]);

async function memberSubscription(guildId:string,userId:string) {
  let sub=await getMemberBilling(guildId,userId);
  if(!sub) {
    try { sub=await reconcileMemberBilling(guildId,userId); }
    catch(err) { console.error("Stripe reconciliation failed",err); }
  }
  return sub;
}

export async function handleBillingAutocomplete(i:AutocompleteInteraction) {
  if(i.commandName!=="premium" || !i.guildId) return false;

  const focused=i.options.getFocused(true);
  const search=String(focused.value||"").toLowerCase();

  if(focused.name==="plan") {
    const plans=await listPlans(i.guildId,true);
    const choices=plans
      .filter(p=>!search || p.name.toLowerCase().includes(search) || p.slug.toLowerCase().includes(search))
      .slice(0,25)
      .map(p=>({name:p.name.slice(0,100),value:p.slug}));
    await i.respond(choices);
    return true;
  }

  if(focused.name==="referral") {
    const refs=await query<{code:string;owner_discord_user_id:string|null}>(
      `SELECT code,owner_discord_user_id FROM referral_codes WHERE guild_id=$1 AND active=true ORDER BY code LIMIT 100`,
      [i.guildId]
    );
    const choices=refs
      .filter(r=>!search || r.code.toLowerCase().includes(search))
      .slice(0,25)
      .map(r=>({name:r.code.slice(0,100),value:r.code}));
    await i.respond(choices);
    return true;
  }

  await i.respond([]);
  return true;
}

export async function handleBillingCommand(_client:Client,i:ChatInputCommandInteraction) {
  if(!i.guildId) return false;
  if(!["premium","subscription"].includes(i.commandName)) return false;
  const feature=await getFeature(i.guildId,"premium_billing",{});
  if(!feature.enabled) {
    await i.reply({content:"Premium memberships are currently disabled.",ephemeral:true});
    return true;
  }

  if(i.commandName==="premium") {
    const existing=await memberSubscription(i.guildId,i.user.id);
    if(existing && activeStatuses.has(String(existing.status))) {
      let portal="";
      try { portal=await createPortal(i.guildId,i.user.id); } catch {}
      const row=new ActionRowBuilder<ButtonBuilder>();
      if(portal) row.addComponents(new ButtonBuilder().setLabel("Manage subscription").setStyle(ButtonStyle.Link).setURL(portal));
      await i.reply({embeds:[await guildEmbed(i.guildId,"💎 Premium active",`**${existing.plan_name||"Premium"}**\nStatus: **${existing.status}**`,BRAND.colours.premium,{banner:true})],components:row.components.length?[row]:[],ephemeral:true});
      return true;
    }

    const plans=await listPlans(i.guildId,true);
    if(!plans.length) {
      await i.reply({content:"No premium plans are available yet.",ephemeral:true});
      return true;
    }
    const slug=i.options.getString("plan");
    const referral=i.options.getString("referral")||undefined;
    if(slug) {
      const plan=plans.find(p=>p.slug.toLowerCase()===slug.toLowerCase());
      if(!plan) {
        await i.reply({content:`Unknown plan. Available: ${plans.map(p=>p.slug).join(", ")}`,ephemeral:true});
        return true;
      }
      try {
        const url=await createCheckout({guildId:i.guildId,discordUserId:i.user.id,planId:plan.id,referralCode:referral});
        const row=new ActionRowBuilder<ButtonBuilder>().addComponents(
          new ButtonBuilder().setLabel(`Subscribe to ${plan.name}`).setStyle(ButtonStyle.Link).setURL(url)
        );
        await i.reply({embeds:[await guildEmbed(i.guildId,`💎 ${plan.name}`,plan.description||"Premium server access",BRAND.colours.premium,{banner:true})],components:[row],ephemeral:true});
      } catch(err:any) {
        await i.reply({content:String(err?.message||"Unable to start checkout."),ephemeral:true});
      }
      return true;
    }

    const embed=await guildEmbed(i.guildId,"💎 Premium","Choose your membership below. Secure checkout is handled by Stripe.",BRAND.colours.premium,{banner:true});
    const buttons:ButtonBuilder[]=[];
    for(const p of plans) {
      embed.addFields({name:p.name,value:p.description||"Premium access"});
      try {
        const url=await createCheckout({guildId:i.guildId,discordUserId:i.user.id,planId:p.id,referralCode:referral});
        buttons.push(new ButtonBuilder().setLabel(p.name.replace(/^FC27\s*/i,"").slice(0,80)).setStyle(ButtonStyle.Link).setURL(url));
      } catch(err) { console.error("Unable to prepare premium plan button",p.slug,err); }
    }
    const rows:ActionRowBuilder<ButtonBuilder>[]=[];
    for(let x=0;x<buttons.length;x+=5) rows.push(new ActionRowBuilder<ButtonBuilder>().addComponents(...buttons.slice(x,x+5)));
    await i.reply({embeds:[embed],components:rows,ephemeral:true});
    return true;
  }

  const sub=await memberSubscription(i.guildId,i.user.id);
  if(!sub) {
    await i.reply({content:"You don't currently have a billing account. Use `/premium` to view plans.",ephemeral:true});
    return true;
  }
  let portal="";
  try { portal=await createPortal(i.guildId,i.user.id); } catch {}
  const renew=sub.current_period_end?new Date(sub.current_period_end).toLocaleDateString("en-GB"):"—";
  const row=new ActionRowBuilder<ButtonBuilder>();
  if(portal) row.addComponents(new ButtonBuilder().setLabel("Manage billing").setStyle(ButtonStyle.Link).setURL(portal));
  await i.reply({embeds:[await guildEmbed(i.guildId,"💎 Your Premium membership",`**${sub.plan_name||"Premium"}**\nStatus: **${sub.status}**\n${sub.cancel_at_period_end?"Ends":"Current period ends"}: **${renew}**`,BRAND.colours.premium,{banner:true})],components:row.components.length?[row]:[],ephemeral:true});
  return true;
}
