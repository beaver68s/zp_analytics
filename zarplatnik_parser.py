#!/usr/bin/env python3
"""
Сбор данных zarplatnik.com:
 1) Парсит встроенный JSON из HTML (быстро, 1 запрос).
 2) Достаёт справочники role/grade/city/format и все срезы (slices).
 3) Сохраняет CSV с данными, JSON со всем деревом и полный список URL-комбинаций.
 4) (опционально) Обходит все URL по очереди — если нужен именно HTTP-отклик.
"""

import csv
import json
import re
import time
from itertools import product
from pathlib import Path
from typing import Optional

import requests

BASE = "https://zarplatnik.com"
TRACK = "design"  # на любой странице направления лежит один и тот же data-объект
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; zarplatnik-parser/1.0)"}


# ---------- 1. Загрузка и распаковка Next.js payload ----------

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def extract_next_payload(html: str) -> str:
    """Склеиваем все строки из self.__next_f.push([1, "..."]) в один текст."""
    pushes = re.findall(r'self\.__next_f\.push\((\[.*?\])\)</script>', html, re.DOTALL)
    chunks = []
    for p in pushes:
        try:
            arr = json.loads(p)
        except json.JSONDecodeError:
            continue
        for item in arr:
            if isinstance(item, str):
                chunks.append(item)
    return "".join(chunks)


def extract_data_object(payload: str) -> dict:
    """Находим уникальный 'data':{'step':..., 'roles':..., 'slices':...} и парсим."""
    m = re.search(r'"data":\s*(\{)', payload)
    if not m:
        raise RuntimeError("Не нашёл data-объект в payload")
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(payload[m.start(1):])
    return data


# ---------- 2. Основной сбор ----------

def collect() -> dict:
    print(f"[*] Скачиваю /{TRACK}/ ...")
    html = fetch_html(f"{BASE}/{TRACK}/")
    payload = extract_next_payload(html)
    data = extract_data_object(payload)

    roles   = data["roles"]
    grades  = data["grades"]
    cities  = data["cities"]
    formats = data["formats"]
    slices  = data["slices"]

    print(f"    ролей:    {len(roles)}")
    print(f"    грейдов:  {len(grades)}")
    print(f"    городов:  {len(cities)}")
    print(f"    форматов: {len(formats)}")
    print(f"    всего возможных комбинаций: "
          f"{len(roles)*len(grades)*len(cities)*len(formats)}")
    print(f"    срезов с данными (slices):  {len(slices)}")

    return {
        "roles": roles, "grades": grades,
        "cities": cities, "formats": formats,
        "slices": slices,
    }


# ---------- 3. Сохранение ----------

def save_slices_csv(slices: dict, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "key", "role", "grade", "city", "format",
            "n", "p25", "p50", "p75", "from", "counts_json",
        ])
        for key, s in slices.items():
            parts = key.split("|")
            if len(parts) != 4:
                continue
            role, grade, city, fmt = parts
            w.writerow([
                key, role, grade, city, fmt,
                s.get("n"), s.get("p25"), s.get("p50"), s.get("p75"),
                s.get("from"),
                json.dumps(s.get("counts"), ensure_ascii=False),
            ])
    print(f"[+] CSV со срезами: {path}")


def save_full_json(data: dict, path: Path) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[+] Полный JSON:  {path}")


def save_all_urls(data: dict, path: Path) -> int:
    role_ids   = [r["id"] for r in data["roles"]]
    grade_ids  = [g["id"] for g in data["grades"]]
    city_ids   = [c["id"] for c in data["cities"]]
    format_ids = [f["id"] for f in data["formats"]]

    count = 0
    with path.open("w", encoding="utf-8") as f:
        for role, grade, city, fmt in product(role_ids, grade_ids, city_ids, format_ids):
            f.write(f"{BASE}/{TRACK}/?role={role}&grade={grade}"
                    f"&city={city}&format={fmt}\n")
            count += 1
    print(f"[+] {count} URL-комбинаций: {path}")
    return count


# ---------- 4. (опционально) Обход всех URL ----------

def crawl_all_urls(data: dict, out_path: Path,
                   delay: float = 0.3, limit: Optional[int] = None) -> None:
    """
    Долбит все URL последовательно. На каждой странице ищет <title> и наличие
    цифр в data-объекте. Полезно, если сервер отдаёт разные slices по URL.
    """
    role_ids   = [r["id"] for r in data["roles"]]
    grade_ids  = [g["id"] for g in data["grades"]]
    city_ids   = [c["id"] for c in data["cities"]]
    format_ids = [f["id"] for f in data["formats"]]

    session = requests.Session()
    session.headers.update(HEADERS)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "status", "n_slices", "sample_p50"])
        done = 0
        for role, grade, city, fmt in product(role_ids, grade_ids, city_ids, format_ids):
            url = (f"{BASE}/{TRACK}/?role={role}&grade={grade}"
                   f"&city={city}&format={fmt}")
            try:
                r = session.get(url, timeout=20)
                r.encoding = "utf-8"
                status = r.status_code
                payload = extract_next_payload(r.text) if status == 200 else ""
                slices = {}
                if payload:
                    try:
                        slices = extract_data_object(payload)["slices"]
                    except Exception:
                        pass
                sample_p50 = ""
                # ключ конкретной комбинации
                exact_key = f"{role}|{grade}|{city}|{fmt}"
                if exact_key in slices:
                    sample_p50 = slices[exact_key].get("p50", "")
                w.writerow([url, status, len(slices), sample_p50])
            except Exception as e:
                w.writerow([url, f"ERR:{e}", 0, ""])
            done += 1
            if limit and done >= limit:
                break
            time.sleep(delay)
        print(f"[+] Результаты обхода: {out_path} ({done} URL)")


# ---------- main ----------

def main():
    out_dir = Path("zarplatnik_data")
    out_dir.mkdir(exist_ok=True)

    data = collect()
    save_slices_csv(data["slices"], out_dir / "slices.csv")
    save_full_json(data,        out_dir / "full.json")
    save_all_urls(data,         out_dir / "all_urls.txt")

    # Раскомментируйте, если действительно нужно бить по всем URL:
    # crawl_all_urls(data, out_dir / "crawl.csv", delay=0.3)


if __name__ == "__main__":
    main()