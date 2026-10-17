import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import ejs from "ejs";
import { modules, moduleSetupGaps, validateModuleConfig } from "../dist/modules.js";
import { scheduleCronMatches, scheduleLocalTime } from "../dist/schedule-time.js";
import { dashboardSidebar } from "../dist/admin-navigation.js";
import { validateBirthdayInput, validateCountingInput, validateDashboardWidgets, validateEconomyQuest, validateNativeEvent, validateNativePoll, validateOnboardingInput, validateReactionRole, validateRolePanel, validateScheduledMessage, validateSecurityPolicy, validateServerCounterInput, validateStudioTemplate } from "../dist/admin-validation.js";

const byKey = key => modules.find(item => item.key === key);
const makeGuild = () => {
  const roles = new Map([
    ["@everyone", { id: "@everyone" }],
    ["assignable", { id: "assignable", managed: false, position: 2 }],
    ["above-bot", { id: "above-bot", managed: false, position: 20 }]
  ]);
  const channels = new Map([
    ["general", { id: "general", type: 0, isTextBased: () => true }],
    ["category", { id: "category", type: 4 }]
  ]);
  return { id: "guild", channels: { cache: channels }, roles: { cache: roles }, members: { me: { roles: { highest: { position: 10 } } } } };
};

test("unset and incomplete features are reported as setup work", () => {
  assert.deepEqual(moduleSetupGaps("welcome", {}, false), ["Open settings to check this feature before turning it on."]);
  assert.ok(moduleSetupGaps("welcome", {}, true).some(text => text.includes("welcome channel")));
  assert.deepEqual(moduleSetupGaps("welcome", { channelId: "general" }, true), []);
});

test("an enabled welcome feature needs a valid channel before saving", () => {
  const guild = makeGuild();
  assert.ok(validateModuleConfig(byKey("welcome"), { channelId: "" }, guild, true).some(text => text.includes("Choose a destination channel")));
  assert.deepEqual(validateModuleConfig(byKey("welcome"), { channelId: "general", message: "Welcome" }, guild, true), []);
  assert.deepEqual(validateModuleConfig(byKey("welcome"), { channelId: "missing" }, guild, false), ["Welcome channel includes a channel that is missing or cannot receive messages."]);
});

test("numeric bounds are enforced by the server", () => {
  const issues = validateModuleConfig(byKey("starboard"), { channelId: "general", threshold: 101 }, makeGuild(), false);
  assert.ok(issues.some(text => text.includes("Reactions required must be a whole number")));
});

test("role menus reject roles the bot cannot assign", () => {
  const cfg = { channelId: "general", groups: [{ name: "Platform", roleIds: ["above-bot"] }] };
  assert.ok(validateModuleConfig(byKey("role_menus"), cfg, makeGuild(), true).some(text => text.includes("roles the bot can assign")));
});

test("disabled features may be saved before setup is complete", () => {
  assert.deepEqual(validateModuleConfig(byKey("welcome"), { channelId: "" }, makeGuild(), false), []);
});

test("scheduled post times follow the configured timezone in winter and summer", () => {
  const winter=scheduleLocalTime(new Date("2026-01-05T18:30:00.000Z"),"Europe/London");
  const summer=scheduleLocalTime(new Date("2026-07-05T17:30:00.000Z"),"Europe/London");
  assert.deepEqual([winter.hour,winter.minute,winter.weekday],[18,30,1]);
  assert.deepEqual([summer.hour,summer.minute,summer.weekday],[18,30,0]);
  assert.equal(scheduleCronMatches("30 18 * * 1,2,3,4,5",winter),true);
  assert.equal(scheduleCronMatches("30 18 * * 1,2,3,4,5",summer),false);
});

test("admin navigation stays compact and opens the group for the current route", () => {
  const html = dashboardSidebar("/modules/role_menus", { username: "Owner" });
  assert.match(html, /<details class="nav-group nav-collapsible" open><summary><span>Set up<\/span>/);
  assert.match(html, /href="\/control\/community" aria-current="page"/);
  assert.equal((html.match(/<details class="nav-group nav-collapsible"/g) || []).length, 4);
  assert.equal((html.match(/<details class="nav-group nav-collapsible" open>/g) || []).length, 1);
  assert.match(dashboardSidebar("/control"), /href="\/control" aria-current="page"/);
});

