type ChannelChoice = { id: string; type: number };
type RoleChoice = { id: string };

const textChannels = (channels: ChannelChoice[]) => new Set(channels.filter(channel => channel.type !== 4 && channel.type !== 2).map(channel => channel.id));
const roleIds = (roles: RoleChoice[]) => new Set(roles.map(role => role.id));
const boundedInteger = (value: unknown, min: number, max: number) => {
  const raw = String(value ?? "").trim();
  if (!/^\d+$/.test(raw)) return false;
  const number = Number(raw);
  return Number.isSafeInteger(number) && number >= min && number <= max;
};

export function validateOnboardingInput(input: Record<string, unknown>, channels: ChannelChoice[], roles: RoleChoice[]) {
  const errors: string[] = [];
  const allowedChannels = textChannels(channels), allowedRoles = roleIds(roles);
  if (input.channelId && !allowedChannels.has(String(input.channelId))) errors.push("Choose an onboarding text channel that still exists.");
  const selectedRoles = Object.entries(input).filter(([key, value]) => /^(verifiedRoleId|quarantineRoleId|platform_|interest_|notification_)/.test(key) && value);
  if (selectedRoles.some(([, value]) => !allowedRoles.has(String(value)))) errors.push("One of the selected roles is unavailable or above the bot’s role. Refresh the page and choose again.");
  if (!boundedInteger(input.minAccountAgeHours ?? "24", 0, 8760)) errors.push("Minimum account age must be between 0 and 8,760 hours.");
  const title = String(input.welcomeTitle ?? "").trim(), body = String(input.welcomeBody ?? "").trim();
  if (title.length > 100) errors.push("Panel title must be 100 characters or fewer.");
  if (body.length > 1800) errors.push("Panel text must be 1,800 characters or fewer.");
  const questions = String(input.questions ?? "").split(/\r?\n/).map(question => question.trim()).filter(Boolean);
  if (questions.length > 5 || questions.some(question => question.length > 100)) errors.push("Use up to five questions, each 100 characters or fewer.");
  return errors;
}

export function validateBirthdayInput(input: Record<string, unknown>, channels: ChannelChoice[], roles: RoleChoice[]) {
  const errors: string[] = [], allowedChannels = textChannels(channels), allowedRoles = roleIds(roles);
  const enabled = input.enabled === "on" || input.enabled === true || input.enabled === "true";
  if (input.channelId && !allowedChannels.has(String(input.channelId))) errors.push("Choose an announcement text channel that still exists.");
  if (input.roleId && !allowedRoles.has(String(input.roleId))) errors.push("Choose an available birthday role below the bot’s role.");
  if (enabled && !input.channelId) errors.push("Choose an announcement channel before enabling birthday announcements.");
  if (!boundedInteger(input.xpReward ?? "50", 0, 1000000) || !boundedInteger(input.coinReward ?? "100", 0, 1000000)) errors.push("Birthday rewards must be whole numbers from 0 to 1,000,000.");
  return errors;
}

export function validateCountingInput(input: Record<string, unknown>, channels: ChannelChoice[]) {
  const errors: string[] = [], allowedChannels = textChannels(channels);
  const enabled = input.enabled === "on" || input.enabled === true || input.enabled === "true";
  if (input.channelId && !allowedChannels.has(String(input.channelId))) errors.push("Choose a counting text channel that still exists.");
  if (enabled && !input.channelId) errors.push("Choose a channel before enabling counting.");
  if (!boundedInteger(input.nextNumber ?? "1", 1, 2147483647)) errors.push("Next number must be a whole number from 1 to 2,147,483,647.");
  if (!boundedInteger(input.rewardEvery ?? "100", 0, 2147483647)) errors.push("Reward interval must be 0 (off) or a whole number up to 2,147,483,647.");
  return errors;
}

