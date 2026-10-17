type GuildChoice = { id: string; name: string };
type AdminUser = { username?: string; avatar?: string; guilds?: GuildChoice[] };
type NavigationItem = [href: string, icon: string, label: string];

const groups: Array<{ label: string; items: NavigationItem[] }> = [
  { label: "Set up", items: [["/control/onboarding", "✧", "Welcome & onboarding"], ["/control/community", "◈", "Community tools"], ["/control/studio", "✦", "Messages & role menus"], ["/control/automation", "↻", "Scheduled posts & feeds"], ["/control/settings", "⚙", "All bot features"], ["/discord", "♢", "Discord tools"], ["/commands", "⌘", "Command access"]] },
  { label: "Manage", items: [["/control/kudos", "✳", "Engagement & levels"], ["/economy", "¤", "Coins & rewards"], ["/control/safety", "⊘", "Tickets & moderation"], ["/control/security", "◉", "Security & health"]] },
  { label: "Grow", items: [["/control/growth", "↗", "Invites & partnerships"], ["/billing", "◆", "Premium & billing"], ["/control/insights", "▦", "Insights & reports"], ["/audit", "≡", "Admin activity"]] },
  { label: "Server", items: [["/branding", "◈", "Name, logo & colours"], ["/invite", "+", "Add the bot"]] }
];

const routeAliases: Record<string, string[]> = {
  "/control/members": ["/members"],
  "/control/community": ["/modules/welcome", "/modules/role_menus", "/modules/suggestions", "/modules/tickets", "/modules/starboard"],
  "/control/insights": ["/analytics"],
  "/control/automation": ["/automation", "/social", "/modules/scheduled_messages", "/modules/social_feeds"],
  "/control/kudos": ["/control/engagement", "/modules/reputation", "/modules/levels", "/modules/giveaways"],
  "/economy": ["/control/rewards"],
  "/control/safety": ["/tickets", "/moderation", "/modules/automod", "/modules/mod_tools", "/modules/join_security"],
  "/control/security": ["/setup"],
  "/billing": ["/modules/premium_billing"]
};

function escapeHtml(value: unknown) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]!));
}

export function dashboardSidebar(pathname: string, user?: AdminUser, selectedId?: string) {
  const activeFor = (href: string) => {
    if (href === "/control") return pathname === "/control";
    if (href === "/branding" && (pathname === "/branding" || pathname === "/modules/server_branding")) return true;
    return [href, ...(routeAliases[href] || [])].some(route => pathname === route || pathname.startsWith(`${route}/`));
  };
  const link = ([href, icon, label]: NavigationItem, direct = false) =>
    `<a class="nav-link${direct ? " nav-direct" : ""}${activeFor(href) ? " active" : ""}" href="${href}"${activeFor(href) ? ' aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">${icon}</span><span>${label}</span></a>`;
  const directNav = ([["/control", "⌂", "Overview"], ["/control/members", "◎", "Members"]] as NavigationItem[]).map(item => link(item, true)).join("");
  const nav = groups.map(group => {
    const active = group.items.some(([href]) => activeFor(href));
    const links = group.items.map(item => link(item)).join("");
    return `<details class="nav-group nav-collapsible"${active ? " open" : ""}><summary><span>${group.label}</span><span class="nav-group-meta"><span>${group.items.length}</span><i aria-hidden="true">⌄</i></span></summary><div class="nav-group-items">${links}</div></details>`;
  }).join("");
  const rawUsername = user?.username || "Administrator";
  const username = escapeHtml(rawUsername);
  const initial = escapeHtml(rawUsername.trim().slice(0, 1).toUpperCase() || "A");
  const guilds = user?.guilds || [];
  const onlyGuild = guilds[0];
  const addServerLink = `<a class="server-add-link" href="/invite">Add bot to another server</a>`;
  const selector = guilds.length > 1 ? `<form class="server-switcher" method="post" action="/servers/select">
      <label for="admin-server-select">Server</label>
      <select id="admin-server-select" name="guildId">${guilds.map(g => `<option value="${escapeHtml(g.id)}" ${g.id === selectedId ? "selected" : ""}>${escapeHtml(g.name)}</option>`).join("")}</select>
      <button class="btn-secondary small" type="submit">Switch server</button>
      ${addServerLink}
    </form>` : onlyGuild ? `<div class="server-switcher readonly"><label>Server</label><strong>${escapeHtml(onlyGuild.name)}</strong>${addServerLink}</div>` : `<div class="server-switcher readonly"><label>Server</label>${addServerLink}</div>`;
  return `<aside class="sidebar">
    <a class="brand" href="/control"><span class="brand-mark">E</span><span class="brand-copy"><b>EAFC.Live</b><small>Discord Control</small></span></a>
    ${selector}
    <nav aria-label="Server administration"><div class="nav-label nav-home-label">Workspace</div>${directNav}${nav}</nav>
    <div class="sidebar-footer"><div class="admin-chip"><span class="admin-avatar">${initial}</span><span><b>${username}</b><small>Administrator</small></span></div><form method="post" action="/logout"><button class="icon-button" title="Log out" aria-label="Log out">↪</button></form></div>
  </aside>`;
}
