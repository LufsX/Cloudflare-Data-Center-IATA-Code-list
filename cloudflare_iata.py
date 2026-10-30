import argparse
import csv
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

__version__ = "2.1.0"

STATUS_URL = "https://www.cloudflarestatus.com/api/v2/components.json"
CLOUDFLARE_LOCATIONS_URL = "https://speed.cloudflare.com/locations"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
GITHUB_MARKDOWN_URL = "https://api.github.com/markdown"
EXCLUDED_GROUP_ID = "1km35smx8p41"

DATA_FILENAMES = (
    "cloudflare-iata.json",
    "cloudflare-iata-zh.json",
    "cloudflare-iata-full.json",
    "en2zh.json",
)
SPECIAL_NODES = {"JIB": "Djibouti City", "SIN": "Singapore", "LOCAL": "LOCAL"}
IATA_ALIASES = {"JXG": "JNH", "KIV": "RMO"}
CONTINENT_REGION_MAP = {
    "AF": "Africa",
    "AN": "Antarctica",
    "AS": "Asia Pacific",
    "EU": "Europe",
    "NA": "North America",
    "OC": "Oceania",
    "SA": "South America",
}
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
EMPTY_LOCATION = {"lat": None, "lng": None, "cca2": None, "region": None}
CODE_PATTERN = re.compile(r"^[A-Z0-9]{3,5}$")
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
FULL_FIELDS = ("place", "place_zh", "lat", "lng", "cca2", "region")

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


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def from_root(cls, root: str | Path = ".") -> "ProjectPaths":
        return cls(Path(root).resolve())

    @property
    def english(self) -> Path:
        return self.root / DATA_FILENAMES[0]

    @property
    def chinese(self) -> Path:
        return self.root / DATA_FILENAMES[1]

    @property
    def full(self) -> Path:
        return self.root / DATA_FILENAMES[2]

    @property
    def translations(self) -> Path:
        return self.root / DATA_FILENAMES[3]

    @property
    def readme(self) -> Path:
        return self.root / "README.md"

    @property
    def dist(self) -> Path:
        return self.root / "dist"


class DataValidationError(ValueError):
    pass


class TranslationError(DataValidationError):
    pass


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_pretty_json(path: Path, data: Any, *, sort_keys: bool = False) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    atomic_write_text(path, content)


def write_compact_json(path: Path, data: Any) -> None:
    content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    atomic_write_text(path, content)


def create_session(retries: int = 3) -> Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = Session()
    session.headers["User-Agent"] = "cloudflare-iata/2.0"
    session.mount("https://", adapter)
    return session


def validate_code(code: Any) -> str:
    if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
        raise DataValidationError(f"Invalid data center code: {code!r}")
    return code


def _validate_sorted_mapping(name: str, data: Any) -> Mapping[str, Any]:
    if not isinstance(data, dict):
        raise DataValidationError(f"{name} must be a JSON object")
    if list(data) != sorted(data):
        raise DataValidationError(f"{name} keys must be sorted")
    for code in data:
        validate_code(code)
    return data


def validate_basic_data(name: str, data: Any) -> Mapping[str, str]:
    mapping = _validate_sorted_mapping(name, data)
    for code, value in mapping.items():
        if not isinstance(value, str):
            raise DataValidationError(f"{name}[{code!r}] must be a string")
    return mapping


def validate_full_data(data: Any) -> Mapping[str, Mapping[str, Any]]:
    mapping = _validate_sorted_mapping("full data", data)
    for code, value in mapping.items():
        if not isinstance(value, dict) or tuple(value) != FULL_FIELDS:
            raise DataValidationError(
                f"full data[{code!r}] fields must be {FULL_FIELDS!r}"
            )
        if not isinstance(value["place"], str) or not isinstance(
            value["place_zh"], str
        ):
            raise DataValidationError(f"full data[{code!r}] places must be strings")
        for field in ("lat", "lng"):
            coordinate = value[field]
            if coordinate is not None and (
                isinstance(coordinate, bool) or not isinstance(coordinate, Real)
            ):
                raise DataValidationError(
                    f"full data[{code!r}][{field!r}] must be a number or null"
                )
        for field in ("cca2", "region"):
            if value[field] is not None and not isinstance(value[field], str):
                raise DataValidationError(
                    f"full data[{code!r}][{field!r}] must be a string or null"
                )
        has_location = any(value[field] is not None for field in ("lat", "lng", "cca2"))
        if has_location and value["region"] is None:
            raise DataValidationError(
                f"full data[{code!r}] has location data but no region"
            )
    return mapping


