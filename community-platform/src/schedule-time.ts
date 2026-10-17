export type ScheduleLocalTime={year:string;month:string;day:string;hour:number;minute:number;weekday:number};

export function scheduleLocalTime(date:Date,timeZone:string):ScheduleLocalTime {
  const parts=new Intl.DateTimeFormat("en-GB",{timeZone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",weekday:"short",hourCycle:"h23"}).formatToParts(date);
  const value=(type:string)=>parts.find(part=>part.type===type)?.value||"00";
  const weekdays:Record<string,number>={Sun:0,Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6};
  return {year:value("year"),month:value("month"),day:value("day"),hour:Number(value("hour")),minute:Number(value("minute")),weekday:weekdays[value("weekday").slice(0,3)]??0};
}

export function scheduleCronMatches(expression:string,local:ScheduleLocalTime):boolean {
  const fields=expression.trim().split(/\s+/),minute=fields[0]||"*",hour=fields[1]||"*",day=fields[4]||"*";
  const matches=(field:string,value:number)=>field==="*"||field.split(",").map(Number).includes(value);
  return matches(minute,local.minute)&&matches(hour,local.hour)&&matches(day,local.weekday);
}
