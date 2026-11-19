#!/usr/bin/env python3
"""Build data/movies.json for the site from a raw Regal pull plus Rotten Tomatoes lookups.

Usage:
  python3 -I build.py queries RAW.json            -> prints RT search queries still missing from data/rt.json (JSON list)
  python3 -I build.py build RAW.json [RT_NEW.json] -> merges RT_NEW into data/rt.json and writes data/movies.json

RAW.json comes from scripts/scrape_regal.js (run in a browser tab on regmovies.com).
RT_NEW.json comes from scripts/scrape_rt.js (run in a browser tab on rottentomatoes.com).
"""
import json, re, sys, os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("America/Los_Angeles")
RT_CACHE = os.path.join(HERE, "data", "rt.json")
OUT = os.path.join(HERE, "data", "movies.json")
THEATRE = {"code": "0758", "name": "Regal Old Mill", "address": "680 SW Powerhouse Drive, Bend, OR 97702",
           "url": "https://www.regmovies.com/theatres/regal-old-mill-0758"}

# Live events and stage broadcasts: no Rotten Tomatoes page worth looking up.
NO_RT = re.compile(r"^(Met Op|Royal Ballet|BTS |Prince 3121|IMAX: George|George Michael|Andre Rieu|Festive Fun|Monday Mystery|Doctor Who|National Theatre|Bolshoi|Fathom)", re.I)
EVENT = re.compile(r"^(Met Op|Royal Ballet|BTS |Prince 3121|IMAX: George|George Michael|Andre Rieu|Monday Mystery|Doctor Who|National Theatre|Bolshoi|Festive Fun)|Live$|Concert|Fan Event|Insider Screening|Early Access", re.I)
CLASSIC = re.compile(r"^(CUT26|Fangoria|Vice Films)|Anniversary|\(Reissue\)|\b4K$|\(\d{4}\)\s*$", re.I)
# Original release years for re-releases whose Regal title carries no year.
RT_OVERRIDE = {
    "The Host 4K": ("The Host", 2006), "A Beautiful Mind 25th Anniversary": ("A Beautiful Mind", 2001),
    "Vice Films: Miami Vice - Director's Cut": ("Miami Vice", 2006), "The Departed - 20th Anniversary": ("The Departed", 2006),
    "Romeo + Juliet 30th Anniversary": ("Romeo + Juliet", 1996), "The Maltese Falcon 85th Anniversary": ("The Maltese Falcon", 1941),
    "The Holiday 20th Anniversary": ("The Holiday", 2006), "Moulin Rouge! 25th Anniversary": ("Moulin Rouge!", 2001),
    "It's a Wonderful Life 80th Anniversary": ("It's a Wonderful Life", 1946),
    "Fangoria: Silent Night Deadly Night (1984)": ("Silent Night, Deadly Night", 1984),
    "The Odyssey (Reissue)": ("The Odyssey", 2026),
}
# Variant suffixes folded into the base movie (shown as a tag on the showtime).
VARIANTS = [(re.compile(r"\s*\(Open Cap/Eng Sub\)\s*$", re.I), "Open caption"), (re.compile(r"\s*\(Sensory\)\s*$", re.I), "Sensory friendly")]
FLAGS = {"3D": "3D", "IMAX": "IMAX", "ScreenX": "ScreenX", "ScreenX 3D": "ScreenX 3D", "InfinityVi": "InfinityVision", "OC": "Open caption",
         "Sub-Titled": "Subtitled", "Japanese": "Japanese", "Korean": "Korean", "Spanish": "Spanish", "Sensory": "Sensory friendly", "WatchParty": "Watch party"}


def slugify(t):
    t = t.lower().replace("&", "")
    t = re.sub(r"[^a-z0-9\s-]", "", t).replace("-", "")
    return re.sub(r"\s+", "-", t.strip())


def rt_key(m):
    title = m["Title"]
    if NO_RT.search(title):
        return None
    for rx, _ in VARIANTS:
        title = rx.sub("", title)
    if title in RT_OVERRIDE:
        t, y = RT_OVERRIDE[title]
        return f"{t}|{y}"
    year = None
    mm = re.search(r"\((\d{4})\)\s*$", title)
    if mm:
        year = int(mm.group(1)); title = title[:mm.start()].strip()
    title = re.sub(r"^(CUT26|Vice Films|Fangoria)\s*:\s*", "", title)
    title = re.sub(r"\s+(4K|\d+(st|nd|rd|th) Anniversary.*|Early Access|Insider Screenings|RealD 3D Fan Event|- Director's Cut)$", "", title, flags=re.I)
    if title == "Sunrise on the Reaping":
        title = "The Hunger Games: Sunrise on the Reaping"
    year = year or int((m.get("OpeningDate") or "2026")[:4])
    return f"{title.strip()}|{year}"


