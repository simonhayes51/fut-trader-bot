import session from "express-session";
import { db } from "./db.js";

export class PostgresSessionStore extends session.Store {
  async get(sid:string,callback:(err:any,session?:session.SessionData|null)=>void) {
    try {
      const result=await db.query(`SELECT sess FROM user_sessions WHERE sid=$1 AND expire>now()`,[sid]);
      callback(null,result.rows[0]?.sess??null);
    } catch(err) { callback(err); }
  }

  async set(sid:string,sess:session.SessionData,callback?:(err?:any)=>void) {
    try {
      const expires=sess.cookie?.expires ? new Date(sess.cookie.expires) : new Date(Date.now()+(sess.cookie?.maxAge??7*24*60*60*1000));
      await db.query(`INSERT INTO user_sessions(sid,sess,expire) VALUES($1,$2::jsonb,$3)
        ON CONFLICT(sid) DO UPDATE SET sess=$2::jsonb,expire=$3`,[sid,JSON.stringify(sess),expires]);
      await db.query(`DELETE FROM user_sessions WHERE expire<=now()`);
      callback?.();
    } catch(err) { callback?.(err); }
  }

  async destroy(sid:string,callback?:(err?:any)=>void) {
    try { await db.query(`DELETE FROM user_sessions WHERE sid=$1`,[sid]); callback?.(); }
    catch(err) { callback?.(err); }
  }

  async touch(sid:string,sess:session.SessionData,callback?:(err?:any)=>void) {
    try {
      const expires=sess.cookie?.expires ? new Date(sess.cookie.expires) : new Date(Date.now()+(sess.cookie?.maxAge??7*24*60*60*1000));
      await db.query(`UPDATE user_sessions SET expire=$2 WHERE sid=$1`,[sid,expires]);
      callback?.();
    } catch(err) { callback?.(err); }
  }
}
