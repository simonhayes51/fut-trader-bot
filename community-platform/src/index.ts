import fs from "node:fs/promises";
import path from "node:path";
import { config } from "./config.js";
import { db } from "./db.js";
import { startBot, client } from "./bot.js";
import { app } from "./dashboard.js";
import { secureSetupRouter } from "./secure-setup.js";
import { extrasRouter } from "./dashboard-extras.js";
import { nativeDiscordRouter } from "./native-discord.js";
import { pollSocialFeeds } from "./social.js";
import { runAutomationTick } from "./feature-suite.js";
import { economyRouter } from "./economy-dashboard.js";
import { runEconomyTick } from "./economy.js";

app.use(secureSetupRouter);
app.use(extrasRouter);
app.use(nativeDiscordRouter);
app.use(economyRouter);

async function readSql(name:string) {return fs.readFile(path.join(process.cwd(),"src",name),"utf8").catch(()=>fs.readFile(path.join(process.cwd(),"dist",name),"utf8"));}
async function initSchema() {await db.query(await readSql("schema.sql"));await db.query(await readSql("schema-v2.sql"));await db.query(await readSql("schema-v3.sql"));}
async function main(){await initSchema();await startBot();app.listen(config.port,()=>console.log(`Dashboard listening on ${config.baseUrl}`));setInterval(()=>pollSocialFeeds().catch(console.error),config.socialPollSeconds*1000);setTimeout(()=>pollSocialFeeds().catch(console.error),5000);setInterval(()=>runAutomationTick(client).catch(console.error),60_000);setTimeout(()=>runAutomationTick(client).catch(console.error),10_000);setInterval(()=>runEconomyTick(client).catch(console.error),60_000);setTimeout(()=>runEconomyTick(client).catch(console.error),15_000);}
main().catch(err=>{console.error(err);process.exit(1);});
