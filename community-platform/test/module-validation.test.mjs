import test from "node:test";
import assert from "node:assert/strict";
import { modules, moduleSetupGaps, validateModuleConfig } from "../dist/modules.js";
import { scheduleCronMatches, scheduleLocalTime } from "../dist/schedule-time.js";

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
