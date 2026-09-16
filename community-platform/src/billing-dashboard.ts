import { Router } from "express";
import { client } from "./bot.js";
import { config } from "./config.js";
import { audit, query } from "./db.js";
import { generateReferralCode, grantComp, handleStripeWebhook, reconcileCheckoutSession, revokeEntitlement } from "./billing.js";

export const billingRouter=Router();
const auth=(req:any,res:any,next:any)=>req.session?.user?next():res.redirect("/login");

billingRouter.post("/webhook",async(req:any,res)=>{
  try {
    const signature=String(req.headers["stripe-signature"]||"");
    if(!signature||!req.rawBody) return res.status(400).send("Missing Stripe signature/body");
    await handleStripeWebhook(req.rawBody,signature);
    res.json({received:true});
  } catch(err:any) {
    console.error("Stripe webhook",err);
    res.status(400).send(`Webhook error: ${err?.message||err}`);
  }
});

billingRouter.get("/success",async(req,res)=>{
  const sessionId=String(req.query.session_id||"");
  let synced=false;
  if(sessionId) {
    try { synced=Boolean(await reconcileCheckoutSession(sessionId)); }
    catch(err) { console.error("Checkout success reconciliation failed",err); }
  }
  res.render("billing-result",{
    tone:"success",icon:"✓",badge:synced?"Premium access synced":"Payment received",
    title:"You're in.",
    message:synced
      ?"Your FC27 Premium membership has been linked to Discord and your Premium role has been synced."
      :"Your checkout completed successfully. Discord access will sync automatically in a moment.",
    showDashboard:Boolean((req as any).session?.user)
  });
});

billingRouter.get("/cancelled",(req,res)=>res.render("billing-result",{
  tone:"warning",icon:"↩",badge:"No charge made",title:"Checkout cancelled",
  message:"Nothing has been changed. You can return to Discord and subscribe whenever you're ready.",
  showDashboard:Boolean((req as any).session?.user)
}));

billingRouter.get("/return",(req,res)=>res.render("billing-result",{
  tone:"info",icon:"✓",badge:"Billing updated",title:"All done",
  message:"Your billing settings have been updated. Any subscription changes will sync back to Discord automatically.",
  showDashboard:Boolean((req as any).session?.user)
}));

billingRouter.get("/",auth,async(req:any,res)=>{
  const [plans,subs,refs,events]=await Promise.all([
    query<any>(`SELECT * FROM billing_plans WHERE guild_id=$1 ORDER BY sort_order,name`,[config.targetGuildId]),
    query<any>(`SELECT s.*,p.name plan_name,p.slug FROM billing_subscriptions s LEFT JOIN billing_plans p ON p.id=s.plan_id WHERE s.guild_id=$1 ORDER BY s.updated_at DESC LIMIT 250`,[config.targetGuildId]),
    query<any>(`SELECT * FROM referral_codes WHERE guild_id=$1 ORDER BY created_at DESC`,[config.targetGuildId]),
    query<any>(`SELECT stripe_event_id,event_type,processed_at,error,created_at FROM billing_events ORDER BY created_at DESC LIMIT 50`,[])
  ]);
  const guild=client.guilds.cache.get(config.targetGuildId);
  const roles=guild?[...guild.roles.cache.values()].filter(r=>r.id!==guild.id).sort((a,b)=>b.position-a.position):[];
  const metrics={
    active:subs.filter(s=>["active","trialing","comped","gifted","past_due"].includes(s.status)).length,
    trialing:subs.filter(s=>s.status==="trialing").length,
    pastDue:subs.filter(s=>s.status==="past_due").length,
    cancelling:subs.filter(s=>s.cancel_at_period_end).length
  };
  res.render("billing",{user:req.session.user,plans,subs,refs,events,roles,metrics,stripeReady:Boolean(config.stripeSecretKey&&config.stripeWebhookSecret),baseUrl:config.baseUrl});
});

billingRouter.post("/plans",auth,async(req:any,res)=>{
  const slug=String(req.body.slug||"").trim().toLowerCase().replace(/[^a-z0-9_-]/g,"-");
  if(!slug||!req.body.name||!req.body.stripePriceId||!req.body.roleId) return res.status(400).send("Name, slug, Stripe Price ID and Discord role are required.");
  await query(`INSERT INTO billing_plans(guild_id,name,slug,description,stripe_price_id,role_id,trial_days,sort_order) VALUES($1,$2,$3,$4,$5,$6,$7,$8)
    ON CONFLICT(guild_id,slug) DO UPDATE SET name=$2,description=$4,stripe_price_id=$5,role_id=$6,trial_days=$7,sort_order=$8,updated_at=now()`,[
    config.targetGuildId,String(req.body.name),slug,String(req.body.description||""),String(req.body.stripePriceId),String(req.body.roleId),Math.max(0,Number(req.body.trialDays||0)),Number(req.body.sortOrder||0)
  ]);
  await audit(config.targetGuildId,req.session.user.id,"billing.plan.saved",{slug,name:req.body.name});
  res.redirect("/billing");
});

billingRouter.post("/plans/:id/toggle",auth,async(req:any,res)=>{
  await query(`UPDATE billing_plans SET active=NOT active,updated_at=now() WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);
  await audit(config.targetGuildId,req.session.user.id,"billing.plan.toggle",{id:req.params.id});
  res.redirect("/billing");
});

billingRouter.post("/comp",auth,async(req:any,res)=>{
  const userId=String(req.body.discordUserId||"").trim();
  const planId=Number(req.body.planId),days=Math.max(1,Number(req.body.days||30));
  if(!/^\d{15,22}$/.test(userId)||!planId) return res.status(400).send("Valid Discord user ID and plan are required.");
  await grantComp(config.targetGuildId,userId,planId,days,req.session.user.id);
  res.redirect("/billing");
});

billingRouter.post("/revoke",auth,async(req:any,res)=>{
  await revokeEntitlement(config.targetGuildId,String(req.body.discordUserId),Number(req.body.planId),req.session.user.id);
  res.redirect("/billing");
});

billingRouter.post("/referrals",auth,async(req:any,res)=>{
  const code=String(req.body.code||generateReferralCode()).trim().toUpperCase();
  const owner=String(req.body.ownerDiscordUserId||"").trim()||null;
  await query(`INSERT INTO referral_codes(guild_id,owner_discord_user_id,code,reward_type,reward_value) VALUES($1,$2,$3,$4,$5)
    ON CONFLICT(guild_id,code) DO UPDATE SET owner_discord_user_id=$2,reward_type=$4,reward_value=$5,active=true`,[
    config.targetGuildId,owner,code,String(req.body.rewardType||"none"),Number(req.body.rewardValue||0)
  ]);
  await audit(config.targetGuildId,req.session.user.id,"billing.referral.saved",{code,owner});
  res.redirect("/billing");
});

billingRouter.post("/referrals/:id/toggle",auth,async(_req,res)=>{
  const req:any=_req;
  await query(`UPDATE referral_codes SET active=NOT active WHERE id=$1 AND guild_id=$2`,[req.params.id,config.targetGuildId]);
  res.redirect("/billing");
});
