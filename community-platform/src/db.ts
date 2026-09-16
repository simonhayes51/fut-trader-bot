import pg from "pg";
import { config } from "./config.js";

const { Pool } = pg;
export const db = new Pool({
  connectionString: config.databaseUrl,
  ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : undefined
});

export async function query<T = any>(text: string, params: unknown[] = []): Promise<T[]> {
  const result = await db.query(text, params);
  return result.rows as T[];
}

export async function one<T = any>(text: string, params: unknown[] = []): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows[0] ?? null;
}

export async function audit(guildId: string, actorId: string | null, action: string, details: unknown = {}) {
  await query(
    `INSERT INTO audit_log(guild_id, actor_id, action, details) VALUES ($1,$2,$3,$4::jsonb)`,
    [guildId, actorId, action, JSON.stringify(details)]
  );
}

export async function getFeature<T extends Record<string, any> = Record<string, any>>(
  guildId: string,
  key: string,
  defaults: T
): Promise<{ enabled: boolean; config: T }> {
  const row = await one<{ enabled: boolean; config: T }>(
    `SELECT enabled, config FROM feature_settings WHERE guild_id=$1 AND feature_key=$2`,
    [guildId, key]
  );
  return row ? { enabled: row.enabled, config: { ...defaults, ...row.config } } : { enabled: true, config: defaults };
}
