import csv
import json
import os
import requests

# Constants
CLOUDFLARE_LOCATIONS_URL = "https://speed.cloudflare.com/locations"
OURAIRPORTS_AIRPORTS_URL = (
    "https://davidmegginson.github.io/ourairports-data/airports.csv"
)

REGION_MAP = {
    "CN": "Asia Pacific",
    "RU": "Europe",
    "GB": "Europe",
    "US": "North America",
    "IN": "Asia Pacific",
    "IE": "Europe",
    "UZ": "Asia Pacific",
    "BR": "South America",
    "BD": "Asia Pacific",
    "MD": "Europe",
    "NZ": "Oceania",
    "CL": "South America",
}

IATA_SPECIAL_CASES = {
    "JXG": "JNH",  # JNH (Jiaxing Nanhu Airport) was mistakenly recorded as JXG (Jiaxing Airport)
    "KIV": "RMO",  # On 18 January 2024, the IATA airport code KIV, derived from Kishinev (the Russian and former English name of the city), was changed to RMO (Republica Moldova, "Republic of Moldova" in Romanian).
}

# Global caches
_CLOUDFLARE_CACHE = {}
_OURAIRPORTS_CACHE = {}


def load_cloudflare_locations():
    """Fetch and cache Cloudflare location data."""
    global _CLOUDFLARE_CACHE
    if _CLOUDFLARE_CACHE:
        return _CLOUDFLARE_CACHE

    try:
        print("Fetching Cloudflare locations...")
        response = requests.get(
            CLOUDFLARE_LOCATIONS_URL,
            headers={"Referer": "https://speed.cloudflare.com/"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        for entry in data:
            iata = entry.get("iata")
            if iata and entry.get("lat") is not None and entry.get("lon") is not None:
                _CLOUDFLARE_CACHE[iata] = {
                    "lat": entry.get("lat"),
                    "lng": entry.get("lon"),
                    "cca2": entry.get("cca2"),
                    "region": entry.get("region"),
                }
        print(f"Loaded {len(_CLOUDFLARE_CACHE)} locations from Cloudflare.")
    except Exception as e:
        print(f"Error loading Cloudflare locations: {e}")

    return _CLOUDFLARE_CACHE


def load_ourairports_locations():
    """Lazy-load OurAirports data for fallback lookups."""
    global _OURAIRPORTS_CACHE
    if _OURAIRPORTS_CACHE:
        return _OURAIRPORTS_CACHE

    try:
        print("Fetching OurAirports data...")
        response = requests.get(OURAIRPORTS_AIRPORTS_URL, timeout=30)
        response.raise_for_status()

        reader = csv.DictReader(response.text.splitlines())
        for row in reader:
            iata = (row.get("iata_code") or "").strip().upper()
            lat = row.get("latitude_deg")
            lon = row.get("longitude_deg")
            cca2 = (row.get("iso_country") or "").strip().upper() or None

            if iata and lat and lon:
                try:
                    _OURAIRPORTS_CACHE[iata] = {
                        "lat": float(lat),
                        "lng": float(lon),
                        "cca2": cca2,
                    }
                except ValueError:
                    continue
        for special_iata, mapped_iata in IATA_SPECIAL_CASES.items():
            if mapped_iata in _OURAIRPORTS_CACHE:
                _OURAIRPORTS_CACHE[special_iata] = _OURAIRPORTS_CACHE[mapped_iata]
        print(f"Loaded {len(_OURAIRPORTS_CACHE)} locations from OurAirports.")
    except Exception as e:
        print(f"Error loading OurAirports data: {e}")

    return _OURAIRPORTS_CACHE


def get_location_details(iata_code):
    """
    Look up latitude, longitude, country code, and region for an IATA code.
    """
    if iata_code == "LOCAL":
        return None, None, None, None

    lookup_code = iata_code.upper()

    # 1. Try Cloudflare
    cf_locations = load_cloudflare_locations()
    location = cf_locations.get(lookup_code)

    if location:
        lat = location["lat"]
        lng = location["lng"]
        cca2 = location["cca2"]
        region = location["region"]

        # Apply region override if applicable
        if cca2 in REGION_MAP:
            region = REGION_MAP[cca2]

        return lat, lng, cca2, region

    # 2. Fallback to OurAirports
    oa_locations = load_ourairports_locations()
    fallback = oa_locations.get(lookup_code)

    if fallback:
        lat = fallback["lat"]
        lng = fallback["lng"]
        cca2 = fallback["cca2"]
        # For fallback data, we only have region if we map it from cca2
        region = REGION_MAP.get(cca2)
        return lat, lng, cca2, region

    print(f"Warning: Could not find coordinates for '{iata_code}'.")
    return None, None, None, None


def generate_full_data(en_file, zh_file, output_file):
    """Reads input files, enriches data, and writes the output file."""
    if not os.path.exists(en_file) or not os.path.exists(zh_file):
        print(f"Error: Input files not found: {en_file}, {zh_file}")
        return

    try:
        print(f"Reading input files: {en_file}, {zh_file}")
        with open(en_file, "r", encoding="utf-8") as f:
            data_en = json.load(f)

        with open(zh_file, "r", encoding="utf-8") as f:
            data_zh = json.load(f)
    except Exception as e:
        print(f"Error reading files: {e}")
        return

    full_data = {}
    sorted_slugs = sorted(data_en.keys())

    print("Processing and enriching data...")
    for slug in sorted_slugs:
        place_en = data_en[slug]
        # Fallback to English name if no translation exists
        place_zh = data_zh.get(slug, place_en)

        lat, lng, cca2, region = get_location_details(slug)

        full_data[slug] = {
            "place": place_en,
            "place_zh": place_zh,
            "lat": lat,
            "lng": lng,
            "cca2": cca2,
            "region": region,
        }

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        print(f"Successfully generated {output_file} with {len(full_data)} entries.")
    except Exception as e:
        print(f"Failed to write output file: {e}")


if __name__ == "__main__":
    print("Starting Geocoding for Combined Full Data File")
    generate_full_data(
        "cloudflare-iata.json", "cloudflare-iata-zh.json", "cloudflare-iata-full.json"
    )
