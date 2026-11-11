import html
import re
import time
import urllib.request

BACKLASH_URL = "https://www.backlash.co.jp/e/item_list/00102/?lm=120&od=1&kop=1"
PRODUCT_URL = "https://www.backlash.co.jp/e/item/{}/"
CARD = re.compile(
    r'<p class="pn"><a href="/e/item/(\d+)/">([^<]+)</a></p>'
    r'\s*<p class="sp">&yen;([0-9,]+)'
)


def _get(url):
    request = urllib.request.Request(url, headers={"Accept": "text/html"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                encoding = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(encoding, errors="replace")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def fetch_backlash(max_pages=60):
    items = {}
    for page_number in range(1, max_pages + 1):
        url = BACKLASH_URL if page_number == 1 else f"{BACKLASH_URL}&p={page_number}"
        page = _get(url)
        if "</html>" not in page[-4096:].lower():
            raise RuntimeError(f"страница {page_number} загрузилась не полностью")
        count_before = len(items)
        for uid, name, raw_price in CARD.findall(page):
            items[uid] = {
                "uid": f"bl{uid}",
                "name": html.unescape(name).strip(),
                "price": int(raw_price.replace(",", "")),
                "link": PRODUCT_URL.format(uid),
                "shop": "BackLash",
                "stock": True,
            }
        if len(items) == count_before:
            raise RuntimeError(f"на странице {page_number} нет новых карточек")
        if "pagerNextText" not in page:
            return list(items.values())
    raise RuntimeError(f"достигнут лимит в {max_pages} страниц, каталог прочитан не полностью")
