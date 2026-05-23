import re
import requests


_cache = {}


def search_stock(query: str) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    if query in _cache:
        return _cache[query]

    results = []
    try:
        url = "https://searchadapter.eastmoney.com/api/suggest/get"
        params = {
            "input": query,
            "type": 14,
            "token": "D43BF722C8E33BDC906FB84D85E326E8",
            "count": 8,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.eastmoney.com/",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("QuotationCodeTable", {}).get("Data", []):
                code = str(item.get("Code", "")).strip()
                name = str(item.get("Name", "")).strip()
                if _is_stock_code(code) and name:
                    results.append({"code": code, "name": name})
    except Exception:
        pass

    if not results:
        results = _tencent_search(query)

    _cache[query] = results
    return results


def _is_stock_code(code: str) -> bool:
    return bool(re.match(r"^(60|68|00|30|20|301|300)\d{4}$", code))


def _tencent_search(query: str) -> list[dict]:
    try:
        url = f"http://qt.gtimg.cn/q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            text = resp.text.strip()
            if "=" in text:
                parts = text.split("~")
                if len(parts) > 2:
                    code_raw = text.split("=")[0].split("_")[-1].strip()
                    if re.match(r"^\d{6}$", code_raw):
                        return [{"code": code_raw, "name": parts[1]}]
    except Exception:
        pass
    return []


def resolve_code(query: str) -> tuple[str | None, str | None]:
    query = query.strip()
    if re.match(r"^\d{6}$", query):
        return query, None

    results = search_stock(query)
    if results:
        return results[0]["code"], results[0]["name"]

    return None, None


def get_stock_name_from_code(code: str) -> str | None:
    code = code.strip()
    if re.match(r"^\d{6}$", code):
        results = search_stock(code)
        if results:
            return results[0]["name"]
    return None
