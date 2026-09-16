export type ModuleDefinition = {
  key: string;
  name: string;
  description: string;
  category: "Community" | "Trading" | "Moderation" | "Automation" | "Social" | "Billing";
  defaults: Record<string, unknown>;
};

export const modules: ModuleDefinition[] = [
  { key:"welcome", name:"Welcome & onboarding", description:"Welcome embeds, auto-role and new-member onboarding.", category:"Community", defaults:{channelId:"",autoRoleId:"",message:"Welcome {user} to {server}! Read the rules, pick your roles and get trading.",dmWelcome:false}},
  { key:"role_menus", name:"Role menus", description:"Self-service platform, trading style and notification roles.", category:"Community", defaults:{channelId:"",messageId:"",groups:[]}},
  { key:"reputation", name:"Reputation & thanks", description:"Helpful-member reputation with farming controls and profile stats.", category:"Community", defaults:{dailyLimit:3,minAccountAgeDays:3,leaderboardSize:10}},
  { key:"levels", name:"Activity levels", description:"Meaningful activity XP with cooldowns and role rewards.", category:"Community", defaults:{messageXp:2,helpfulXp:15,cooldownSeconds:60,ignoredChannelIds:[],rewards:[]}},
  { key:"trading_tools", name:"Trading calculators", description:"EA tax, profit, ROI and break-even commands.", category:"Trading", defaults:{taxPercent:5,ephemeralCalculators:true}},
  { key:"trade_calls", name:"Trade calls", description:"Structured trader calls with targets, outcomes and tracked performance.", category:"Trading", defaults:{channelId:"",allowedRoleIds:[],autoThread:true,requireReason:true}},
  { key:"wl_votes", name:"W / L voting", description:"Community W/L voting for purchases and flips.", category:"Trading", defaults:{channelId:"",voteMinutes:15,cooldownMinutes:5}},
  { key:"suggestions", name:"Suggestions", description:"Structured suggestions with voting and staff statuses.", category:"Community", defaults:{channelId:"",createThread:true,statuses:["Submitted","Reviewing","Planned","Added","Declined"]}},
  { key:"tickets", name:"Tickets & reports", description:"Support, scam reports, appeals and partnerships with transcripts.", category:"Community", defaults:{categoryId:"",staffRoleIds:[],logChannelId:"",types:["Support","Trading","Scam report","Appeal","Partnership"]}},
  { key:"giveaways", name:"Giveaways", description:"Button-entry giveaways with account-age and role restrictions.", category:"Community", defaults:{channelId:"",minAccountAgeDays:3,boosterBonusEntries:0}},
  { key:"automod", name:"Automod & anti-scam", description:"Invite, phishing, spam, mention and blocked-word protection.", category:"Moderation", defaults:{blockInvites:true,inviteBypassRoleIds:[],maxMentions:5,duplicateWindowSeconds:15,duplicateLimit:4,blockedTerms:[],blockedDomains:[],action:"delete",timeoutMinutes:10,modLogChannelId:""}},
  { key:"mod_tools", name:"Staff moderation", description:"Warnings, notes, timeout, purge and moderation history.", category:"Moderation", defaults:{staffRoleIds:[],modLogChannelId:""}},
  { key:"scheduled_messages", name:"Scheduled messages", description:"Recurring market chats, promo threads and reminders.", category:"Automation", defaults:{timezone:"Europe/London"}},
  { key:"social_feeds", name:"Social feeds", description:"TweetShift-style RSS, Reddit, YouTube, X and webhook feeds.", category:"Social", defaults:{defaultMentionRoleId:"",compactEmbeds:false}},
  { key:"join_security", name:"Join security", description:"New-account and raid detection.", category:"Moderation", defaults:{minAccountAgeHours:24,alertChannelId:"",joinsPerMinuteAlert:8}},
  { key:"premium_billing", name:"Premium memberships", description:"Stripe subscriptions, trials, Discord role entitlements, referrals, comps and billing portal.", category:"Billing", defaults:{enabledPlans:[],gracePastDue:true,removeRoleOnCancel:true,allowPromotionCodes:true,referralsEnabled:true,defaultTrialDays:0}}
];

export const moduleMap = new Map(modules.map(m => [m.key, m]));
