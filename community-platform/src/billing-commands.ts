import { ChatInputCommandInteraction, Client, EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { createCheckout, createPortal, getMemberBilling, listPlans, reconcileMemberBilling } from "./billing.js";
import { getFeature } from "./db.js";

export const billingCommandData = [
  new SlashCommandBuilder().setName("premium").setDescription("View premium plans or subscribe")
    .addStringOption(o=>o.setName("plan").setDescription("Plan slug (optional)"))
    .addStringOption(o=>o.setName("referral").setDescription("Referral code (optional)")),
  new SlashCommandBuilder().setName("subscription").setDescription("View or manage your premium subscription")
].map(c=>c.toJSON());

export async function handleBillingCommand(_client:Client,i:ChatInputCommandInteraction) {
  if(!i.guildId) return false;
  if(!["premium","subscription"].includes(i.commandName)) return false;
  const feature=await getFeature(i.guildId,"premium_billing",{});
  if(!feature.enabled) {
    await i.reply({content:"Premium memberships are currently disabled.",ephemeral:true});
    return true;
  }
  if(i.commandName==="premium") {
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
      const url=await createCheckout({guildId:i.guildId,discordUserId:i.user.id,planId:plan.id,referralCode:referral});
      await i.reply({content:`💎 **${plan.name}**\n${plan.description||"Premium server access"}\n\nSubscribe securely: ${url}`,ephemeral:true});
      return true;
    }
    const embed=new EmbedBuilder().setTitle("💎 Premium memberships").setDescription("Choose a plan with `/premium plan:<slug>`. Payment is handled securely by Stripe.");
    for(const p of plans) embed.addFields({name:`${p.name} • ${p.slug}`,value:`${p.description||"Premium access"}${p.trial_days?`\n🎁 ${p.trial_days}-day trial`:""}`});
    await i.reply({embeds:[embed],ephemeral:true});
    return true;
  }
  let sub=await getMemberBilling(i.guildId,i.user.id);
  if(!sub) {
    try { sub=await reconcileMemberBilling(i.guildId,i.user.id); } catch(err) { console.error("Stripe reconciliation failed",err); }
  }
  if(!sub) {
    await i.reply({content:"You don't currently have a billing account. Use `/premium` to view plans.",ephemeral:true});
    return true;
  }
  let portal="";
  try { portal=await createPortal(i.guildId,i.user.id); } catch {}
  const renew=sub.current_period_end?new Date(sub.current_period_end).toLocaleDateString("en-GB"):"—";
  await i.reply({content:`💎 **${sub.plan_name||"Premium"}**\nStatus: **${sub.status}**\n${sub.cancel_at_period_end?"Ends":"Current period ends"}: **${renew}**${portal?`\n\nManage billing: ${portal}`:""}`,ephemeral:true});
  return true;
}
