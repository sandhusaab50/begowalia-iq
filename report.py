#!/usr/bin/env python3
"""Begowalia IQ: public-channel YouTube Data API dashboard and daily report.

No dependencies beyond Python's standard library. No uploading or modifying YouTube.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from statistics import median
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://www.googleapis.com/youtube/v3/"
CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCUUhi6u0FzDn2L7mizyog8g")
ARTIST = os.getenv("ARTIST_NAME", "Begowalia")
MAX_VIDEOS = 50


def api_get(endpoint: str, key: str, **params) -> dict:
    url = API_BASE + endpoint + "?" + urlencode({**params, "key": key})
    try:
        with urlopen(url, timeout=25) as response:
            result = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"YouTube API error (HTTP {exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach YouTube API: {exc.reason}") from exc
    return result


def duration_seconds(value: str) -> int:
    """Parse an ISO 8601 duration such as PT3M18S or P1DT2H."""
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value or "")
    if not match:
        return 0
    d, h, m, s = (int(x or 0) for x in match.groups())
    return d * 86400 + h * 3600 + m * 60 + s


def fetch_channel(key: str, channel_id: str) -> tuple[dict, list[dict]]:
    result = api_get("channels", key, part="snippet,statistics,contentDetails", id=channel_id)
    items = result.get("items", [])
    if not items:
        raise RuntimeError("Channel not found. Check YOUTUBE_CHANNEL_ID and API settings.")
    channel = items[0]
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads:
        raise RuntimeError("Could not locate channel uploads playlist.")
    ids = []
    next_page = None
    while len(ids) < MAX_VIDEOS:
        params = {"part": "contentDetails", "playlistId": uploads,
                  "maxResults": min(50, MAX_VIDEOS-len(ids))}
        if next_page:
            params["pageToken"] = next_page
        feed = api_get("playlistItems", key, **params)
        ids += [item.get("contentDetails", {}).get("videoId") for item in feed.get("items", [])]
        ids = [vid for vid in ids if vid]
        next_page = feed.get("nextPageToken")
        if not next_page:
            break
    videos = []
    for i in range(0, len(ids), 50):
        detail = api_get("videos", key, part="snippet,statistics,contentDetails", id=",".join(ids[i:i+50]))
        videos.extend(detail.get("items", []))
    # Keep order from uploads playlist, not arbitrary API response order.
    by_id = {v["id"]: v for v in videos}
    return channel, [by_id[i] for i in ids if i in by_id]


def sample_data() -> tuple[dict, list[dict]]:
    """Clearly fictional demo values, never presented as actual channel metrics."""
    channel = {"id": CHANNEL_ID, "snippet": {"title": "Begowalia Music (DEMO)"},
               "statistics": {"subscriberCount": "700", "viewCount": "28000", "videoCount": "12"}}
    demos = [
        ("sample01", "Saanh – Begowalia | Punjabi Music", 1670, 83, 12, 4, 192),
        ("sample02", "Lion Heart | Begowalia Official Video", 920, 47, 7, 12, 204),
        ("sample03", "Punjab Siyan – New Song", 580, 28, 3, 24, 178),
        ("sample04", "Example Short Clip", 240, 18, 2, 2, 25),
    ]
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    videos = []
    for vid, title, views, likes, comments, days, duration in demos:
        published = (now - timedelta(days=days)).isoformat()
        videos.append({"id": vid, "snippet": {"title": title, "description": "Demo example only",
                       "publishedAt": published, "tags": ["Punjabi", "Begowalia"],
                       "thumbnails": {}},
                       "statistics": {"viewCount": str(views), "likeCount": str(likes),
                                      "commentCount": str(comments)},
                       "contentDetails": {"duration": f"PT{duration//60}M{duration%60}S"}})
    return channel, videos


def number(x, fallback=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return fallback


def parse_date(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def studio_metrics(csv_path: str | None) -> dict:
    """Optional PRIVATE creator-maintained CSV, not needed for public daily GitHub run.
    Expected columns: video_id,impressions,ctr,avg_view_duration_seconds
    CTR is a percentage, e.g., 4.2 (not .042).
    """
    if not csv_path:
        return {}
    results = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("video_id"):
                results[row["video_id"].strip()] = row
    return results


def analyze(videos: list[dict], studio: dict | None = None) -> tuple[list[dict], dict]:
    studio = studio or {}
    now = datetime.now(timezone.utc)
    processed = []
    for v in videos:
        s = v.get("snippet", {})
        stats = v.get("statistics", {})
        title = s.get("title", "Untitled")
        published = parse_date(s.get("publishedAt", now.isoformat()))
        age_days = max((now - published).total_seconds() / 86400, 0.15)
        views = number(stats.get("viewCount"))
        likes = number(stats.get("likeCount"))
        comments = number(stats.get("commentCount"))
        vpd = views / max(age_days, 1)
        engagement = (likes+comments) / views * 100 if views else 0
        duration = duration_seconds(v.get("contentDetails", {}).get("duration", ""))
        tags = s.get("tags", [])
        metadata_flags = []
        if len(title) > 75:
            metadata_flags.append("Consider a shorter, clearer title")
        if len(title) < 18:
            metadata_flags.append("Title may need more context")
        if len(s.get("description", "")) < 80:
            metadata_flags.append("Add a useful video description")
        if not tags:
            metadata_flags.append("Add relevant tags for spelling and context")
        if ARTIST.lower() not in title.lower():
            metadata_flags.append(f"Make the artist name ({ARTIST}) clear")
        creator = studio.get(v["id"], {})
        ctr = creator.get("ctr")
        try:
            ctr_val = float(ctr) if ctr not in (None, "") else None
        except ValueError:
            ctr_val = None
        processed.append({"id": v["id"], "title": title, "views": views, "likes": likes,
                          "comments": comments, "published": published, "age_days": age_days,
                          "views_per_day": vpd, "engagement": engagement,
                          "duration": duration, "flags": metadata_flags, "tags": tags,
                          "description": s.get("description", ""),
                          "thumbnail": s.get("thumbnails", {}).get("medium", {}).get("url", ""),
                          "studio_ctr": ctr_val,
                          "studio_impressions": number(creator.get("impressions"), None),
                          "studio_avd": number(creator.get("avg_view_duration_seconds"), None)})
    # Comparing uploads of the same age band is more useful than all-time views.
    recent = [v["views_per_day"] for v in processed if 1 <= v["age_days"] <= 90]
    typical = median(recent) if recent else 0
    for row in processed:
        if not (1 <= row["age_days"] <= 90) or not typical:
            row["performance"] = "Not compared"
        elif row["views_per_day"] >= typical * 1.5:
            row["performance"] = "Above recent median"
        elif row["views_per_day"] < typical * .6:
            row["performance"] = "Below recent median"
        else:
            row["performance"] = "Near recent median"
        # An observational comparison, NOT a YouTube SEO score or prediction.
    return processed, {"recent_median_views_per_day": typical, "recent_count": len(recent)}


def title_ideas(title: str, artist: str) -> list[str]:
    base = re.split(r"\s*[|–—-]\s*", title, maxsplit=1)[0].strip()
    base = re.sub(r"\s*\([^)]*(official|audio|lyrics|video)[^)]*\)", "", base, flags=re.I).strip()
    if not base:
        base = "New Song"
    base = re.sub(rf"\b{re.escape(artist)}\b", "", base, flags=re.I).strip(" -–—|") or base
    ideas = [f"{base} | {artist} (Official Music Video)",
             f"{base} – {artist} | New Punjabi Song",
             f"{artist} – {base} (Official Audio)"]
    return list(dict.fromkeys(x[:100] for x in ideas))


def keyword_ideas(title: str, artist: str) -> list[str]:
    song = re.split(r"\s*[|–—-]\s*", title, maxsplit=1)[0].strip()
    if not song:
        song = "new Punjabi song"
    choices = [artist, f"{artist} music", f"{artist} new song", song,
               f"{song} {artist}", f"{song} Punjabi song", "Punjabi music", "Punjabi songs"]
    return list(dict.fromkeys(choices))


def format_duration(seconds: int) -> str:
    return f"{seconds//60}:{seconds%60:02d}" if seconds < 3600 else f"{seconds//3600}:{(seconds%3600)//60:02d}:{seconds%60:02d}"


def fmt(x: int | float) -> str:
    return f"{x:,.0f}"


def update_history(channel: dict, demo: bool) -> list[dict]:
    # Demo mode does not alter a channel's real history.
    histfile = ROOT / "data" / "history.json"
    history = json.loads(histfile.read_text()) if histfile.exists() else []
    if not demo:
        s = channel.get("statistics", {})
        row = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
               "subscribers": number(s.get("subscriberCount")),
               "views": number(s.get("viewCount"))}
        history = [h for h in history if h.get("date") != row["date"]] + [row]
        history = sorted(history, key=lambda x: x["date"])[-120:]
        histfile.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return history


def svg_growth(history: list[dict]) -> str:
    if len(history) < 2:
        return '<p class="muted">Growth history appears after at least two daily runs.</p>'
    values = [h["subscribers"] for h in history]
    low, high = min(values), max(values)
    spread = max(high-low, 1)
    coords = []
    for i, val in enumerate(values):
        x = 10 + 680*i/max(len(values)-1, 1)
        y = 135 - 115*(val-low)/spread
        coords.append(f"{x:.1f},{y:.1f}")
    return (f'<svg viewBox="0 0 700 155" role="img" aria-label="Subscriber count history" '
            f'preserveAspectRatio="none"><line x1="0" y1="140" x2="700" y2="140" stroke="#334155"/>'
            f'<polyline fill="none" stroke="#4ade80" stroke-width="3" points="{" ".join(coords)}"/>'
            f'<text x="8" y="12" fill="#aab6c9" font-size="13">{fmt(high)} subscribers</text>'
            f'<text x="8" y="151" fill="#aab6c9" font-size="12">{escape(history[0]["date"])} → {escape(history[-1]["date"])}</text></svg>')


def render_html(channel: dict, videos: list[dict], comparison: dict,
                history: list[dict], demo: bool) -> str:
    s = channel.get("statistics", {})
    channel_title = channel.get("snippet", {}).get("title", ARTIST)
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    warning = '<div class="alert">DEMO DATA ONLY — sample numbers; connect your YouTube API key for real metrics.</div>' if demo else ''
    cards = []
    for v in videos:
        flags = ''.join(f'<li>{escape(msg)}</li>' for msg in v["flags"])
        alternatives = ''.join(f'<li><button class="copy" data-copy="{escape(idea, quote=True)}" type="button">Copy</button> {escape(idea)}</li>'
                               for idea in title_ideas(v["title"], ARTIST))
        kw = ', '.join(keyword_ideas(v["title"], ARTIST))
        vid_link = f'https://www.youtube.com/watch?v={escape(v["id"], quote=True)}'
        thumb = (f'<img loading="lazy" src="{escape(v["thumbnail"], quote=True)}" alt="Video thumbnail">'
                 if v["thumbnail"] and not demo else '<div class="thumb-demo">BEGOWALIA<br> MUSIC</div>')
        label = v["performance"]
        style = "good" if label.startswith("Above") else "quiet" if label.startswith("Near") else "low" if label.startswith("Below") else "quiet"
        creator = ''
        if v["studio_ctr"] is not None:
            creator = f'<p>Studio CSV: CTR <b>{v["studio_ctr"]:.1f}%</b>'
            if v["studio_impressions"] is not None:
                creator += f' · {fmt(v["studio_impressions"])} impressions'
            if v["studio_avd"] is not None:
                creator += f' · Avg view duration {format_duration(v["studio_avd"])}'
            creator += '</p>'
        cards.append(f'''
        <article class="video" data-title="{escape(v["title"].lower(), quote=True)}" data-performance="{style}" data-comments="{v["comments"]}">
            <a class="thumbnail" href="{vid_link}" target="_blank" rel="noopener noreferrer">{thumb}</a>
            <div class="video-main">
                <h3><a href="{vid_link}" target="_blank" rel="noopener noreferrer">{escape(v["title"])}</a></h3>
                <p class="meta">{v["published"].strftime("%d %b %Y")} · {format_duration(v["duration"])} · <span class="chip {style}">{escape(label)}</span></p>
                <div class="stats"><div><b>{fmt(v["views"])}</b><small>Views</small></div><div><b>{v["views_per_day"]:.1f}</b><small>Avg views/day*</small></div><div><b>{v["engagement"]:.1f}%</b><small>Likes + comments / views</small></div></div>
                {creator}
                <details><summary>SEO checklist and title ideas</summary>
                    <div class="detail"><strong>Metadata checklist</strong><ul>{flags or '<li>No basic metadata flags detected</li>'}</ul>
                    <strong>Suggested titles (choose the appropriate video format)</strong><ul>{alternatives}</ul>
                    <strong>Keyword starting points (not search-volume research)</strong><p>{escape(kw)}</p></div>
                </details>
            </div>
        </article>''')
    count_below = sum(v["performance"].startswith("Below") for v in videos)
    insights = [
        ("Analyze lower-performing videos", f"{count_below} recent uploads have fewer average daily views than the recent median band. Check their titles, thumbnail clarity, and opening seconds.") if count_below else ("Review recent winners", "Compare your stronger recent uploads and make follow-up clips from their best hooks."),
        ("Test the first 10 seconds", "For music videos, lead with the strongest moment in teaser Shorts; inspect audience retention in YouTube Studio."),
        ("Use real CTR and retention", "Import private metrics using --studio-csv locally. Public YouTube API data does not include impressions, click-through rate or watch retention."),
    ]
    insights_html = ''.join(f'<div class="tip"><strong>{escape(h)}</strong><p>{escape(body)}</p></div>' for h, body in insights)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Begowalia IQ — YouTube Growth Dashboard</title>
<style>
:root{{color-scheme:dark;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:#e7edf7;background:#0c111b}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at top right,#192e39 0%,#0c111b 45%);min-height:100vh}}
a{{color:inherit;text-decoration:none}}a:hover{{color:#4ade80}}.wrap{{max-width:1200px;margin:auto;padding:24px}}
header{{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:26px}}.brand{{font-weight:900;font-size:26px;letter-spacing:-1px}}.brand em{{font-style:normal;color:#4ade80}}
.sub{{color:#9caec5;font-size:13px;margin-top:5px}}.navpill{{padding:9px 14px;border:1px solid #344358;border-radius:40px;color:#b5c5d8;font-size:13px}}
h1{{font-size:clamp(27px,4vw,43px);margin:13px 0 8px;letter-spacing:-1.1px}}.lead{{color:#a1b3c7;max-width:750px;line-height:1.55}}
.alert{{padding:13px 17px;color:#fbd38d;border:1px solid #a56a25;background:#4937193a;border-radius:10px;margin:22px 0}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:27px 0}}.metric,.panel{{border:1px solid #283647;background:#151e2b;border-radius:18px;padding:21px}}
.metric small{{color:#9eb0c5;display:block;font-size:13px}}.metric b{{font-size:clamp(26px,3.5vw,36px);display:block;margin-top:14px;letter-spacing:-1px}}
.row{{display:grid;grid-template-columns:1.6fr 1fr;gap:15px;margin-bottom:25px}}.panel h2{{font-size:17px;margin:0 0 18px}}.chart svg{{width:100%;height:155px}}
.tip{{margin-bottom:15px}}.tip p{{color:#a5b6ca;font-size:13px;line-height:1.5;margin:6px 0 0}}.section-head{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px}}.section-head h2{{margin:0;font-size:23px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap}}input,select{{background:#1b2938;color:#f0f4fb;border:1px solid #405167;padding:11px 13px;border-radius:10px;font-size:14px;max-width:100%}}
.video[hidden]{{display:none}}.video{{display:flex;gap:20px;border:1px solid #293847;border-radius:16px;padding:16px;margin-bottom:12px;background:#111c29}}.thumbnail{{flex:0 0 215px;max-width:215px;aspect-ratio:16/9;display:block;overflow:hidden;border-radius:10px;background:#1b3044}}.thumbnail img{{width:100%;height:100%;object-fit:cover}}.thumb-demo{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;letter-spacing:1px;color:#eaf9f0;text-align:center;background:linear-gradient(145deg,#174d45,#224d7e 52%,#192337)}}
.video-main{{flex:1;min-width:0}}h3{{margin:0 0 8px;font-size:18px;line-height:1.3}}.meta{{color:#a1b2c6;font-size:12px;margin:0 0 15px}}.chip{{display:inline-block;padding:4px 8px;border-radius:16px;background:#293447;color:#cbd7e5}}.chip.good{{background:#153f36;color:#76e5aa}}.chip.low{{background:#473523;color:#f6c283}}
.stats{{display:flex;gap:28px;flex-wrap:wrap;margin-bottom:15px}}.stats b{{font-size:19px;display:block}}.stats small{{display:block;color:#97a9c1;font-size:11px;margin-top:2px}}
summary{{cursor:pointer;color:#80dbae;font-weight:650;font-size:13px}}details{{border-top:1px solid #263648;padding-top:13px}}.detail{{color:#b6c5d7;font-size:13px;line-height:1.6}}.detail ul{{padding-left:20px}}.detail li{{margin:8px 0}}button.copy{{background:#233b38;border:1px solid #2b755f;border-radius:6px;color:#8ef0bf;padding:4px 7px;margin-right:8px;cursor:pointer}}
footer{{margin-top:28px;border-top:1px solid #29384c;padding:18px 0 40px;font-size:12px;color:#899cb4;line-height:1.7}}
@media(max-width:850px){{.grid{{grid-template-columns:repeat(2,1fr)}}.row{{grid-template-columns:1fr}}}}
@media(max-width:620px){{.wrap{{padding:15px}}.grid{{gap:8px}}.metric{{padding:15px}}.video{{flex-direction:column;gap:12px}}.thumbnail{{flex:auto;max-width:none;width:100%}}.stats{{gap:18px}}}}
</style></head><body><div class="wrap">
<header><div><div class="brand">BEGOWALIA <em>IQ</em></div><div class="sub">Private-built growth toolkit · based on public YouTube metrics</div></div><div class="navpill">Updated {escape(generated)}</div></header>
<main><h1>Make smarter music videos.</h1><p class="lead">A vidIQ-style dashboard for {escape(channel_title)}. Track your recent uploads, spot comparatively strong songs, and collect practical title and keyword ideas. No paid views, bots or engagement manipulation.</p>
{warning}
<div class="grid"><div class="metric"><small>Public subscribers†</small><b>{fmt(number(s.get("subscriberCount"))) if not s.get("hiddenSubscriberCount") else 'Hidden'}</b></div>
<div class="metric"><small>Lifetime channel views</small><b>{fmt(number(s.get("viewCount")))}</b></div>
<div class="metric"><small>Public video count</small><b>{fmt(number(s.get("videoCount")))}</b></div>
<div class="metric"><small>Videos analyzed</small><b>{len(videos)}</b></div></div>
<div class="row"><section class="panel chart"><h2>Subscriber history</h2>{svg_growth(history)}</section>
<section class="panel"><h2>Growth suggestions</h2>{insights_html}</section></div>
<div class="section-head"><h2>Video performance</h2><div class="controls"><input id="search" type="search" placeholder="Search videos" aria-label="Search videos"><select id="sort" aria-label="Sort videos"><option value="newest">Newest first</option><option value="views">Most views</option><option value="vpd">Views/day</option><option value="comments">Most comments</option></select></div></div>
<div id="videos">{''.join(cards) if cards else '<p>No public uploads were returned.</p>'}</div>
</main><footer>* Average views/day = lifetime views divided by time since publication. This is not YouTube's real-time views-per-hour or recommendation metric. Comparison uses uploads 1–90 days old. †Public subscriber counts may be rounded. Public metrics do not reveal impressions, true CTR, audience retention, watch time, traffic sources or recommendation decisions. Suggestions are rules-based starting points, not guaranteed rankings. {('All displayed metrics are FICTIONAL examples.' if demo else '')}</footer>
</div><script>
const list=document.getElementById('videos');const search=document.getElementById('search');const sort=document.getElementById('sort');
function update(){{const rows=[...list.querySelectorAll('.video')];const q=search.value.toLowerCase();rows.forEach(r=>r.hidden=!r.dataset.title.includes(q));
const key=sort.value; if(key==='newest') return rows.forEach((r,i)=>r.style.order=i);
const field=key==='vpd'?1:key==='views'?0:2;rows.sort((a,b)=>{{function val(el){{const s=el.querySelectorAll('.stats b');if(field===2)return Number((el.querySelector('a[href*="watch"]')&&el.dataset.comments)||0);return Number(s[field].innerText.replaceAll(',',''));}}return val(b)-val(a);}}).forEach((r,i)=>r.style.order=i);
}}list.style.display='flex';list.style.flexDirection='column';search.addEventListener('input',update);sort.addEventListener('change',update);
document.querySelectorAll('button.copy').forEach(b=>b.addEventListener('click',()=>{{navigator.clipboard.writeText(b.dataset.copy).then(()=>{{const original=b.innerText;b.innerText='Copied';setTimeout(()=>b.innerText=original,1000)}});}}));
</script></body></html>'''


def render_markdown(channel: dict, videos: list[dict], comparison: dict, demo: bool) -> str:
    s = channel.get("statistics", {})
    heading = "# BEGOWALIA IQ — DEMO ONLY\n\n**All stats below are fictional sample data.**\n" if demo else "# BEGOWALIA IQ — Daily YouTube Report\n"
    lines = [heading, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
             f"Channel: {channel.get('snippet', {}).get('title', ARTIST)}",
             f"Public subscribers: {fmt(number(s.get('subscriberCount')))} (may be rounded)",
             f"Channel views: {fmt(number(s.get('viewCount')))}", "",
             "## Recent videos", "", "| Video | Views | Avg views/day | Likes | Comments | Relative performance |", "|---|---:|---:|---:|---:|---|",]
    for v in videos:
        title = v['title'].replace('|', '\\|').replace('\n',' ')
        lines.append(f"| [{title}](https://www.youtube.com/watch?v={v['id']}) | {fmt(v['views'])} | {v['views_per_day']:.1f} | {v['likes']} | {v['comments']} | {v['performance']} |")
    lines.extend(["", "## Suggested next actions", "", 
                  "1. Review the 3 videos with the weakest recent views/day and compare thumbnails and intros against stronger videos.",
                  "2. Use the dashboard's title alternatives as human-reviewed starting points, never as a guarantee.",
                  "3. For actual thumbnail CTR, impressions, and watch duration, inspect YouTube Studio or export private metrics.",
                  "", "No automatic commenting, subscribing, or fake engagement is used."])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Create a clearly labeled fictional demo dashboard')
    parser.add_argument('--studio-csv', default=None, help='Optional privately exported analytics CSV (local only)')
    args = parser.parse_args()
    if args.demo:
        channel, raw_videos = sample_data()
    else:
        key = os.getenv('YOUTUBE_API_KEY', '').strip()
        if not key:
            raise SystemExit('YOUTUBE_API_KEY is missing. Create a secret or run --demo for a preview.')
        channel, raw_videos = fetch_channel(key, CHANNEL_ID)
    video_rows, summary = analyze(raw_videos, studio_metrics(args.studio_csv))
    history = update_history(channel, args.demo)
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'docs' / 'index.html').write_text(render_html(channel, video_rows, summary, history, args.demo), encoding='utf-8')
    (ROOT / 'reports' / 'latest.md').write_text(render_markdown(channel, video_rows, summary, args.demo), encoding='utf-8')
    print(f"Created docs/index.html and reports/latest.md ({len(video_rows)} videos, demo={args.demo})")


if __name__ == '__main__':
    main()
