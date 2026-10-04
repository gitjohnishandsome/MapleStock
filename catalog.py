"""商品清單：比對 OCR 讀到的道具名稱，決定資料屬於 config.yaml 的哪個商品。"""


def all_items(cfg):
    return cfg.get("items") or []


def detect(cfg, names):
    """names：這批資料的道具名稱列表（可能含空字串或 OCR 雜訊）。
    回傳比對到的商品設定 dict；一個都比對不到，或同時比對到多個商品（混在一起，
    或 match 關鍵字互相重疊）都回傳 None——交給呼叫端當成無法判定來處理，不猜測。"""
    items = all_items(cfg)
    if not items:
        return None
    counts = [sum(it["match"] in (n or "") for n in names) for it in items]
    hits = [i for i, c in enumerate(counts) if c > 0]
    return items[hits[0]] if len(hits) == 1 else None


def find(cfg, name):
    """依商品名稱（例如資料庫裡的 item 值）找回對應設定；找不到回傳 None。"""
    for it in all_items(cfg):
        if it["name"] == name:
            return it
    return None
