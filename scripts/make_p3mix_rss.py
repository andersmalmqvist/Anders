#!/usr/bin/env python3
"""Bygger ett RSS-flöde för Sveriges Radio P3 Mix (programid 5047).

Ljudet streamas direkt från SR (AAC/m4a) - inga kopior lagras lokalt.
Användning:  python make_p3mix_rss.py [utfil]
Standardutfil: p3mix.xml i repots rotmapp.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

PROGRAM_ID = 5047
API = (
    "https://api.sr.se/api/v2/episodes/index"
    f"?format=json&programid={PROGRAM_ID}&size=100&page={{page}}"
)
UA = "p3mix-feed/1.0 (+github pages)"
OUT_DEFAULT = Path(__file__).resolve().parents[1] / "p3mix.xml"
CHANNEL_TITLE = "P3 Mix"
CHANNEL_LINK = "https://www.sverigesradio.se/p3mix"
CHANNEL_DESC = "P3 Mix som poddflöde - avsnitten streamas direkt från Sveriges Radio."
PROGRAM_API = "https://api.sr.se/api/v2/programs/5047?format=json"
PROGRAM_IMAGE_FALLBACK = (
    "https://static-cdn.sr.se/images/5047/45d7b1f7-1af0-4a35-b73f-dc54649cf86d.jpg"
)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def head_length(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def parse_sr_date(value: str) -> datetime | None:
    """SR levererar '/Date(1792864980000)/' (millisekunder, UTC)."""
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit())
    if not digits:
        return None
    return datetime.fromtimestamp(int(digits) / 1000, tz=timezone.utc)


def collect_episodes() -> list[dict]:
    episodes: list[dict] = []
    page = 1
    while True:
        data = fetch_json(API.format(page=page))
        batch = data.get("episodes") or []
        episodes.extend(batch)
        total_pages = int((data.get("pagination") or {}).get("totalpages") or 1)
        if not batch or page >= total_pages:
            break
        page += 1
    return episodes


def program_image() -> str:
    """Programbild (full upplösning) från SR:s program-API, med fallback."""
    try:
        data = fetch_json(PROGRAM_API)
        url = ((data.get("program") or {}).get("programimagetemplate") or "").strip()
        if url:
            return url
    except Exception:
        pass
    return PROGRAM_IMAGE_FALLBACK


def episode_date(ep: dict) -> datetime | None:
    files = (ep.get("broadcast") or {}).get("broadcastfiles") or [{}]
    return parse_sr_date(ep.get("publishdateutc") or (files[0] or {}).get("publishdateutc") or "")


def build(episodes: list[dict]) -> str:
    # lastBuildDate sätts till nyaste avsnittets tid, så filen är stabil
    # och bara ändras när ett nytt avsnitt faktiskt dykt upp.
    dates = [d for d in (episode_date(ep) for ep in episodes) if d]
    build_date = max(dates) if dates else datetime.now(timezone.utc)
    image_url = program_image()

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"'
        ' xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        "  <channel>",
        f"    <title>{escape(CHANNEL_TITLE)}</title>",
        f"    <link>{escape(CHANNEL_LINK)}</link>",
        f"    <description>{escape(CHANNEL_DESC)}</description>",
        "    <language>sv</language>",
        "    <image>",
        f"      <url>{escape(image_url)}</url>",
        f"      <title>{escape(CHANNEL_TITLE)}</title>",
        f"      <link>{escape(CHANNEL_LINK)}</link>",
        "    </image>",
        f'    <itunes:image href="{escape(image_url)}"/>',
        "    <itunes:author>Sveriges Radio</itunes:author>",
        "    <itunes:explicit>no</itunes:explicit>",
        "    <itunes:category text=\"Music\"/>",
        f"    <lastBuildDate>{format_datetime(build_date)}</lastBuildDate>",
    ]

    for ep in episodes:
        ep_id = ep.get("id")
        title = (ep.get("title") or "").strip()
        desc = (ep.get("description") or "").strip()
        link = (ep.get("url") or "").strip()
        files = (ep.get("broadcast") or {}).get("broadcastfiles") or []
        if not files:
            continue
        audio = files[0]
        audio_url = (audio.get("url") or "").strip()
        if not audio_url:
            continue
        duration = int(audio.get("duration") or 0)
        pub = parse_sr_date(ep.get("publishdateutc") or audio.get("publishdateutc") or "")
        length = head_length(audio_url)
        image = (ep.get("imageurl") or "").strip()

        lines.append("    <item>")
        lines.append(f"      <title>{escape(title)}</title>")
        if desc:
            lines.append(f"      <description>{escape(desc)}</description>")
        if link:
            lines.append(f"      <link>{escape(link)}</link>")
        lines.append(f'      <guid isPermaLink="false">p3mix-{escape(str(ep_id))}</guid>')
        if pub:
            lines.append(f"      <pubDate>{format_datetime(pub)}</pubDate>")
        lines.append(
            f'      <enclosure url="{escape(audio_url)}" length="{length}" type="audio/mp4"/>'
        )
        if duration:
            lines.append(f"      <itunes:duration>{duration}</itunes:duration>")
        if image:
            lines.append(f'      <itunes:image href="{escape(image)}"/>')
        lines.append("    </item>")

    lines += ["  </channel>", "</rss>", ""]
    return "\n".join(lines)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    episodes = collect_episodes()
    xml = build(episodes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8", newline="\n")
    items = xml.count("<item>")
    print(f"OK {out} - {items} avsnitt, {len(xml.encode('utf-8'))} byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