export function validateServerCounterInput(input: Record<string, unknown>, channels: ChannelChoice[]) {
  const errors: string[] = [];
  const channel = channels.find(choice => choice.id === String(input.channelId ?? ""));
  if (!channel || channel.type !== 2) errors.push("Choose a voice channel for a live server counter.");
  if (!new Set(["members", "online", "premium", "boosters", "verified"]).has(String(input.metric ?? "members"))) errors.push("Choose a supported counter type.");
  const label = String(input.label ?? "").trim();
  if (!label || label.length > 100 || (label.match(/\{count\}/g) || []).length !== 1) errors.push("Counter name must be 1–100 characters and include {count} exactly once.");
  return errors;
}

export function validateSecurityPolicy(input: Record<string, unknown>, roleChoices: RoleChoice[], memberChoices: Array<{ id: string }> = []) {
  const errors: string[] = [];
  const checks: Array<[string, number, number, string]> = [
    ["minAccountAgeHours", 0, 8760, "Minimum account age must be 0–8,760 hours."],
    ["joinsPerMinute", 2, 1000, "Raid threshold must be 2–1,000 joins per minute."],
    ["actionWindowSeconds", 10, 3600, "Action window must be 10–3,600 seconds."],
    ["maxDestructiveActions", 1, 100, "Destructive action limit must be 1–100."]
  ];
  for (const [key, min, max, message] of checks) if (!boundedInteger(input[key] ?? ({minAccountAgeHours:"24",joinsPerMinute:"8",actionWindowSeconds:"60",maxDestructiveActions:"4"} as Record<string,string>)[key], min, max)) errors.push(message);
  const availableRoles = roleIds(roleChoices), selected = Array.isArray(input.trustedRoleIds) ? input.trustedRoleIds : input.trustedRoleIds ? [input.trustedRoleIds] : [];
  if (selected.some(role => !availableRoles.has(String(role)))) errors.push("One trusted role is no longer in this server. Refresh and choose the roles again.");
  const availableMembers = new Set(memberChoices.map(member => member.id));
  const selectedMembers = Array.isArray(input.trustedUserIds) ? input.trustedUserIds : input.trustedUserIds ? [input.trustedUserIds] : [];
  if (selectedMembers.some(member => !availableMembers.has(String(member)))) errors.push("One trusted member is no longer in this server. Refresh and choose the members again.");
  return errors;
}

export const dashboardWidgetKeys = ["retention", "kudos", "premium", "referrals", "security", "tickets", "economy", "giveaways", "partners", "feature_usage"] as const;
export function validateDashboardWidgets(value: unknown) {
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  return selected.every(key => dashboardWidgetKeys.includes(String(key) as typeof dashboardWidgetKeys[number]));
}

function validHttpUrl(value: unknown) {
  if (!value) return true;
  try { return ["https:", "http:"].includes(new URL(String(value)).protocol); } catch { return false; }
}

