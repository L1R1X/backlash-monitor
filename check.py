#!/usr/bin/env python3
import os, json, time, urllib.request, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
import sites
MSK=ZoneInfo("Europe/Moscow")
TELEGRAM_BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
TELEGRAM_CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID","").strip()
STATE_FILE="state.json"
def load_state():
    if not os.path.exists(STATE_FILE): return {"items":{}}
    try:
        d=json.load(open(STATE_FILE,encoding="utf-8"))
        return d if "items" in d else {"items":d}
    except: return {"items":{}}
def save_state(s):
    s["last_check"]=datetime.now(MSK).isoformat()
    json.dump(s, open(STATE_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(text[:700]); return False
    ok=False
    for cid in [c.strip() for c in TELEGRAM_CHAT_ID.split(",") if c.strip()]:
        data=urllib.parse.urlencode({"chat_id":cid,"text":text,"parse_mode":"HTML"}).encode()
        req=urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data, headers={"User-Agent":"backlash"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                ok=ok or json.load(r).get("ok")
                print(f"  [TG] -> {cid}: ok")
        except Exception as e: print(f"  [TG] {cid}: {e}")
    return ok
def main():
    print(f"=== BackLash check {datetime.now(MSK).isoformat()} ===")
    state=load_state(); old=state.get("items",{})
    print(f"в базе {len(old)}")
    now={}
    for name,fn in sites.SOURCES:
        t0=time.time()
        try:
            items=fn()
            for it in items: now[it["uid"]]=it
            print(f"  {name}: найдено {len(items)} за {time.time()-t0:.1f}с")
        except Exception as e: print(f"  {name} пропуск: {e}")
    new=[v for k,v in now.items() if k not in old]
    price_drop=[(old[k],v) for k,v in now.items() if k in old and v.get("price") and old[k].get("price") and v["price"]<old[k]["price"]]
    if new:
        lines=[f"🆕 <b>BackLash — {len(new)} новинок TROUT</b>\n"]
        for it in new[:10]:
            lines.append(f"• {it['name']}\n  ¥{it['price']:,}  🏬 {it['shop']}\n  {it['link']}\n")
        if len(new)>10: lines.append(f"... и ещё {len(new)-10} шт.")
        send_telegram("\n".join(lines))
    if price_drop:
        lines=[f"📉 <b>Снижение цены — {len(price_drop)}</b>\n"]
        for o,n in price_drop[:10]:
            lines.append(f"• {n['name']}\n  ¥{o['price']:,} → ¥{n['price']:,}  🏬 {n['shop']}\n  {n['link']}\n")
        send_telegram("\n".join(lines))
    if not new and not price_drop: print("Изменений нет")
    state["items"]=now; save_state(state)
    print(f"сохранено {len(now)}")
if __name__=="__main__": main()