def validate_translation_dictionary(data: Any) -> Mapping[str, str]:
    if not isinstance(data, dict):
        raise DataValidationError("translation dictionary must be a JSON object")
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise DataValidationError("translation dictionary entries must be strings")
        if not key.strip() or key != normalize_place(key):
            raise DataValidationError(
                f"translation dictionary key {key!r} is not a normalized place name"
            )
        if not is_translation(key, value):
            raise DataValidationError(
                f"translation dictionary value for {key!r} is not a Chinese "
                f"translation: {value!r}"
            )
    return data


def validate_datasets(
    english: Any,
    chinese: Any,
    full: Any,
    translations: Any,
) -> dict[str, int]:
    english = validate_basic_data("English data", english)
    chinese = validate_basic_data("Chinese data", chinese)
    full = validate_full_data(full)
    translations = validate_translation_dictionary(translations)
    if english.keys() != chinese.keys() or english.keys() != full.keys():
        raise DataValidationError("English, Chinese, and full data keys must match")
    for code, place in english.items():
        if full[code]["place"] != place or full[code]["place_zh"] != chinese[code]:
            raise DataValidationError(f"full data[{code!r}] does not match basic data")
        if not is_translation(place, chinese[code]):
            raise DataValidationError(
                f"Chinese data[{code!r}] is not translated: {chinese[code]!r}"
            )
    untranslated = sorted(
        {place for place in english.values() if place not in translations}
    )
    if untranslated:
        raise DataValidationError(
            "translation dictionary is missing entries for: "
            + ", ".join(repr(place) for place in untranslated)
        )
    return {
        "english": len(english),
        "chinese": len(chinese),
        "full": len(full),
        "translations": len(translations),
        "unused_translations": len(set(translations) - set(english.values())),
    }


def validate_project(paths: ProjectPaths) -> dict[str, int]:
    return validate_datasets(
        read_json(paths.english),
        read_json(paths.chinese),
        read_json(paths.full),
        read_json(paths.translations),
    )


def place_city(place: str) -> str:
    """Fold a place name down to its city part for rename detection."""
    city = place.split(",")[0]
    folded = unicodedata.normalize("NFKD", city)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", folded.casefold()).split())


