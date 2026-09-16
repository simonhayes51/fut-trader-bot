export type ModuleField = {
  key:string;
  label:string;
  help?:string;
  type:"channel"|"category"|"role"|"roles"|"channels"|"text"|"textarea"|"number"|"toggle"|"select"|"list"|"roleGroups"|"rewards";
  options?: {value:string;label:string}[];
  placeholder?:string;
  min?:number;
  max?:number;
  step?:number;
};

export type ModuleDefinition = {
  key: string;
  name: string;
  description: string;
  category: "Community" | "Trading" | "Moderation" | "Automation" | "Social" | "Billing";
  defaults: Record<string, any>;
  fields: ModuleField[];
};

export const modules: ModuleDefinition[] = [
  {
    key:"welcome", name:"Welcome & onboarding", description:"Welcome messages, automatic member role and private welcome DM.", category:"Community",
    defaults:{channelId:"",autoRoleId:"",message:"Welcome {user} to {server}! Read the rules, pick your roles and get trading.",dmWelcome:false},
    fields:[
      {key:"channelId",label:"Welcome channel",help:"Where the public welcome message should be posted.",type:"channel"},
      {key:"autoRoleId",label:"New member role",help:"Optional role automatically given to everyone who joins.",type:"role"},
      {key:"message",label:"Welcome message",help:"Use {user} for the member and {server} for the server name.",type:"textarea"},
      {key:"dmWelcome",label:"Send a private welcome too",help:"Also send the same welcome message by DM.",type:"toggle"}
    ]
  },
  {
    key:"role_menus", name:"Role menus", description:"Let members choose platform, trading style and notification roles themselves.", category:"Community",
    defaults:{channelId:"",messageId:"",groups:[]},
    fields:[
      {key:"channelId",label:"Role selection channel",help:"Where the bot should publish the role selector.",type:"channel"},
      {key:"groups",label:"Role groups",help:"Create groups such as Platform, Trader Type or Notifications, then choose the roles members can pick.",type:"roleGroups"}
    ]
  },
  {
    key:"reputation", name:"Reputation & thanks", description:"Reward helpful members while limiting farming and spam.", category:"Community",
    defaults:{dailyLimit:3,minAccountAgeDays:3,leaderboardSize:10},
    fields:[
      {key:"dailyLimit",label:"Thanks allowed per day",help:"Maximum number one member can give each day.",type:"number",min:1,max:50},
      {key:"minAccountAgeDays",label:"Minimum account age",help:"New Discord accounts must be this many days old before using reputation.",type:"number",min:0,max:365},
      {key:"leaderboardSize",label:"Leaderboard size",help:"Number of members shown on reputation leaderboards.",type:"number",min:3,max:50}
    ]
  },
  {
    key:"levels", name:"Activity levels", description:"Give XP for useful activity and automatically award level roles.", category:"Community",
    defaults:{messageXp:2,helpfulXp:15,cooldownSeconds:60,ignoredChannelIds:[],rewards:[]},
    fields:[
      {key:"messageXp",label:"XP per message",help:"XP earned for an eligible message.",type:"number",min:0,max:100},
      {key:"helpfulXp",label:"Helpful activity bonus",help:"Extra XP available for helpful contributions.",type:"number",min:0,max:500},
      {key:"cooldownSeconds",label:"XP cooldown",help:"Seconds before the same member can earn message XP again.",type:"number",min:0,max:3600},
      {key:"ignoredChannelIds",label:"Channels that do not earn XP",help:"Select channels where activity should not count.",type:"channels"},
      {key:"rewards",label:"Level role rewards",help:"Choose the XP target and role that should be awarded.",type:"rewards"}
    ]
  },
  {
    key:"trading_tools", name:"Trading calculators", description:"Configure EA tax and how calculator command results are shown.", category:"Trading",
    defaults:{taxPercent:5,ephemeralCalculators:true},
    fields:[
      {key:"taxPercent",label:"EA market tax",help:"Normally 5%. Change this only if EA changes the transfer-market tax.",type:"number",min:0,max:20,step:0.1},
      {key:"ephemeralCalculators",label:"Keep calculator results private",help:"Only the member using the command sees the result.",type:"toggle"}
    ]
  },
  {
    key:"trade_calls", name:"Trade calls", description:"Control where trade calls are posted and who can publish them.", category:"Trading",
    defaults:{channelId:"",allowedRoleIds:[],autoThread:true,requireReason:true},
    fields:[
      {key:"channelId",label:"Trade calls channel",help:"All structured trade calls will be posted here.",type:"channel"},
      {key:"allowedRoleIds",label:"Who can post trade calls",help:"Choose the trader/staff roles allowed to publish calls. Leave empty to allow everyone.",type:"roles"},
      {key:"autoThread",label:"Create a discussion thread",help:"Automatically open a thread underneath each trade call.",type:"toggle"},
      {key:"requireReason",label:"Require a reason",help:"Traders must explain why they are recommending the trade.",type:"toggle"}
    ]
  },
  {
    key:"wl_votes", name:"W / L voting", description:"Configure community Win/Loss voting for purchases and flips.", category:"Trading",
    defaults:{channelId:"",voteMinutes:15,cooldownMinutes:5},
    fields:[
      {key:"channelId",label:"W/L channel",help:"Where W/L submissions should be posted.",type:"channel"},
      {key:"voteMinutes",label:"Voting time",help:"Minutes before voting closes.",type:"number",min:1,max:1440},
      {key:"cooldownMinutes",label:"Member cooldown",help:"Minutes a member waits before submitting another W/L.",type:"number",min:0,max:1440}
    ]
  },
  {
    key:"suggestions", name:"Suggestions", description:"Member suggestions with voting, discussion threads and staff statuses.", category:"Community",
    defaults:{channelId:"",createThread:true,statuses:["Submitted","Reviewing","Planned","Added","Declined"]},
    fields:[
      {key:"channelId",label:"Suggestions channel",help:"New suggestions are posted here.",type:"channel"},
      {key:"createThread",label:"Create a discussion thread",help:"Open a thread for each new suggestion.",type:"toggle"},
      {key:"statuses",label:"Suggestion statuses",help:"One status per line, in the order staff should use them.",type:"list",placeholder:"Submitted\nReviewing\nPlanned\nAdded\nDeclined"}
    ]
  },
  {
    key:"tickets", name:"Tickets & reports", description:"Private support, scam reports, appeals and partnership tickets.", category:"Community",
    defaults:{categoryId:"",staffRoleIds:[],logChannelId:"",types:["Support","Trading","Scam report","Appeal","Partnership"]},
    fields:[
      {key:"categoryId",label:"Ticket category",help:"New private ticket channels will be created inside this Discord category.",type:"category"},
      {key:"staffRoleIds",label:"Ticket staff",help:"Choose every role that should be able to see and manage tickets.",type:"roles"},
      {key:"logChannelId",label:"Ticket log channel",help:"Closed-ticket and staff activity logs go here.",type:"channel"},
      {key:"types",label:"Ticket reasons",help:"One option per line. Members choose one when opening a ticket.",type:"list",placeholder:"Support\nTrading\nScam report\nAppeal\nPartnership"}
    ]
  },
  {
    key:"giveaways", name:"Giveaways", description:"Set the default giveaway channel and anti-alt restrictions.", category:"Community",
    defaults:{channelId:"",minAccountAgeDays:3,boosterBonusEntries:0},
    fields:[
      {key:"channelId",label:"Giveaway channel",help:"Default channel for giveaways.",type:"channel"},
      {key:"minAccountAgeDays",label:"Minimum account age",help:"Discord accounts younger than this cannot enter.",type:"number",min:0,max:3650},
      {key:"boosterBonusEntries",label:"Server booster bonus entries",help:"Extra entries given to members boosting the server.",type:"number",min:0,max:20}
    ]
  },
  {
    key:"automod", name:"Automod & anti-scam", description:"Protect the server from invite spam, phishing, mention spam and repeated messages.", category:"Moderation",
    defaults:{blockInvites:true,inviteBypassRoleIds:[],maxMentions:5,duplicateWindowSeconds:15,duplicateLimit:4,blockedTerms:[],blockedDomains:[],action:"delete",timeoutMinutes:10,modLogChannelId:""},
    fields:[
      {key:"blockInvites",label:"Block Discord invite links",help:"Delete unauthorised server invite links automatically.",type:"toggle"},
      {key:"inviteBypassRoleIds",label:"Roles allowed to post invites",help:"Staff or partner roles that may post Discord invites.",type:"roles"},
      {key:"maxMentions",label:"Maximum mentions in one message",help:"Messages over this limit trigger automod.",type:"number",min:1,max:100},
      {key:"duplicateWindowSeconds",label:"Spam detection window",help:"Seconds used to detect repeated messages.",type:"number",min:1,max:300},
      {key:"duplicateLimit",label:"Repeated-message limit",help:"Number of matching messages that triggers automod.",type:"number",min:2,max:20},
      {key:"blockedTerms",label:"Blocked words or phrases",help:"One word or phrase per line.",type:"list"},
      {key:"blockedDomains",label:"Blocked websites",help:"One domain per line, for example badsite.com.",type:"list"},
      {key:"action",label:"When automod triggers",help:"Choose what the bot should do.",type:"select",options:[{value:"delete",label:"Delete the message"},{value:"timeout",label:"Delete message + timeout member"}]},
      {key:"timeoutMinutes",label:"Timeout length",help:"Minutes to timeout the member when timeout is selected.",type:"number",min:1,max:40320},
      {key:"modLogChannelId",label:"Moderation log channel",help:"Where automod actions should be recorded.",type:"channel"}
    ]
  },
  {
    key:"mod_tools", name:"Staff moderation", description:"Choose which staff roles can use moderation tools and where actions are logged.", category:"Moderation",
    defaults:{staffRoleIds:[],modLogChannelId:""},
    fields:[
      {key:"staffRoleIds",label:"Moderation staff roles",help:"Roles allowed to use staff moderation commands.",type:"roles"},
      {key:"modLogChannelId",label:"Moderation log channel",help:"Warnings and staff actions are recorded here.",type:"channel"}
    ]
  },
  {
    key:"scheduled_messages", name:"Scheduled messages", description:"Default settings for recurring server announcements and reminders.", category:"Automation",
    defaults:{timezone:"Europe/London"},
    fields:[
      {key:"timezone",label:"Server timezone",help:"Used when scheduling messages. Europe/London is recommended for a UK server.",type:"select",options:[{value:"Europe/London",label:"UK (Europe/London)"},{value:"Europe/Paris",label:"Central Europe (Europe/Paris)"},{value:"America/New_York",label:"US Eastern (America/New_York)"},{value:"America/Chicago",label:"US Central (America/Chicago)"},{value:"America/Los_Angeles",label:"US Pacific (America/Los_Angeles)"},{value:"UTC",label:"UTC"}]}
    ]
  },
  {
    key:"social_feeds", name:"Social feeds", description:"Default options for automatic X, RSS, Reddit, YouTube and webhook posts.", category:"Social",
    defaults:{defaultMentionRoleId:"",compactEmbeds:false},
    fields:[
      {key:"defaultMentionRoleId",label:"Default notification role",help:"Optional role mentioned on new social posts.",type:"role"},
      {key:"compactEmbeds",label:"Use compact posts",help:"Keep social feed messages shorter and cleaner.",type:"toggle"}
    ]
  },
  {
    key:"join_security", name:"Join security", description:"Flag suspicious new accounts and sudden join spikes.", category:"Moderation",
    defaults:{minAccountAgeHours:24,alertChannelId:"",joinsPerMinuteAlert:8},
    fields:[
      {key:"minAccountAgeHours",label:"Young-account threshold",help:"Accounts newer than this many hours are flagged to staff.",type:"number",min:0,max:8760},
      {key:"alertChannelId",label:"Security alert channel",help:"Where suspicious joins should be reported.",type:"channel"},
      {key:"joinsPerMinuteAlert",label:"Raid alert threshold",help:"Alert when this many members join within one minute.",type:"number",min:2,max:100}
    ]
  },
  {
    key:"premium_billing", name:"Premium memberships", description:"Simple defaults for premium access. Plans and referrals are managed on the dedicated Billing page.", category:"Billing",
    defaults:{gracePastDue:true,removeRoleOnCancel:true,allowPromotionCodes:true,referralsEnabled:true,defaultTrialDays:0},
    fields:[
      {key:"gracePastDue",label:"Keep access during payment retries",help:"Members keep Premium while Stripe is retrying a failed payment.",type:"toggle"},
      {key:"removeRoleOnCancel",label:"Remove Premium when access ends",help:"Automatically remove the Premium role after cancellation/expiry.",type:"toggle"},
      {key:"allowPromotionCodes",label:"Allow discount codes",help:"Let members enter Stripe promotion codes at checkout.",type:"toggle"},
      {key:"referralsEnabled",label:"Enable referral codes",help:"Allow referral attribution at checkout.",type:"toggle"},
      {key:"defaultTrialDays",label:"Default free trial",help:"Default trial length for new plans. Individual plans can override this.",type:"number",min:0,max:90}
    ]
  }
];

export const moduleMap = new Map(modules.map(m => [m.key, m]));