export function validateStudioTemplate(input: Record<string, unknown>, roleChoices: RoleChoice[]) {
  const errors: string[] = [], availableRoles = roleIds(roleChoices);
  const name = String(input.name ?? "").trim(), body = String(input.body ?? "");
  const types = new Set(["announcement", "server update", "maintenance", "event", "giveaway", "premium", "help panel"]);
  if (!name || name.length > 80) errors.push("Template name must be 1–80 characters.");
  if (!types.has(String(input.templateType ?? ""))) errors.push("Choose a message type from the list.");
  if (!body.trim() || body.length > 4000) errors.push("Message text must be 1–4,000 characters.");
  if (String(input.title ?? "").length > 256) errors.push("Message title must be 256 characters or fewer.");
  if (input.colour && !/^#?[0-9a-f]{6}$/i.test(String(input.colour))) errors.push("Accent colour must be a six-digit hex value, such as #27D7E8.");
  for (const key of ["imageUrl", "thumbnailUrl"]) if (!validHttpUrl(input[key])) errors.push(`${key === "imageUrl" ? "Image" : "Thumbnail"} URL must begin with http:// or https://.`);
  if (input.mentionRoleId && !availableRoles.has(String(input.mentionRoleId))) errors.push("Choose a mention role that still exists in this server.");
  for (let index = 1; index <= 5; index++) {
    const label = String(input[`button${index}Label`] ?? "").trim(), url = String(input[`button${index}Url`] ?? "").trim(), role = String(input[`button${index}Role`] ?? "").trim();
    if (label.length > 80) errors.push(`Button ${index} label must be 80 characters or fewer.`);
    if (url && (!label || !validHttpUrl(url))) errors.push(`Button ${index} needs a label and a valid http or https URL.`);
    if (role && !availableRoles.has(role)) errors.push(`Button ${index} uses a role that is no longer available.`);
  }
  for (let index = 1; index <= 5; index++) {
    const label = String(input[`option${index}Label`] ?? "").trim(), role = String(input[`option${index}Role`] ?? "").trim(), response = String(input[`option${index}Response`] ?? "");
    if (label.length > 100 || response.length > 1000) errors.push(`Dropdown option ${index} is too long.`);
    if ((role || response) && !label) errors.push(`Dropdown option ${index} needs a label before its role or reply can be saved.`);
    if (role && !availableRoles.has(role)) errors.push(`Dropdown option ${index} uses a role that is no longer available.`);
  }
  return [...new Set(errors)];
}

export function validateRolePanel(input: Record<string, unknown>, channels: ChannelChoice[], assignableRoles: RoleChoice[], publishNow: boolean) {
  const errors: string[] = [], allowedChannels = textChannels(channels), allowedRoles = roleIds(assignableRoles);
  const name = String(input.name ?? "").trim(), title = String(input.title ?? ""), body = String(input.body ?? "");
  if (!name || name.length > 80) errors.push("Panel name must be 1–80 characters.");
  if (!new Set(["buttons", "select"]).has(String(input.panelType ?? "buttons"))) errors.push("Choose Buttons or Dropdown for the panel style.");
  if (input.channelId && !allowedChannels.has(String(input.channelId))) errors.push("Choose a text channel that still exists for this panel.");
  if (publishNow && !input.channelId) errors.push("Choose a text channel before publishing the panel.");
  if (title.length > 256 || body.length > 4000) errors.push("Panel title must be 256 characters and body 4,000 characters or fewer.");
  const roles = Array.from({ length: 10 }, (_, index) => String(input[`role${index + 1}Id`] ?? "").trim()).filter(Boolean);
  if (roles.length > 25 || roles.some(role => !allowedRoles.has(role))) errors.push("Panel roles must be selected from the available roles the bot can assign.");
  if (publishNow && !roles.length) errors.push("Add at least one assignable role before publishing this panel.");
  for (let index = 1; index <= 10; index++) if (String(input[`role${index}Label`] ?? "").length > 80) errors.push(`Role ${index} label must be 80 characters or fewer.`);
  return [...new Set(errors)];
}

export function validateReactionRole(input: Record<string, unknown>, channels: ChannelChoice[], assignableRoles: RoleChoice[]) {
  const errors: string[] = [], allowedChannels = textChannels(channels), allowedRoles = roleIds(assignableRoles);
  if (!allowedChannels.has(String(input.channelId ?? ""))) errors.push("Choose a text channel that still exists.");
  if (!/^\d{15,22}$/.test(String(input.messageId ?? ""))) errors.push("Enter the 15–22 digit ID of the Discord message.");
  if (!String(input.emoji ?? "").trim() || String(input.emoji).length > 100) errors.push("Choose one valid emoji.");
  if (!allowedRoles.has(String(input.roleId ?? ""))) errors.push("Choose a role the bot can assign.");
  return errors;
}

export const economyQuestEvents = ["message", "daily_claim", "join", "helpful_received", "referral_conversion", "kudos_given"] as const;
export function validateEconomyQuest(input: Record<string, unknown>) {
  const errors: string[] = [], key = String(input.quest_key ?? "").trim(), name = String(input.name ?? "").trim();
  if (!/^[a-z0-9_-]{2,60}$/i.test(key)) errors.push("Quest key must be 2–60 letters, numbers, underscores or hyphens.");
  if (!name || name.length > 80) errors.push("Quest name must be 1–80 characters.");
  if (String(input.description ?? "").length > 500) errors.push("Quest description must be 500 characters or fewer.");
  if (!["daily", "weekly", "season", "lifetime"].includes(String(input.cadence ?? ""))) errors.push("Choose a valid quest schedule.");
  if (!economyQuestEvents.includes(String(input.event_type ?? "") as typeof economyQuestEvents[number])) errors.push("Choose an event the bot can track.");
  for (const [field, min, max, label] of [["target", 1, 1000000, "Target"], ["xp_reward", 0, 1000000, "XP reward"], ["coin_reward", 0, 1000000, "Coin reward"], ["sort_order", 0, 10000, "Sort order"]] as const) {
    if (!boundedInteger(input[field] ?? (field === "target" ? "1" : field === "sort_order" ? "100" : "0"), min, max)) errors.push(`${label} must be a whole number from ${min.toLocaleString("en-GB")} to ${max.toLocaleString("en-GB")}.`);
  }
  return errors;
}

export function validateScheduledMessage(input: Record<string, unknown>, channels: ChannelChoice[]) {
  const errors: string[] = [], allowedChannels = textChannels(channels), name = String(input.name ?? "").trim(), content = String(input.content ?? "");
  if (!allowedChannels.has(String(input.channelId ?? ""))) errors.push("Choose a text channel that still exists.");
  if (!name || name.length > 80) errors.push("Post name must be 1–80 characters.");
  if (!content.trim() || content.length > 2000) errors.push("Post text must be 1–2,000 characters.");
  if (!boundedInteger(input.hour, 0, 23) || !boundedInteger(input.minute, 0, 59)) errors.push("Choose a valid time between 00:00 and 23:59.");
  const days = Array.isArray(input.days) ? input.days : input.days ? [input.days] : [];
  if (days.some(day => !/^[0-6]$/.test(String(day))) || new Set(days.map(String)).size !== days.length) errors.push("Choose valid, non-duplicate weekdays.");
  return errors;
}

export function validateNativePoll(input: Record<string, unknown>, channels: ChannelChoice[]) {
  const errors: string[] = [], allowedChannels = textChannels(channels), answers = String(input.answers ?? "").split(/\r?\n/).map(answer => answer.trim()).filter(Boolean);
  if (!allowedChannels.has(String(input.channelId ?? ""))) errors.push("Choose a text channel in this server.");
  if (!String(input.question ?? "").trim() || String(input.question).length > 300) errors.push("Poll question must be 1–300 characters.");
  if (answers.length < 2 || answers.length > 10 || answers.some(answer => answer.length > 55)) errors.push("Add 2–10 answers, each 55 characters or fewer.");
  if (!boundedInteger(input.duration ?? "24", 1, 168)) errors.push("Poll duration must be 1–168 hours.");
  return errors;
}

export function validateNativeEvent(input: Record<string, unknown>, now = Date.now()) {
  const errors: string[] = [], name = String(input.name ?? "").trim(), description = String(input.description ?? ""), location = String(input.location ?? "").trim(), start = new Date(String(input.startsAt ?? "")), duration = Number(input.duration);
  if (!name || name.length > 100) errors.push("Event name must be 1–100 characters.");
  if (description.length > 1000 || location.length > 100) errors.push("Description must be at most 1,000 characters and location at most 100.");
  if (!Number.isFinite(start.getTime()) || start.getTime() <= now) errors.push("Choose a start time in the future.");
  if (!boundedInteger(input.duration ?? "60", 15, 10080)) errors.push("Event duration must be 15–10,080 minutes.");
  return errors;
}
