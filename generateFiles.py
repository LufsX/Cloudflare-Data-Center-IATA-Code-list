import json
import os
from pathlib import Path

import requests

DIST = Path("dist")
JSON_FILES = [
    "cloudflare-iata.json",
    "cloudflare-iata-zh.json",
    "cloudflare-iata-full.json",
    "en2zh.json",
]

HEADERS = """/en/*
  Access-Control-Allow-Origin: *
  Access-Control-Expose-Headers: *
  Cache-Control: public, max-age=86400
  Content-Type: text/plain; charset=UTF-8
/zh/*
  Access-Control-Allow-Origin: *
  Access-Control-Expose-Headers: *
  Cache-Control: public, max-age=86400
  Content-Type: text/plain; charset=UTF-8
/full/*
  Access-Control-Allow-Origin: *
  Access-Control-Expose-Headers: *
  Cache-Control: public, max-age=86400
  Content-Type: application/json; charset=UTF-8
"""

PAGE = """<!DOCTYPE html><html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloudflare Data Center IATA Code List</title>
<link rel="icon" href="https://cdn.isteed.cc/favicon_opt.png">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css" integrity="sha512-BrOPA520KmDMqieeM7XFe6a3u3Sb3F1JBaQnrIAmWg3EYrciJ+Qqe6ZcKCdfPv26rGcgTrJnZ/IdQEct8h3Zhw==" crossorigin="anonymous" referrerpolicy="no-referrer" />
<style>
.markdown-body {{box-sizing:border-box;min-width:200px;max-width:980px;margin:0 auto;padding:45px;}}@media (max-width:767px) {{.markdown-body {{padding:15px;}}}}
</style>
</head>
<body class="markdown-body">{body}</body>
</html>"""


def generate_files(json_path, output_dir):
    print(f"Generating {output_dir} from {json_path}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for code, value in data.items():
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        (output_dir / code).write_text(value, encoding="utf-8")
    print(f"Generated {len(data)} files in {output_dir}.")


def convert_readme_to_html(readme_path, output_path):
    print("Converting README.md to HTML...")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {github_token}"

    with open(readme_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    response = requests.post(
        "https://api.github.com/markdown",
        headers=headers,
        json={"text": md_content},
        timeout=30,
    )
    response.raise_for_status()
    output_path.write_text(PAGE.format(body=response.text), encoding="utf-8")
    print(f"Wrote {output_path}.")


def main():
    generate_files("cloudflare-iata.json", DIST / "en")
    generate_files("cloudflare-iata-zh.json", DIST / "zh")
    generate_files("cloudflare-iata-full.json", DIST / "full")

    print("Writing headers file...")
    DIST.mkdir(exist_ok=True)
    (DIST / "_headers").write_text(HEADERS, encoding="utf-8")
    convert_readme_to_html("README.md", DIST / "index.html")

    for filename in JSON_FILES:
        print(f"Copying {filename}...")
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(DIST / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print("Generated dist files.")


if __name__ == "__main__":
    main()
