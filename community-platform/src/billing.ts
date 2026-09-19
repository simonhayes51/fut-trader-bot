import Stripe from "stripe";
import crypto from "node:crypto";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, one, query } from "./db.js";
import { rewardReferralConversion } from "./economy-core.js";

export const stripe = config.stripeSecretKey ? new Stripe(config.stripeSecretKey) : null;

export type BillingPlan = {
  id:number; guild_id:string; name:string; slug:string; description:string|null;
  stripe_price_id:string; role_id:string; active:boolean; trial_days:number;
  sort_order:number; metadata:any;
};

export async function listPlans(guildId:string, activeOnly=false) {
  return query<BillingPlan>(`SELECT * FROM billing_plans WHERE guild_id=$1 ${activeOnly?"AND active=true":""} ORDER BY sort_order,name`,[guildId]);
}

const paidLikeStatuses=new Set(["active","trialing","past_due","unpaid","paused"]);

export async function createCheckout(input:{guildId:string;discordUserId:string;planId:number;referralCode?:string}) {
  if(!stripe) throw new Error("Stripe is not configured");
  const plan=await one<BillingPlan>(`SELECT * FROM billing_plans WHERE id=$1 AND guild_id=$2 AND active=true`,[input.planId,input.guildId]);
  if(!plan) throw new Error("Plan not found");

  let current=await getMemberBilling(input.guildId,input.discordUserId);
  if(!current) {
    try { current=await reconcileMemberBilling(input.guildId,input.discordUserId); } catch(err) { console.error("Stripe reconciliation before checkout failed",err); }
  }
  if(current && paidLikeStatuses.has(String(current.status))) {
    throw new Error("You already have an active Premium subscription. Use /subscription to manage it.");
  }

  const existing=await one<any>(`SELECT stripe_customer_id FROM billing_customers WHERE guild_id=$1 AND discord_user_id=$2`,[input.guildId,input.discordUserId]);
  const referral=input.referralCode ? await one<any>(`SELECT * FROM referral_codes WHERE guild_id=$1 AND lower(code)=lower($2) AND active=true`,[input.guildId,input.referralCode]) : null;
  const params:Stripe.Checkout.SessionCreateParams={
    mode:"subscription",
    line_items:[{price:plan.stripe_price_id,quantity:1}],
    success_url:`${config.baseUrl}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url:`${config.baseUrl}/billing/cancelled`,
    allow_promotion_codes:true,
    client_reference_id:input.discordUserId,
    metadata:{guildId:input.guildId,discordUserId:input.discordUserId,planId:String(plan.id),referralCode:referral?.code||""},
    subscription_data:{
      metadata:{guildId:input.guildId,discordUserId:input.discordUserId,planId:String(plan.id),referralCode:referral?.code||""}
    }
  };
  if(existing?.stripe_customer_id) params.customer=existing.stripe_customer_id;
  const checkout=await stripe.checkout.sessions.create(params);
  if(referral) await query(`UPDATE referral_codes SET clicks=clicks+1 WHERE id=$1`,[referral.id]);
  await audit(input.guildId,input.discordUserId,"billing.checkout.created",{planId:plan.id,sessionId:checkout.id,referralCode:referral?.code});
  return checkout.url!;
}

export async function createPortal(guildId:string,discordUserId:string) {
  if(!stripe) throw new Error("Stripe is not configured");
  const customer=await one<any>(`SELECT stripe_customer_id FROM billing_customers WHERE guild_id=$1 AND discord_user_id=$2`,[guildId,discordUserId]);
  if(!customer?.stripe_customer_id) throw new Error("No billing account found");
  const portal=await stripe.billingPortal.sessions.create({customer:customer.stripe_customer_id,return_url:`${config.baseUrl}/billing/return`});
  return portal.url;
}

export async function getMemberBilling(guildId:string,discordUserId:string) {
  return one<any>(`SELECT s.*,p.name plan_name,p.role_id,p.slug FROM billing_subscriptions s LEFT JOIN billing_plans p ON p.id=s.plan_id WHERE s.guild_id=$1 AND s.discord_user_id=$2 ORDER BY s.created_at DESC LIMIT 1`,[guildId,discordUserId]);
}

async function upsertCustomer(guildId:string,userId:string,customerId:string) {
  await query(`INSERT INTO billing_customers(guild_id,discord_user_id,stripe_customer_id) VALUES($1,$2,$3)
    ON CONFLICT(guild_id,discord_user_id) DO UPDATE SET stripe_customer_id=$3,updated_at=now()`,[guildId,userId,customerId]);
}

function entitlementActive(status:string) { return ["active","trialing","past_due","comped","gifted"].includes(status); }

export async function syncEntitlement(guildId:string,userId:string,planId:number,status:string,source="stripe",expiresAt?:Date|null) {
  const plan=await one<BillingPlan>(`SELECT * FROM billing_plans WHERE id=$1 AND guild_id=$2`,[planId,guildId]);
  if(!plan) return;
  const active=entitlementActive(status) && (!expiresAt || expiresAt.getTime()>Date.now());
  await query(`INSERT INTO entitlements(guild_id,discord_user_id,entitlement_key,source,source_ref,active,expires_at,updated_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,now())
    ON CONFLICT(guild_id,discord_user_id,entitlement_key) DO UPDATE SET source=$4,source_ref=$5,active=$6,expires_at=$7,updated_at=now()`,
    [guildId,userId,`plan:${plan.slug}`,source,String(planId),active,expiresAt||null]);
  const guild=client.guilds.cache.get(guildId);
  if(!guild||!plan.role_id) return;
  const member=await guild.members.fetch(userId).catch(()=>null);
  if(!member) return;
  if(active && !member.roles.cache.has(plan.role_id)) await member.roles.add(plan.role_id,"Premium entitlement active").catch(console.error);
  if(!active && member.roles.cache.has(plan.role_id)) await member.roles.remove(plan.role_id,"Premium entitlement inactive").catch(console.error);
}

export async function processSubscription(sub:Stripe.Subscription) {
  const meta=sub.metadata||{};
  const guildId=meta.guildId||config.targetGuildId;
  const userId=meta.discordUserId;
  const planId=Number(meta.planId||0);
  if(!userId||!planId) return;
  const customerId=typeof sub.customer==="string"?sub.customer:sub.customer.id;
  await upsertCustomer(guildId,userId,customerId);
  const periodEnd=new Date((sub.items.data[0]?.current_period_end||Math.floor(Date.now()/1000))*1000);
  await query(`INSERT INTO billing_subscriptions(guild_id,discord_user_id,plan_id,stripe_subscription_id,stripe_customer_id,status,current_period_end,cancel_at_period_end,referral_code,updated_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,now())
    ON CONFLICT(stripe_subscription_id) DO UPDATE SET plan_id=$3,status=$6,current_period_end=$7,cancel_at_period_end=$8,referral_code=$9,updated_at=now()`,
    [guildId,userId,planId,sub.id,customerId,sub.status,periodEnd,sub.cancel_at_period_end,meta.referralCode||null]);
  await syncEntitlement(guildId,userId,planId,sub.status,"stripe",periodEnd);
}

export async function reconcileMemberBilling(guildId:string,discordUserId:string) {
  if(!stripe) return null;
  const result=await stripe.subscriptions.search({
    query:`metadata['guildId']:'${guildId}' AND metadata['discordUserId']:'${discordUserId}'`,
    limit:10
  });
  const candidates=result.data.sort((a,b)=>b.created-a.created);
  for(const sub of candidates) await processSubscription(sub);
  return getMemberBilling(guildId,discordUserId);
}

export async function reconcileCheckoutSession(sessionId:string) {
  if(!stripe) return null;
  const session=await stripe.checkout.sessions.retrieve(sessionId,{expand:["subscription"]});
  const sub=session.subscription;
  if(sub && typeof sub!=="string") {
    await processSubscription(sub as Stripe.Subscription);
    return sub;
  }
  if(typeof sub==="string") {
    const full=await stripe.subscriptions.retrieve(sub);
    await processSubscription(full);
    return full;
  }
  return null;
}

export async function handleStripeWebhook(rawBody:Buffer,signature:string) {
  if(!stripe||!config.stripeWebhookSecret) throw new Error("Stripe webhook is not configured");
  const event=stripe.webhooks.constructEvent(rawBody,signature,config.stripeWebhookSecret);
  const existing=await one<any>(`SELECT id,processed_at FROM billing_events WHERE stripe_event_id=$1`,[event.id]);
  if(existing?.processed_at) return event;
  if(!existing) {
    await query(`INSERT INTO billing_events(stripe_event_id,event_type,payload) VALUES($1,$2,$3::jsonb)`,[event.id,event.type,JSON.stringify(event)]);
  } else {
    await query(`UPDATE billing_events SET event_type=$2,payload=$3::jsonb,error=NULL WHERE stripe_event_id=$1`,[event.id,event.type,JSON.stringify(event)]);
  }
  try {
    if(event.type==="checkout.session.completed") {
      const s=event.data.object as Stripe.Checkout.Session;
      const guildId=s.metadata?.guildId||config.targetGuildId,userId=s.metadata?.discordUserId||s.client_reference_id;
      if(userId && typeof s.customer==="string") await upsertCustomer(guildId,userId,s.customer);
      if(typeof s.subscription==="string") {
        const sub=await stripe.subscriptions.retrieve(s.subscription);
        await processSubscription(sub);
      }
      const ref=s.metadata?.referralCode;
      if(ref) {
        await query(`UPDATE referral_codes SET conversions=conversions+1 WHERE guild_id=$1 AND lower(code)=lower($2)`,[guildId,ref]);
        if(userId) await rewardReferralConversion(guildId,ref,userId,s.id).catch(err=>console.error("Referral economy reward failed",err));
      }
    }
    if(["customer.subscription.created","customer.subscription.updated","customer.subscription.deleted"].includes(event.type)) await processSubscription(event.data.object as Stripe.Subscription);
    if(event.type==="invoice.payment_failed") {
      const invoice=event.data.object as Stripe.Invoice;
      await audit(config.targetGuildId,null,"billing.payment_failed",{invoiceId:invoice.id,customer:invoice.customer});
    }
    if(event.type==="charge.dispute.created") {
      const dispute=event.data.object as Stripe.Dispute;
      await audit(config.targetGuildId,null,"billing.dispute",{disputeId:dispute.id,charge:dispute.charge});
    }
    await query(`UPDATE billing_events SET processed_at=now(),error=NULL WHERE stripe_event_id=$1`,[event.id]);
  } catch(err:any) {
    await query(`UPDATE billing_events SET error=$2 WHERE stripe_event_id=$1`,[event.id,String(err?.message||err)]);
    throw err;
  }
  return event;
}

export async function grantComp(guildId:string,userId:string,planId:number,days:number,actorId:string) {
  const plan=await one<BillingPlan>(`SELECT * FROM billing_plans WHERE id=$1 AND guild_id=$2`,[planId,guildId]);
  if(!plan) throw new Error("Plan not found");
  const current=await one<any>(`SELECT expires_at FROM entitlements WHERE guild_id=$1 AND discord_user_id=$2 AND entitlement_key=$3 AND active=true`,[guildId,userId,`plan:${plan.slug}`]);
  const base=current?.expires_at && new Date(current.expires_at).getTime()>Date.now()?new Date(current.expires_at).getTime():Date.now();
  const expires=new Date(base+Math.max(1,days)*86400000);
  await query(`INSERT INTO billing_subscriptions(guild_id,discord_user_id,plan_id,status,current_period_end,source,updated_at)
    VALUES($1,$2,$3,'comped',$4,'manual',now())`,[guildId,userId,planId,expires]);
  await syncEntitlement(guildId,userId,planId,"comped","manual",expires);
  await audit(guildId,actorId,"billing.comp.granted",{userId,planId,days,expires});
}

export async function revokeEntitlement(guildId:string,userId:string,planId:number,actorId:string) {
  await syncEntitlement(guildId,userId,planId,"revoked","manual",new Date());
  await query(`UPDATE billing_subscriptions SET status='revoked',updated_at=now() WHERE guild_id=$1 AND discord_user_id=$2 AND plan_id=$3 AND status IN ('comped','gifted')`,[guildId,userId,planId]);
  await audit(guildId,actorId,"billing.entitlement.revoked",{userId,planId});
}

export function generateReferralCode(prefix="FC") { return `${prefix}${crypto.randomBytes(4).toString("hex")}`.toUpperCase(); }
