import {
  ActionRowBuilder,
  StringSelectMenuBuilder,
  StringSelectMenuOptionBuilder,
  TextChannel
} from "discord.js";
import { BRAND, guildSystemEmbed } from "./brand.js";

export function ticketMenuOptions(types: string[]) {
  const source = types.length ? types : ["General", "Support", "Question", "Other"];
  const emojiFor = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes("support")) return "🛠️";
    if (t.includes("question")) return "❓";
    if (t.includes("report")) return "🚨";
    if (t.includes("appeal")) return "📣";
    if (t.includes("partner")) return "🤝";
    if (t.includes("application") || t.includes("apply")) return "📝";
    if (t.includes("premium")) return "⭐";
    return "💬";
  };
  return source.slice(0, 25).map(type => new StringSelectMenuOptionBuilder()
    .setLabel(`${type} Ticket`.replace(/ Ticket Ticket$/, " Ticket").slice(0, 100))
    .setValue(type.slice(0, 100))
    .setEmoji(emojiFor(type)));
}

export async function publishTicketPanelForGuild(guildId: string, channel: any, types: string[]) {
  const source = types.length ? types : ["General", "Support", "Question", "Other"];
  const menu = new StringSelectMenuBuilder()
    .setCustomId("v5:ticket-menu")
    .setPlaceholder("Choose your option")
    .addOptions(...ticketMenuOptions(types));

  const reasons = source
    .slice(0, 25)
    .map(type => {
      const emoji = type.toLowerCase().includes("application") ? "📝" :
        type.toLowerCase().includes("support") ? "🛠️" :
        type.toLowerCase().includes("question") ? "❓" :
        type.toLowerCase().includes("report") ? "🚨" :
        type.toLowerCase().includes("appeal") ? "📣" :
        type.toLowerCase().includes("partner") ? "🤝" :
        type.toLowerCase().includes("premium") ? "⭐" : "💬";
      return `${emoji} ${type} Ticket`.replace(/ Ticket Ticket$/, " Ticket");
    })
    .join("\n");

  return (channel as TextChannel).send({
    embeds: [await guildSystemEmbed(
      guildId,
      "🎟️ Ticket Support",
      `If you have a request, click the menu below.\n\n**📍 Selection options:**\n${reasons}`,
      BRAND.colours.primary
    )],
    components: [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)]
  });
}
