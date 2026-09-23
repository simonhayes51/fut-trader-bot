import {
  ActionRowBuilder,
  PermissionFlagsBits,
  StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder,
  TextChannel
} from "discord.js";
import { BRAND, guildSystemEmbed } from "./brand.js";

function roleEmoji(name: string) {
  const n = name.toLowerCase();
  if (n.includes("pc")) return "🖥️";
  if (n.includes("console") || n.includes("playstation") || n.includes("ps5") || n.includes("ps4") || n.includes("xbox")) return "🎮";
  if (n.includes("mobile")) return "📱";
  if (n.includes("premium") || n.includes("vip")) return "💎";
  if (n.includes("announce") || n.includes("news")) return "📢";
  if (n.includes("giveaway")) return "🎉";
  if (n.includes("trade") || n.includes("trading") || n.includes("profit")) return "📈";
  if (n.includes("social") || n.includes("tiktok") || n.includes("instagram")) return "📱";
  return undefined;
}

export async function publishRoleMenusForGuild(guild: any, channel: any, groups: any[]) {
  const me = guild.members.me;
  if (!me) throw new Error("Bot member is not available in the server.");

  const permissions = channel.permissionsFor?.(me);
  if (permissions && (!permissions.has(PermissionFlagsBits.ViewChannel) || !permissions.has(PermissionFlagsBits.SendMessages))) {
    throw new Error("The bot needs View Channel and Send Messages permission in the selected role channel.");
  }

  let posted = 0;
  for (let index = 0; index < groups.length; index++) {
    const group = groups[index] || {};
    const roleIds = Array.isArray(group.roleIds) ? group.roleIds : [];
    const options = roleIds.map((id: string) => {
      const role = guild.roles.cache.get(id);
      if (!role || role.managed || role.position >= me.roles.highest.position) return null;
      const option = new StringSelectMenuOptionBuilder()
        .setLabel(role.name.slice(0, 100))
        .setValue(role.id);
      const emoji = roleEmoji(role.name);
      if (emoji) option.setEmoji(emoji);
      return option;
    }).filter((option: StringSelectMenuOptionBuilder | null): option is StringSelectMenuOptionBuilder => Boolean(option));

    if (!options.length) continue;

    const maxSelect = Number(group.maxSelect || 1) === 1 ? 1 : Math.min(25, options.length);
    const menu = new StringSelectMenuBuilder()
      .setCustomId(`role-menu:${index}`)
      .setPlaceholder(String(group.name || "Choose roles").slice(0, 100))
      .setMinValues(0)
      .setMaxValues(maxSelect)
      .addOptions(...options.slice(0, 25));

    const description = maxSelect === 1
      ? "Choose one role from the menu below."
      : "Choose any roles that apply to you from the menu below.";
    const optionList = options
      .map((option: any) => {
        const data = option.toJSON();
        const emoji = data.emoji?.name ? `${data.emoji.name} ` : "";
        return `${emoji}${data.label}`;
      })
      .join("\n");

    await (channel as TextChannel).send({
      embeds: [await guildSystemEmbed(
        guild.id,
        String(group.name || "Choose roles").slice(0, 256),
        `${description}\n\n**📍 Selection options:**\n${optionList}`,
        BRAND.colours.primary
      )],
      components: [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)]
    });
    posted++;
  }

  return posted;
}