test("admin navigation escapes server and account labels", () => {
  const html = dashboardSidebar("/control", { username: "<Owner>", guilds: [{ id: "guild&1", name: "<Server>" }, { id: "guild2", name: "Second" }] });
  assert.match(html, /&lt;Owner&gt;/);
  assert.match(html, /<span class="admin-avatar">&lt;<\/span>/);
  assert.match(html, /&lt;Server&gt;/);
  assert.match(html, /value="guild&amp;1"/);
  assert.match(html, /<button class="btn-secondary small" type="submit">Switch server<\/button>/);
  assert.doesNotMatch(html, /onchange="this\.form\.submit\(\)"/);
});

test("onboarding settings reject stale Discord objects and out-of-range values", () => {
  const channels = [{ id: "general", type: 0 }, { id: "voice", type: 2 }, { id: "category", type: 4 }];
  const roles = [{ id: "member" }];
  assert.deepEqual(validateOnboardingInput({ channelId: "general", verifiedRoleId: "member", minAccountAgeHours: "24", welcomeTitle: "Welcome", welcomeBody: "Hello", questions: "One\nTwo" }, channels, roles), []);
  assert.ok(validateOnboardingInput({ channelId: "missing", verifiedRoleId: "above-bot", minAccountAgeHours: "-1", welcomeTitle: "x", welcomeBody: "y", questions: "" }, channels, roles).length >= 3);
});

test("birthday and counting need valid channels before activation and never clamp bad input silently", () => {
  const channels = [{ id: "general", type: 0 }], roles = [{ id: "member" }];
  assert.ok(validateBirthdayInput({ enabled: "on", channelId: "", roleId: "", xpReward: "5", coinReward: "10" }, channels, roles).some(issue => issue.includes("announcement channel")));
  assert.ok(validateBirthdayInput({ enabled: "off", xpReward: "-3", coinReward: "10" }, channels, roles).some(issue => issue.includes("whole numbers")));
  assert.ok(validateCountingInput({ enabled: "on", channelId: "stale", nextNumber: "0", rewardEvery: "-1" }, channels).length >= 3);
});

test("live counters only accept voice channels and one count placeholder", () => {
  const channels = [{ id: "text", type: 0 }, { id: "voice", type: 2 }, { id: "category", type: 4 }];
  assert.deepEqual(validateServerCounterInput({ channelId: "voice", metric: "members", label: "Members: {count}" }, channels), []);
  assert.ok(validateServerCounterInput({ channelId: "text", metric: "made-up", label: "Members" }, channels).length >= 3);
});

test("security limits and dashboard widget names are checked on the server", () => {
  assert.deepEqual(validateSecurityPolicy({ minAccountAgeHours: "24", joinsPerMinute: "8", actionWindowSeconds: "60", maxDestructiveActions: "4", trustedRoleIds: ["staff"], trustedUserIds: ["owner"] }, [{ id: "staff" }], [{ id: "owner" }]), []);
  assert.equal(validateSecurityPolicy({ minAccountAgeHours: "99999", joinsPerMinute: "1", actionWindowSeconds: "0", maxDestructiveActions: "0", trustedRoleIds: ["missing"], trustedUserIds: ["missing"] }, [{ id: "staff" }], [{ id: "owner" }]).length, 6);
  assert.equal(validateDashboardWidgets(["retention", "security"]), true);
  assert.equal(validateDashboardWidgets(["retention", "arbitrary-query"]), false);
});