def normalize_place(value: str) -> str:
    """Collapse whitespace, drop a middle region segment, and tidy commas."""
    cleaned = " ".join(value.split())
    cleaned = re.sub(r",[^,]*,", ",", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*", ", ", cleaned)
    return " ".join(cleaned.split())


def parse_components(
    components: Iterable[Mapping[str, Any]],
    excluded_group_id: str = EXCLUDED_GROUP_ID,
) -> dict[str, str]:
    components = list(components)
    excluded_ids = next(
        (
            set(component.get("components", []))
            for component in components
            if component.get("id") == excluded_group_id
        ),
        set(),
    )
    result: dict[str, str] = {}
    for component in components:
        name = component.get("name")
        if (
            component.get("id") in excluded_ids
            or not isinstance(name, str)
            or " - " not in name
        ):
            continue
        location, raw_code = name.rsplit(" - ", 1)
        code = raw_code.strip("() ").upper()
        if CODE_PATTERN.fullmatch(code):
            result[code] = normalize_place(location)
    result.update(SPECIAL_NODES)
    return dict(sorted(result.items()))


def fetch_components(session: Session) -> list[dict[str, Any]]:
    response = session.get(STATUS_URL, timeout=30)
    response.raise_for_status()
    components = response.json().get("components")
    if not isinstance(components, list):
        raise ValueError("Cloudflare status response has no components list")
    return components


def update_nodes(paths: ProjectPaths, session: Session) -> dict[str, str]:
    print("Fetching Cloudflare status components...")
    components = fetch_components(session)
    new_data = parse_components(components)
    existing_data = read_json(paths.english) if paths.english.exists() else {}
    validate_basic_data("existing English data", existing_data)
    result = dict(sorted((existing_data | new_data).items()))
    validate_basic_data("updated English data", result)
    added = sorted(new_data.keys() - existing_data.keys())
    updated = sorted(
        code
        for code in new_data.keys() & existing_data.keys()
        if new_data[code] != existing_data[code]
    )
    write_pretty_json(paths.english, result, sort_keys=True)
    print(f"Loaded {len(components)} components; parsed {len(new_data)} nodes.")
    print(f"Added {len(added)} nodes: {', '.join(added) or 'none'}")
    print(f"Updated {len(updated)} nodes: {', '.join(updated) or 'none'}")
    print(f"Wrote {len(result)} nodes to {paths.english}.")
    return result


def is_translation(source: str, candidate: Any) -> bool:
    """A usable translation is a non-empty Chinese string that differs from the source."""
    if not isinstance(candidate, str):
        return False
    text = candidate.strip()
    if not text or text == source.strip():
        return False
    return CJK_PATTERN.search(text) is not None


def _extract_google_chunks(payload: Any) -> str:
    chunks = payload[0] if isinstance(payload, list) and payload else None
    if not isinstance(chunks, list):
        raise ValueError("unexpected Google Translate payload")
    parts = [
        chunk[0]
        for chunk in chunks
        if isinstance(chunk, list) and chunk and isinstance(chunk[0], str)
    ]
    return "".join(parts)


def _extract_mymemory(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("unexpected MyMemory payload")
    data = payload.get("responseData")
    text = data.get("translatedText") if isinstance(data, dict) else None
    if not isinstance(text, str):
        raise ValueError(f"MyMemory error: {payload.get('responseDetails')!r}")
    return html.unescape(text)


@dataclass(frozen=True)
class TranslationProvider:
    name: str
    url: str
    params: Callable[[str], dict[str, str]]
    extract: Callable[[Any], str]

    def fetch(self, session: Session, text: str) -> str:
        response = session.get(self.url, params=self.params(text), timeout=20)
        response.raise_for_status()
        return self.extract(response.json())


def _google_params(text: str) -> dict[str, str]:
    return {
        "client": "dict-chrome-ex",
        "sl": "auto",
        "tl": "zh-CN",
        "dt": "t",
        "q": text,
    }


TRANSLATION_PROVIDERS = (
    TranslationProvider(
        "google-chrome-extension",
        "https://clients5.google.com/translate_a/single",
        _google_params,
        _extract_google_chunks,
    ),
    TranslationProvider(
        "google-gtx",
        TRANSLATE_URL,
        lambda text: {
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": text,
        },
        _extract_google_chunks,
    ),
    TranslationProvider(
        "mymemory",
        "https://api.mymemory.translated.net/get",
        lambda text: {"q": text, "langpair": "en|zh-CN"},
        _extract_mymemory,
    ),
)


def translate_text(
    session: Session,
    text: str,
    *,
    providers: Sequence[TranslationProvider] = TRANSLATION_PROVIDERS,
    attempts: int = 2,
    backoff: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    problems: list[str] = []
    for attempt in range(1, attempts + 1):
        for provider in providers:
            try:
                candidate = provider.fetch(session, text)
            except Exception as error:
                problems.append(f"{provider.name}: {error}")
                continue
            if is_translation(text, candidate):
                return candidate.strip()
            problems.append(f"{provider.name}: unusable result {candidate!r}")
        if attempt < attempts:
            sleep(backoff * attempt)
    raise TranslationError(f"cannot translate {text!r} ({'; '.join(problems)})")


def carry_over_translations(
    english: Mapping[str, str],
    previous: Mapping[str, Any],
    dictionary: MutableMapping[str, str],
) -> list[str]:
    """Reuse an existing translation when only the region part of a place changed.

    Cloudflare regularly rewrites names (accents dropped, country renamed), but
    the city stays the same, so the curated Chinese name is still valid.
    """
    carried: list[str] = []
    for code, place in english.items():
        if place in dictionary:
            continue
        entry = previous.get(code)
        if not isinstance(entry, Mapping):
            continue
        old_place = entry.get("place")
        old_zh = entry.get("place_zh")
        if not isinstance(old_place, str) or not isinstance(old_zh, str):
            continue
        if not is_translation(old_place, old_zh):
            continue
        if place_city(old_place) != place_city(place):
            continue
        dictionary[place] = old_zh.strip()
        carried.append(code)
    return carried


def build_translations(
    english: Mapping[str, str],
    dictionary: MutableMapping[str, str],
    translate: Callable[[str], str],
    *,
    delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, str], list[str]]:
    """Return Chinese data plus the places left untranslated.

    Only a verified Chinese translation enters the result or the dictionary;
    untranslated places are reported instead of leaking English into the
    Chinese dataset.
    """
    result: dict[str, str] = {}
    missing: list[str] = []
    for code, place in english.items():
        if place in dictionary:
            result[code] = dictionary[place]
            continue
        try:
            translated = translate(place)
        except Exception as error:
            print(f"Unable to translate {place}: {error}")
            missing.append(place)
            continue
        if not is_translation(place, translated):
            print(f"Untranslated output for {place}: {translated!r}")
            missing.append(place)
            continue
        dictionary[place] = translated.strip()
        result[code] = dictionary[place]
        sleep(delay)
    return dict(sorted(result.items())), sorted(missing)


def update_translations(paths: ProjectPaths, session: Session) -> dict[str, str]:
    english = read_json(paths.english)
    dictionary = read_json(paths.translations)
    validate_basic_data("English data", english)
    validate_translation_dictionary(dictionary)
    existing_places = set(dictionary)
    previous = read_json(paths.full) if paths.full.exists() else {}
    carried = carry_over_translations(english, previous, dictionary)
    if carried:
        print(
            "Reused existing translations for renamed places: "
            + ", ".join(carried)
        )
    print(f"Translating {len(english)} nodes...")
    result, missing = build_translations(
        english,
        dictionary,
        lambda text: translate_text(session, text),
    )
    added_places = [place for place in dictionary if place not in existing_places]
    if added_places:
        write_pretty_json(paths.translations, dictionary)
        print(
            f"Appended {len(added_places)} machine translations to "
            f"{paths.translations}."
        )
    if missing:
        raise TranslationError(
            f"{len(missing)} place(s) still need a Chinese translation: "
            + ", ".join(repr(place) for place in missing)
            + f". Add them to {paths.translations} by hand and run again; "
            "no untranslated entry was written to "
            f"{paths.chinese.name}."
        )
    validate_basic_data("Chinese data", result)
    write_pretty_json(paths.chinese, result, sort_keys=True)
    print(f"Wrote {len(result)} translations to {paths.chinese}.")
    return result


def parse_cloudflare_locations(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Cloudflare locations response must be a list")
    locations = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        iata = (item.get("iata") or "").strip().upper()
        if not iata or item.get("lat") is None or item.get("lon") is None:
            continue
        locations[iata] = {
            "lat": item["lat"],
            "lng": item["lon"],
            "cca2": (item.get("cca2") or "").strip().upper() or None,
            "region": item.get("region"),
        }
    return locations


def parse_ourairports_locations(content: str) -> dict[str, dict[str, Any]]:
    locations = {}
    for row in csv.DictReader(content.splitlines()):
        iata = (row.get("iata_code") or "").strip().upper()
        if not iata:
            continue
        try:
            continent = (row.get("continent") or "").strip().upper()
            locations[iata] = {
                "lat": float(row["latitude_deg"]),
                "lng": float(row["longitude_deg"]),
                "cca2": (row.get("iso_country") or "").strip().upper() or None,
                "region": CONTINENT_REGION_MAP.get(continent),
            }
        except (KeyError, TypeError, ValueError):
            continue
    for alias, target in IATA_ALIASES.items():
        if target in locations:
            locations[alias] = locations[target].copy()
    return locations


class LocationProvider:
    def __init__(self, session: Session):
        self.session = session
        self._cloudflare: dict[str, dict[str, Any]] | None = None
        self._ourairports: dict[str, dict[str, Any]] | None = None

    def _load_cloudflare(self) -> dict[str, dict[str, Any]]:
        if self._cloudflare is None:
            print("Fetching Cloudflare locations...")
            response = self.session.get(
                CLOUDFLARE_LOCATIONS_URL,
                headers={"Referer": "https://speed.cloudflare.com/"},
                timeout=15,
            )
            response.raise_for_status()
            self._cloudflare = parse_cloudflare_locations(response.json())
            print(f"Loaded {len(self._cloudflare)} Cloudflare locations.")
        return self._cloudflare

    def _load_ourairports(self) -> dict[str, dict[str, Any]]:
        if self._ourairports is None:
            print("Fetching OurAirports locations...")
            response = self.session.get(OURAIRPORTS_URL, timeout=30)
            response.raise_for_status()
            self._ourairports = parse_ourairports_locations(response.text)
            print(f"Loaded {len(self._ourairports)} OurAirports locations.")
        return self._ourairports

    def get(self, iata: str) -> dict[str, Any]:
        iata = iata.strip().upper()
        if iata == "LOCAL":
            return EMPTY_LOCATION.copy()
        location = self._load_cloudflare().get(iata)
        if location is None:
            location = self._load_ourairports().get(iata)
        if location is None:
            print(f"Warning: no coordinates for {iata}")
            return EMPTY_LOCATION.copy()
        result = {**EMPTY_LOCATION, **location}
        result["region"] = REGION_MAP.get(result["cca2"], result["region"])
        return result


def build_full_data(
    english: Mapping[str, str],
    chinese: Mapping[str, str],
    provider: LocationProvider,
) -> dict[str, dict[str, Any]]:
    return {
        code: {
            "place": place,
            "place_zh": chinese.get(code, place),
            **provider.get(code),
        }
        for code, place in sorted(english.items())
    }


def update_full_data(paths: ProjectPaths, session: Session) -> dict[str, dict[str, Any]]:
    english = read_json(paths.english)
    chinese = read_json(paths.chinese)
    validate_basic_data("English data", english)
    validate_basic_data("Chinese data", chinese)
    print(f"Resolving locations for {len(english)} nodes...")
    result = build_full_data(english, chinese, LocationProvider(session))
    validate_full_data(result)
    write_pretty_json(paths.full, result)
    print(f"Wrote {len(result)} entries to {paths.full}.")
    return result


def render_markdown(session: Session, markdown: str) -> str:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(
        GITHUB_MARKDOWN_URL,
        headers=headers,
        json={"text": markdown},
        timeout=30,
    )
    response.raise_for_status()
    return PAGE.format(body=response.text)


def generate_endpoint_files(data: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True)
    for code, value in data.items():
        validate_code(code)
        content = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, dict)
            else value
        )
        if not isinstance(content, str):
            raise ValueError(f"Endpoint value for {code} must be text or an object")
        atomic_write_text(output_dir / code, content)


def _replace_directory(staging: Path, target: Path) -> None:
    backup = Path(tempfile.mkdtemp(prefix=f".{target.name}-backup-", dir=target.parent))
    backup.rmdir()
    had_target = target.exists()
    try:
        if had_target:
            target.rename(backup)
        staging.rename(target)
    except Exception:
        if had_target and backup.exists() and not target.exists():
            backup.rename(target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def build_site(paths: ProjectPaths, session: Session) -> None:
    validate_project(paths)
    staging = Path(tempfile.mkdtemp(prefix=".dist-build-", dir=paths.root))
    try:
        english = read_json(paths.english)
        chinese = read_json(paths.chinese)
        full = read_json(paths.full)
        generate_endpoint_files(english, staging / "en")
        generate_endpoint_files(chinese, staging / "zh")
        generate_endpoint_files(full, staging / "full")
        atomic_write_text(staging / "_headers", HEADERS)
        markdown = paths.readme.read_text(encoding="utf-8")
        atomic_write_text(staging / "index.html", render_markdown(session, markdown))
        for filename in DATA_FILENAMES:
            write_compact_json(staging / filename, read_json(paths.root / filename))
        _replace_directory(staging, paths.dist)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"Built {paths.dist} with {len(english)} API endpoints per dataset.")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudflare-iata",
        description="Maintain and publish the Cloudflare data center dataset.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    update = commands.add_parser("update", help="update generated datasets")
    update.add_argument(
        "dataset",
        choices=("nodes", "translations", "full", "all"),
        help="dataset stage to update",
    )
    commands.add_parser("build", help="build the static API into dist/")
    commands.add_parser("validate", help="validate checked-in JSON datasets")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    paths = ProjectPaths.from_root(args.root)
    try:
        return run_command(args, paths)
    except DataValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def run_command(args: argparse.Namespace, paths: ProjectPaths) -> int:
    if args.command == "validate":
        counts = validate_project(paths)
        print(
            "Validated datasets: "
            + ", ".join(f"{name}={count}" for name, count in counts.items())
        )
        return 0
    session = create_session()
    if args.command == "build":
        build_site(paths, session)
        return 0
    if args.dataset in ("nodes", "all"):
        update_nodes(paths, session)
    if args.dataset in ("translations", "all"):
        update_translations(paths, session)
    if args.dataset in ("full", "all"):
        update_full_data(paths, session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