def load(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def queries(raw):
    cache = load(RT_CACHE, {})
    now = datetime.now(timezone.utc)
    out = set()
    for m in raw["movies"]:
        k = rt_key(m)
        if not k:
            continue
        c = cache.get(k)
        # Re-check scores for recent releases (they move in the first weeks) and anything not yet found.
        recent = int(k.rsplit("|", 1)[1]) >= now.year - 1
        stale = not c or not c.get("score") or (recent and c.get("checked", "") < (now - timedelta(days=6)).strftime("%Y-%m-%d"))
        if stale:
            out.add(k)
    return sorted(out)


def build(raw, rt_new):
    cache = load(RT_CACHE, {})
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    for k, v in (rt_new or {}).items():
        if v and v[0] not in ("NOMATCH", "ERR"):
            cache[k] = {"title": v[0], "year": v[1], "score": v[2] or "", "url": v[3], "checked": today}
        elif k not in cache:
            cache[k] = {"title": "", "year": None, "score": "", "url": "", "checked": today}
    os.makedirs(os.path.dirname(RT_CACHE), exist_ok=True)
    with open(RT_CACHE, "w") as f:
        json.dump(dict(sorted(cache.items())), f, indent=0)

    by_code = {m["MasterMovieCode"]: m for m in raw["movies"]}
    slugs = raw.get("slugs", {})
    # Group variants under a base movie.
    base_of, variant_of = {}, {}
    title_to_code = {m["Title"]: c for c, m in by_code.items()}
    for c, m in by_code.items():
        base_of[c], variant_of[c] = c, ""
        for rx, label in VARIANTS:
            if rx.search(m["Title"]):
                bt = rx.sub("", m["Title"])
                if bt in title_to_code:
                    base_of[c], variant_of[c] = title_to_code[bt], label

    now_local = datetime.now(TZ).replace(tzinfo=None)
    movies, idx, shows = [], {}, []
    slug_list, slug_idx = [], {}
    for code, local, perf, aud, attrs in sorted(raw["shows"], key=lambda s: s[1]):
        dt = datetime.fromisoformat(local)
        if dt < now_local - timedelta(hours=1):
            continue
        b = base_of.get(code, code)
        if b not in idx:
            m = by_code[b]
            media = m.get("Media") or []
            pick = lambda st: next((x.get("SecureUrl") for x in media if x.get("SubType") == st and x.get("SecureUrl")), "")
            k = rt_key(m)
            rt = cache.get(k, {}) if k else {}
            trailer = m.get("TrailerUrl") or pick("Trailer_Youtube") or ""
            title = m["Title"]
            kind = "event" if EVENT.search(title) else ("classic" if CLASSIC.search(title) else "film")
            idx[b] = len(movies)
            movies.append({
                "id": b, "title": title, "rating": m.get("Rating") or "", "runtime": m.get("Duration") or 0,
                "genre": " / ".join(x for x in [m.get("GenrePrimary"), m.get("GenreSecondary")] if x),
                "opens": (m.get("OpeningDate") or "")[:10], "desc": re.sub(r"\s+", " ", m.get("Description") or "").strip(),
                "directors": ", ".join((m.get("Directors") or [])[:3]), "cast": ", ".join((m.get("Actors") or [])[:5]),
                "poster": pick("TV_SmallPosterImage") or pick("Mobile_MovieThumbnail"), "wide": pick("Mobile_MovieFeed"),
                "trailer": trailer, "rt": rt.get("score", ""), "rtUrl": rt.get("url", ""), "kind": kind,
                "regal": f"https://www.regmovies.com/movies/{slugs.get(b) or slugify(title) + '-' + b.lower()}?site={THEATRE['code']}",
            })
        utc = dt.replace(tzinfo=TZ).astimezone(timezone.utc)
        tags = [FLAGS[a] for a in attrs.split("|") if a in FLAGS]
        if variant_of.get(code) and variant_of[code] not in tags:
            tags.append(variant_of[code])
        slug = slugs.get(code) or slugify(by_code[code]["Title"]) + "-" + code.lower()
        if slug not in slug_idx:
            slug_idx[slug] = len(slug_list); slug_list.append(slug)
        shows.append([idx[b], local[:16], int(utc.timestamp()), aud, " · ".join(tags), slug_idx[slug], perf])

    # Per-movie first/last date and day count.
    for i, m in enumerate(movies):
        days = sorted({s[1][:10] for s in shows if s[0] == i})
        m["first"], m["last"], m["days"] = days[0], days[-1], len(days)
        m["shows"] = sum(1 for s in shows if s[0] == i)

    out = {"theatre": THEATRE, "updated": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "fetched": raw.get("fetched"),
           "movies": movies, "slugs": slug_list,
           "showFields": ["movie", "local", "utc", "auditorium", "tags", "slug", "performanceId"], "shows": shows}
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(json.dumps({"movies": len(movies), "shows": len(shows), "range": [shows[0][1], shows[-1][1]] if shows else None,
                      "withRT": sum(1 for m in movies if m["rt"]), "noTrailer": sum(1 for m in movies if not m["trailer"])}))


if __name__ == "__main__":
    mode, raw_path = sys.argv[1], sys.argv[2]
    raw = load(raw_path, None)
    if not raw or not raw.get("shows"):
        sys.exit("raw file has no shows; refusing to overwrite data")
    if mode == "queries":
        print(json.dumps(queries(raw)))
    else:
        build(raw, load(sys.argv[3], {}) if len(sys.argv) > 3 else {})