test("redesigned admin task pages render their validation and empty states", () => {
  const onboarding = ejs.render(fs.readFileSync("views/control-onboarding.ejs", "utf8"), {
    saved: false, published: true, error: "", channels: [{ id: "voice", name: "Voice", type: 2 }, { id: "general", name: "general", type: 0 }], roles: [],
    onboarding: {}, birthday: { enabled: false, config: {} }, counting: {}, counters: [], counterDraft: {}
  }, { filename: "views/control-onboarding.ejs" });
  assert.match(onboarding, /Onboarding panel published to Discord/);
  assert.match(onboarding, /No live counters yet/);
  assert.match(onboarding, /name="channelId" required/);
  const security = ejs.render(fs.readFileSync("views/control-security.ejs", "utf8"), {
    user: {}, channels: [], roles: [], allRoles: [], members: [], feature: { config: {} }, findings: [], events: [], inspector: null, score: null, healthScan: null, requestedMember: "", requestedChannel: "", saved: false, error: "Choose a valid limit."
  }, { filename: "views/control-security.ejs" });
  assert.match(security, /role="alert"/);
  assert.match(security, /Not checked/);
  assert.match(security, /No scan has been run yet/);
  const cleanSecurity = ejs.render(fs.readFileSync("views/control-security.ejs", "utf8"), {
    user: {}, channels: [], roles: [], allRoles: [], members: [], feature: { config: {} }, findings: [], events: [], inspector: null, score: 100, healthScan: { scanned_at: "2026-10-17T12:00:00Z" }, requestedMember: "", requestedChannel: "", saved: false, error: ""
  }, { filename: "views/control-security.ejs" });
  assert.match(cleanSecurity, /100%/);
  assert.match(cleanSecurity, /Last scan:/);
  const studio = ejs.render(fs.readFileSync("views/control-studio.ejs", "utf8"), {
    user: {}, channels: [{ id: "general", name: "general", type: 0 }], roles: [], allRoles: [], templates: [], panels: [], reactions: [], saved: false, error: "Check this", draftForm: "studio-form", draft: { name: "<script>alert(1)</script>" }
  }, { filename: "views/control-studio.ejs" });
  assert.match(studio, /data-draft=/);
  assert.doesNotMatch(studio, /<script>alert\(1\)<\/script>/);
  assert.match(studio, /Action not completed/);
});

test("message studio validates Discord payloads before saving or publishing", () => {
  const channels = [{ id: "general", type: 0 }, { id: "voice", type: 2 }, { id: "category", type: 4 }];
  const roles = [{ id: "member" }];
  const validTemplate = { name: "News", templateType: "announcement", body: "Server update", colour: "#27D7E8", button1Label: "Read more", button1Url: "https://example.com", option1Label: "Join", option1Role: "member" };
  assert.deepEqual(validateStudioTemplate(validTemplate, roles), []);
  assert.ok(validateStudioTemplate({ ...validTemplate, body: "", colour: "red", button1Url: "javascript:alert(1)", option1Role: "missing" }, roles).length >= 4);
  assert.deepEqual(validateRolePanel({ name: "Platform roles", channelId: "general", panelType: "buttons", publishNow: "on", role1Id: "member" }, channels, roles, true), []);
  assert.ok(validateRolePanel({ name: "", channelId: "voice", panelType: "unknown", publishNow: "on" }, channels, roles, true).length >= 4);
  assert.deepEqual(validateReactionRole({ channelId: "general", messageId: "123456789012345678", emoji: "⭐", roleId: "member" }, channels, roles), []);
  assert.ok(validateReactionRole({ channelId: "voice", messageId: "bad", emoji: "", roleId: "missing" }, channels, roles).length >= 4);
});

test("economy quests only use tracked events and reject invalid reward values", () => {
  const valid = { quest_key: "daily_checkin", name: "Daily check-in", cadence: "daily", event_type: "daily_claim", target: "1", xp_reward: "25", coin_reward: "10", sort_order: "10" };
  assert.deepEqual(validateEconomyQuest(valid), []);
  assert.ok(validateEconomyQuest({ ...valid, event_type: "trade_logged", target: "0", xp_reward: "-5", name: "" }).length >= 3);
});

test("scheduled posts, native polls and Discord events validate destinations and limits", () => {
  const channels = [{ id: "general", type: 0 }, { id: "voice", type: 2 }, { id: "category", type: 4 }];
  assert.deepEqual(validateScheduledMessage({ name: "Morning", channelId: "general", content: "Hello", hour: "9", minute: "30", days: ["1", "3"] }, channels), []);
  assert.ok(validateScheduledMessage({ name: "", channelId: "voice", content: "", hour: "27", minute: "-1", days: ["7"] }, channels).length >= 4);
  assert.deepEqual(validateNativePoll({ channelId: "general", question: "Pick one", answers: "Buy\nHold", duration: "24" }, channels), []);
  assert.ok(validateNativePoll({ channelId: "voice", question: "", answers: "Only one", duration: "500" }, channels).length >= 3);
  const now = Date.now();
  assert.deepEqual(validateNativeEvent({ name: "Community night", startsAt: new Date(now + 3_600_000).toISOString(), duration: "60", location: "Discord" }, now), []);
  assert.ok(validateNativeEvent({ name: "", startsAt: new Date(now - 1).toISOString(), duration: "0" }, now).length >= 3);
});
