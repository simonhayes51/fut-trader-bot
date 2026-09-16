import fs from "node:fs/promises";
import path from "node:path";
import { config } from "./config.js";
import { db } from "./db.js";
import { startBot } from "./bot.js";
import { app } from "./dashboard.js";
import { pollSocialFeeds } from "./social.js";

async function initSchema() {
  const sql=await fs.readFile(path.join(process.cwd(),"src","schema.sql"),"utf8").catch(()=>fs.readFile(path.join(process.cwd(),"dist","schema.sql"),"utf8"));
  await db.query(sql);
}

async function main() {
  await initSchema();
  await startBot();
  app.listen(config.port,()=>console.log(`Dashboard listening on ${config.baseUrl}`));
  setInterval(()=>pollSocialFeeds().catch(console.error),config.socialPollSeconds*1000);
  setTimeout(()=>pollSocialFeeds().catch(console.error),5000);
}
main().catch(err=>{console.error(err);process.exit(1);});
