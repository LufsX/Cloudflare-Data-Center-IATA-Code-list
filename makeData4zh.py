import json
import time

import requests

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def google_translate(text):
    response = requests.get(
        TRANSLATE_URL,
        params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()[0][0][0]


def main():
    # 加载数据
    print("加载基础数据...")
    with open("cloudflare-iata.json", "r", encoding="utf-8") as f:
        result = json.load(f)

    # 加载字典
    print("加载翻译字典...")
    with open("en2zh.json", "r", encoding="utf-8") as f:
        en2zh = json.load(f)

    # 处理翻译
    print(f"处理 {len(result)} 个节点翻译...")
    zh_result = {}
    for code, name in result.items():
        if name in en2zh:
            zh_result[code] = en2zh[name]
            continue

        print(f"原文 {name} 暂无翻译，尝试机器翻译...")
        try:
            translated = google_translate(name)
        except Exception as error:
            print(f"无法翻译 {name}: {error}")
            zh_result[code] = name
            continue

        print(f"谷歌翻译: {name} -> {translated}")
        zh_result[code] = translated or name
        time.sleep(0.5)

    # 保存结果
    print("保存中文数据...")
    with open("cloudflare-iata-zh.json", "w", encoding="utf-8") as f:
        json.dump(zh_result, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"已保存，共 {len(zh_result)} 个节点翻译")


if __name__ == "__main__":
    main()
