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
    if (t.includes("premium")) return "⭐";
    return "💬";
  };
  return source.slice(0, 25).map(type => new StringSelectMenuOptionBuilder()
    .setLabel(`${type} Ticket`.replace(/ Ticket Ticket$/, " Ticket").slice(0, 100))
    .setValue(type.slice(0, 100))
    .setEmoji(emojiFor(type)));
}

export async function publishTicketPanelForGuild(guildId: string, channel: any, types: string[]) {
  const menu = new StringSelectMenuBuilder()
    .setCustomId("v5:ticket-menu")
    .setPlaceholder("Choose a ticket reason")
    .addOptions(...ticketMenuOptions(types));

  const reasons = (types.length ? types : ["General", "Support", "Question", "Other"])
    .slice(0, 25)
    .map(type => `• ${type} Ticket`)
    .join("\n");

  return (channel as TextChannel).send({
    embeds: [await guildSystemEmbed(
      guildId,
      "Ticket Support",
      `Need help from staff? Choose the closest reason below and a private ticket will be created.\n\n**Ticket reasons**\n${reasons}`,
      BRAND.colours.primary
    )],
    components: [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)]
  });
}
