function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export const config = {
  discordToken: required("DISCORD_TOKEN"),
  clientId: required("DISCORD_CLIENT_ID"),
  clientSecret: required("DISCORD_CLIENT_SECRET"),
  redirectUri: process.env.DISCORD_REDIRECT_URI || "http://localhost:3000/auth/discord/callback",
  targetGuildId: required("TARGET_GUILD_ID"),
  databaseUrl: required("DATABASE_URL"),
  sessionSecret: required("SESSION_SECRET"),
  port: Number(process.env.PORT || 3000),
  baseUrl: stripTrailingSlash(process.env.BASE_URL || "http://localhost:3000"),
  botInvitePermissions: process.env.DISCORD_BOT_INVITE_PERMISSIONS || "8",
  adminIds: new Set((process.env.DASHBOARD_ADMIN_IDS || "").split(",").map(v => v.trim()).filter(Boolean)),
  xBearerToken: process.env.X_BEARER_TOKEN || "",
  socialPollSeconds: Math.max(60, Number(process.env.SOCIAL_POLL_SECONDS || 120)),
  stripeSecretKey: process.env.STRIPE_SECRET_KEY || "",
  stripeWebhookSecret: process.env.STRIPE_WEBHOOK_SECRET || "",
  billingCurrency: (process.env.BILLING_CURRENCY || "gbp").toLowerCase(),
  systemBannerUrl: process.env.SYSTEM_BANNER_URL || "",
  systemLogoUrl: process.env.SYSTEM_LOGO_URL || "",
  statusUpdateSeconds: Math.max(30, Number(process.env.STATUS_UPDATE_SECONDS || 60))
};

function required(key: string): string {
  const value = process.env[key];
  if (!value) throw new Error(`Missing required environment variable: ${key}`);
  return value;
}
