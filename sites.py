# -*- coding: utf-8 -*-
import re, urllib.request
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def _get(url):
    req=urllib.request.Request(url, headers={"User-Agent":UA, "Accept":"text/html,*/*", "Accept-Language":"en,ja;q=0.8"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="ignore")
        except: 
            import time; time.sleep(1)
            continue
    return ""

BACKLASH_URL="https://www.backlash.co.jp/e/item_list/00102/?lm=120&od=1&kop=1"

def fetch_backlash():
    items=[]; seen=set()
    # BackLash has 32 pages ×120 = ~3840 trout lures (English export, без налога)
    for p in range(1, 33):
        url=BACKLASH_URL if p==1 else f"{BACKLASH_URL}&p={p}"
        html=_get(url)
        # blocks: <p class="pn"><a href="/e/item/XXX/">NAME</a></p> + <p class="sp">&yen;PRICE</p>
        # price is &yen;1,800 or &yen;1,665 (0H)
        for m in re.finditer(r'<p class="pn"><a href="/e/item/(\d+)/">([^<]+)</a></p>\s*<p class="sp">&yen;([0-9,]+)', html):
            uid=m.group(1); name=m.group(2).strip(); price_raw=m.group(3)
            if uid in seen: continue
            seen.add(uid)
            try: price=int(price_raw.replace(",",""))
            except: price=None
            link=f"https://www.backlash.co.jp/e/item/{uid}/"
            items.append({"uid":f"bl{uid}","name":name,"price":price,"link":link,"shop":"BackLash","stock":True})
        # Last page has no Next
        if 'pagerNextText' not in html: break
        if len(items)>=5000: break
    return items

SOURCES=[("BackLash", fetch_backlash)]
