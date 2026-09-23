export type ModuleField = {
  key:string;
  label:string;
  help?:string;
  type:"channel"|"category"|"role"|"roles"|"channels"|"text"|"textarea"|"number"|"toggle"|"select"|"list"|"roleGroups"|"ticketPanels"|"rewards";
  options?: {value:string;label:string}[];
  placeholder?:string;
  min?:number;
  max?:number;
  step?:number;
};

export type ModuleDefinition = {
  key:string;
  name:string;
  description:string;
  category:"Community"|"Engagement"|"Moderation"|"Automation"|"Social"|"Billing"|"Branding";
  defaults:Record<string,any>;
  fields:ModuleField[];
};

export const modules:ModuleDefinition[]=[
  {
    key:"server_branding",name:"Server branding",description:"Customise the bot name, embed colours, logo, header image and footer per Discord server.",category:"Branding",
    defaults:{name:"EAFC.Live",botNickname:"",url:"https://eafc.live",footerText:"EAFC.Live • FC27 Community",logoUrl:"",bannerUrl:"",primaryColour:"#22d3ee",premiumColour:"#8b5cf6",successColour:"#22c55e",warningColour:"#f59e0b",dangerColour:"#ef4444",neutralColour:"#64748b",coinsColour:"#f5b942"},
    fields:[
      {key:"name",label:"Server/bot brand name",type:"text",placeholder:"EAFC Legends"},
      {key:"botNickname",label:"Bot nickname in this server",help:"Changes the bot's Discord display name for this server only. Leave blank to keep the current nickname.",type:"text",placeholder:"EAFC Legends Bot"},
      {key:"url",label:"Website URL",type:"text",placeholder:"https://example.com"},
      {key:"footerText",label:"Embed footer text",type:"text",placeholder:"EAFC Legends • FC27 Trading"},
      {key:"logoUrl",label:"Logo URL",help:"Shown as the embed thumbnail where possible.",type:"text",placeholder:"https://.../logo.png"},
      {key:"bannerUrl",label:"Header/banner URL",help:"Shown on larger system and premium embeds.",type:"text",placeholder:"https://.../banner.png"},
      {key:"primaryColour",label:"Primary colour",type:"text",placeholder:"#22d3ee"},
      {key:"premiumColour",label:"Premium colour",type:"text",placeholder:"#8b5cf6"},
      {key:"successColour",label:"Success colour",type:"text",placeholder:"#22c55e"},
      {key:"warningColour",label:"Warning colour",type:"text",placeholder:"#f59e0b"},
      {key:"dangerColour",label:"Danger colour",type:"text",placeholder:"#ef4444"},
      {key:"neutralColour",label:"Neutral colour",type:"text",placeholder:"#64748b"},
      {key:"coinsColour",label:"Coins/rewards colour",type:"text",placeholder:"#f5b942"}
    ]
  },
  {
    key:"welcome",name:"Welcome & onboarding",description:"Welcome new members, assign a base role and optionally send a private introduction.",category:"Community",
    defaults:{channelId:"",autoRoleId:"",message:"Welcome {user} to {server}! Read the rules and choose your roles.",dmWelcome:false},
    fields:[
      {key:"channelId",label:"Welcome channel",help:"Where public welcome messages are posted.",type:"channel"},
      {key:"autoRoleId",label:"New member role",help:"Optional role automatically assigned when somebody joins.",type:"role"},
      {key:"message",label:"Welcome message",help:"Use {user}, {server}, {inviter}, {invites} and {invite_code} as placeholders.",type:"textarea"},
      {key:"dmWelcome",label:"Send a welcome DM",help:"Also send the welcome message privately.",type:"toggle"}
    ]
  },
  {
    key:"role_menus",name:"Roles & interests",description:"Let members choose platform, interests and notification roles themselves.",category:"Community",
    defaults:{channelId:"",messageId:"",groups:[]},
    fields:[
      {key:"channelId",label:"Role selection channel",help:"Where the role selector is published.",type:"channel"},
      {key:"groups",label:"Role groups",help:"Create groups such as Platform, Interests and Notifications.",type:"roleGroups"}
    ]
  },
  {
    key:"reputation",name:"Kudos",description:"Let members recognise useful posts, good calls and helpful community contributions.",category:"Engagement",
    defaults:{dailyLimit:5,minAccountAgeDays:3,leaderboardSize:10},
    fields:[
      {key:"dailyLimit",label:"Kudos per day",help:"Maximum kudos one member can give every 24 hours.",type:"number",min:1,max:50},
      {key:"minAccountAgeDays",label:"Minimum account age",help:"New Discord accounts must be this old before giving kudos.",type:"number",min:0,max:365},
      {key:"leaderboardSize",label:"Leaderboard size",help:"Number of members shown on the kudos leaderboard.",type:"number",min:3,max:50}
    ]
  },
  {
    key:"levels",name:"Levels & progression",description:"Award XP for useful community activity and unlock role milestones.",category:"Engagement",
    defaults:{messageXp:2,helpfulXp:15,cooldownSeconds:60,ignoredChannelIds:[],rewards:[]},
    fields:[
      {key:"messageXp",label:"XP per eligible message",type:"number",min:0,max:100},
      {key:"helpfulXp",label:"Kudos bonus XP",type:"number",min:0,max:500},
      {key:"cooldownSeconds",label:"XP cooldown",help:"How long before another message can earn XP.",type:"number",min:10,max:3600},
      {key:"ignoredChannelIds",label:"No-XP channels",type:"channels"},
      {key:"rewards",label:"Level role rewards",type:"rewards"}
    ]
  },
  {
    key:"suggestions",name:"Suggestions",description:"Collect ideas with voting, discussion threads and staff statuses.",category:"Community",
    defaults:{channelId:"",createThread:true,statuses:["Submitted","Reviewing","Planned","Added","Declined"]},
    fields:[
      {key:"channelId",label:"Suggestions channel",type:"channel"},
      {key:"createThread",label:"Create a discussion thread",type:"toggle"},
      {key:"statuses",label:"Suggestion statuses",type:"list",placeholder:"Submitted\nReviewing\nPlanned\nAdded\nDeclined"}
    ]
  },
  {
    key:"tickets",name:"Tickets & reports",description:"Private support, reports, appeals and partnership requests.",category:"Community",
    defaults:{panels:[
      {id:"support",name:"Ticket Support",enabled:true,panelChannelId:"",categoryId:"",staffRoleIds:[],types:["Support","Report","Appeal","Partnership","Other"]},
      {id:"applications",name:"Staff Applications",enabled:true,panelChannelId:"",categoryId:"",staffRoleIds:[],types:["Staff Application"]},
      {id:"trading-school",name:"Trading School",enabled:true,panelChannelId:"",categoryId:"",staffRoleIds:[],types:["Trading School","Lesson Support","Student Question"]}
    ],panelChannelId:"",categoryId:"",staffRoleIds:[],logChannelId:"",types:["Support","Report","Appeal","Partnership","Staff Application","Other"]},
    fields:[
      {key:"panels",label:"Ticket panels",help:"Create separate panels for support, applications, trading school or anything else.",type:"ticketPanels"},
      {key:"logChannelId",label:"Ticket log channel",type:"channel"},
      {key:"types",label:"Fallback ticket reasons",type:"list",placeholder:"Support\nReport\nAppeal\nPartnership\nOther"}
    ]
  },
  {
    key:"giveaways",name:"Giveaways",description:"Run server giveaways with account-age protection and booster perks.",category:"Engagement",
    defaults:{channelId:"",minAccountAgeDays:3,boosterBonusEntries:0},
    fields:[
      {key:"channelId",label:"Giveaway channel",type:"channel"},
      {key:"minAccountAgeDays",label:"Minimum account age",type:"number",min:0,max:3650},
      {key:"boosterBonusEntries",label:"Booster bonus entries",type:"number",min:0,max:20}
    ]
  },
  {
    key:"starboard",name:"Starboard",description:"Promote community-favourite messages into a showcase channel.",category:"Engagement",
    defaults:{channelId:"",emoji:"⭐",threshold:5,allowSelf:false,ignoredChannelIds:[]},
    fields:[
      {key:"channelId",label:"Starboard channel",type:"channel"},
      {key:"emoji",label:"Reaction emoji",help:"Unicode emoji used to nominate messages.",type:"text",placeholder:"⭐"},
      {key:"threshold",label:"Reactions required",type:"number",min:2,max:100},
      {key:"allowSelf",label:"Allow self-reactions",type:"toggle"},
      {key:"ignoredChannelIds",label:"Ignored channels",type:"channels"}
    ]
  },
  {
    key:"automod",name:"Automod & anti-scam",description:"Protect the server from invite spam, phishing, mention spam and repeated messages.",category:"Moderation",
    defaults:{blockInvites:true,inviteBypassRoleIds:[],maxMentions:5,duplicateWindowSeconds:15,duplicateLimit:4,blockedTerms:[],blockedDomains:[],action:"delete",timeoutMinutes:10,modLogChannelId:""},
    fields:[
      {key:"blockInvites",label:"Block Discord invite links",type:"toggle"},
      {key:"inviteBypassRoleIds",label:"Roles allowed to post invites",type:"roles"},
      {key:"maxMentions",label:"Maximum mentions",type:"number",min:1,max:100},
      {key:"duplicateWindowSeconds",label:"Spam detection window",type:"number",min:1,max:300},
      {key:"duplicateLimit",label:"Repeated-message limit",type:"number",min:2,max:20},
      {key:"blockedTerms",label:"Blocked words or phrases",type:"list"},
      {key:"blockedDomains",label:"Blocked websites",type:"list"},
      {key:"action",label:"Automod action",type:"select",options:[{value:"delete",label:"Delete message"},{value:"timeout",label:"Delete + timeout"}]},
      {key:"timeoutMinutes",label:"Timeout length",type:"number",min:1,max:40320},
      {key:"modLogChannelId",label:"Moderation log channel",type:"channel"}
    ]
  },
  {
    key:"mod_tools",name:"Staff moderation",description:"Choose moderation roles and where staff actions are logged.",category:"Moderation",
    defaults:{staffRoleIds:[],modLogChannelId:""},
    fields:[
      {key:"staffRoleIds",label:"Moderation staff roles",type:"roles"},
      {key:"modLogChannelId",label:"Moderation log channel",type:"channel"}
    ]
  },
  {
    key:"join_security",name:"Join security",description:"Flag suspicious new accounts and sudden join spikes.",category:"Moderation",
    defaults:{minAccountAgeHours:24,alertChannelId:"",joinsPerMinuteAlert:8},
    fields:[
      {key:"minAccountAgeHours",label:"Young-account threshold",type:"number",min:0,max:8760},
      {key:"alertChannelId",label:"Security alert channel",type:"channel"},
      {key:"joinsPerMinuteAlert",label:"Raid alert threshold",type:"number",min:2,max:100}
    ]
  },
  {
    key:"scheduled_messages",name:"Scheduled messages",description:"Recurring announcements and reminders in the server timezone.",category:"Automation",
    defaults:{timezone:"Europe/London"},
    fields:[{key:"timezone",label:"Server timezone",type:"select",options:[{value:"Europe/London",label:"UK (Europe/London)"},{value:"Europe/Paris",label:"Central Europe"},{value:"America/New_York",label:"US Eastern"},{value:"America/Chicago",label:"US Central"},{value:"America/Los_Angeles",label:"US Pacific"},{value:"UTC",label:"UTC"}]}]
  },
  {
    key:"social_feeds",name:"Content feeds",description:"Route X, RSS, Reddit, YouTube and webhook content into Discord.",category:"Social",
    defaults:{defaultMentionRoleId:"",compactEmbeds:true},
    fields:[
      {key:"defaultMentionRoleId",label:"Default notification role",type:"role"},
      {key:"compactEmbeds",label:"Use compact posts",type:"toggle"}
    ]
  },
  {
    key:"premium_billing",name:"Premium memberships",description:"Premium Discord access, Stripe billing and referral attribution.",category:"Billing",
    defaults:{gracePastDue:true,removeRoleOnCancel:true,allowPromotionCodes:true,referralsEnabled:true},
    fields:[
      {key:"gracePastDue",label:"Keep access during payment retries",type:"toggle"},
      {key:"removeRoleOnCancel",label:"Remove Premium when access ends",type:"toggle"},
      {key:"allowPromotionCodes",label:"Allow discount codes",type:"toggle"},
      {key:"referralsEnabled",label:"Enable referral codes",type:"toggle"}
    ]
  }
];

export const moduleMap=new Map(modules.map(m=>[m.key,m]));
