import csv
import json
from functools import cache

import requests

CLOUDFLARE_LOCATIONS_URL = "https://speed.cloudflare.com/locations"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

REGION_MAP = {
    "BD": "Asia Pacific",
    "BR": "South America",
    "CL": "South America",
    "CN": "Asia Pacific",
    "GB": "Europe",
    "IE": "Europe",
    "IN": "Asia Pacific",
    "MD": "Europe",
    "NZ": "Oceania",
    "RU": "Europe",
    "US": "North America",
    "UZ": "Asia Pacific",
}

IATA_ALIASES = {
    "JXG": "JNH",
    "KIV": "RMO",
}

EMPTY_LOCATION = {"lat": None, "lng": None, "cca2": None, "region": None}


@cache
def load_cloudflare_locations():
    # 优先使用 Cloudflare 自己的位置数据
    print("Fetching Cloudflare locations...")
    response = requests.get(
        CLOUDFLARE_LOCATIONS_URL,
        headers={"Referer": "https://speed.cloudflare.com/"},
        timeout=15,
    )
    response.raise_for_status()

    locations = {}
    for item in response.json():
        iata = (item.get("iata") or "").strip().upper()
        if not iata or item.get("lat") is None or item.get("lon") is None:
            continue

        locations[iata] = {
            "lat": item["lat"],
            "lng": item["lon"],
            "cca2": (item.get("cca2") or "").strip().upper() or None,
            "region": item.get("region"),
        }
    print(f"Loaded {len(locations)} locations from Cloudflare.")
    return locations


@cache
def load_ourairports_locations():
    # Cloudflare 缺失时，用 OurAirports 作为备用数据源
    print("Fetching OurAirports locations...")
    response = requests.get(OURAIRPORTS_URL, timeout=30)
    response.raise_for_status()

    locations = {}
    for row in csv.DictReader(response.text.splitlines()):
        iata = (row.get("iata_code") or "").strip().upper()
        if not iata:
            continue

        try:
            locations[iata] = {
                "lat": float(row["latitude_deg"]),
                "lng": float(row["longitude_deg"]),
                "cca2": (row.get("iso_country") or "").strip().upper() or None,
                "region": None,
            }
        except (KeyError, TypeError, ValueError):
            continue

    for alias, target in IATA_ALIASES.items():
        if target in locations:
            locations[alias] = locations[target]

    print(f"Loaded {len(locations)} locations from OurAirports.")
    return locations


def get_location(iata):
    iata = iata.strip().upper()
    if iata == "LOCAL":
        return EMPTY_LOCATION.copy()

    location = load_cloudflare_locations().get(iata)
    if not location:
        location = load_ourairports_locations().get(iata)

    if location:
        location = {**EMPTY_LOCATION, **location}
        location["region"] = REGION_MAP.get(location["cca2"], location["region"])
        return location

    print(f"Warning: no coordinates for {iata}")
    return EMPTY_LOCATION.copy()


def main():
    print("Reading input files...")
    with open("cloudflare-iata.json", "r", encoding="utf-8") as f:
        data_en = json.load(f)
    with open("cloudflare-iata-zh.json", "r", encoding="utf-8") as f:
        data_zh = json.load(f)

    # 生成完整数据
    print(f"Processing {len(data_en)} locations...")
    full_data = {}
    for iata, place in sorted(data_en.items()):
        full_data[iata] = {
            "place": place,
            "place_zh": data_zh.get(iata, place),
            **get_location(iata),
        }

    with open("cloudflare-iata-full.json", "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated cloudflare-iata-full.json with {len(full_data)} entries.")


if __name__ == "__main__":
    main()
