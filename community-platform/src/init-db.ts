import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { db } from "./db.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const sql = await fs.readFile(path.join(here, "schema.sql"), "utf8").catch(async () => {
  return fs.readFile(path.join(process.cwd(), "src", "schema.sql"), "utf8");
});
await db.query(sql);
console.log("Database initialised.");
await db.end();
