import json
import re
from pathlib import Path

import requests

STATUS_URL = "https://www.cloudflarestatus.com/api/v2/components.json"
EXCLUDED_GROUP_ID = "1km35smx8p41"
OUTPUT_FILE = Path("cloudflare-iata.json")


def main():
    # 从 Cloudflare 节点状态中获取
    print("Fetching Cloudflare status components...")
    response = requests.get(STATUS_URL, timeout=30)
    response.raise_for_status()
    components = response.json().get("components", [])
    print(f"Loaded {len(components)} components.")

    exclude_ids = set()
    for component in components:
        # 排除掉 Cloudflare Sites and Services 中的内容
        if component.get("id") == EXCLUDED_GROUP_ID:
            exclude_ids = set(component.get("components", []))
            break

    # 尝试读取现有的数据文件
    existing_data = {}
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("r", encoding="utf-8") as f:
            existing_data = json.load(f)
        print(f"Current data, containing {len(existing_data)} nodes")

    # 获取新数据
    new_data = {}
    for component in components:
        name = component.get("name", "")
        if component.get("id") in exclude_ids or " - " not in name:
            continue

        location, code = name.rsplit(" - ", 1)
        code = code.strip("() ")
        new_data[code] = re.sub(r",.*,", ",", location.strip())

    # 特殊处理
    new_data.update({"JIB": "Djibouti City", "SIN": "Singapore", "LOCAL": "LOCAL"})
    print(f"Parsed {len(new_data)} data center nodes.")

    # 合并新旧数据（新数据优先）
    result = existing_data | new_data

    new_entries = sorted(new_data.keys() - existing_data.keys())
    updated_entries = sorted(
        k for k in new_data.keys() & existing_data.keys() if new_data[k] != existing_data[k]
    )
    print(f"Added {len(new_entries)} nodes: {', '.join(new_entries) or 'none'}")
    print(f"Updated {len(updated_entries)} nodes: {', '.join(updated_entries) or 'none'}")

    print(f"Writing {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Data has been saved, a total of {len(result)} nodes")


if __name__ == "__main__":
    main()
