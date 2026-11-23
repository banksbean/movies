#!/usr/bin/env python3
"""Build data/movies.json for the site from theatre pulls plus Rotten Tomatoes lookups.

Theatres: Regal Old Mill (regal), Tin Pan Theater (tinpan), McMenamins Old St. Francis Theater (osf).

Usage:
  python3 -I build.py queries [--regal F] [--tinpan F] [--osf F]
      -> prints the RT search queries still missing from data/rt.json (JSON list)
  python3 -I build.py build [--regal F] [--tinpan F] [--osf F] [--rt RT_NEW.json]
      -> merges RT_NEW into data/rt.json and writes data/movies.json
  Old form still works: build.py queries RAW.json / build.py build RAW.json [RT_NEW.json] (RAW = Regal pull).

A theatre left out (or whose file is missing or empty) keeps its showtimes from the current data/movies.json,
so one failed pull never wipes that theatre off the site. Pulls come from:
  regal  : scripts/scrape_regal.js       (browser tab on regmovies.com)
  tinpan : scripts/scrape_tinpan.js      (browser tab on tinpantheater2025.eventive.org/schedule, one run per week)
  osf    : scripts/scrape_mcmenamins.js  (browser tab on the McMenamins Old St. Francis now-playing page)
  RT     : scripts/scrape_rt.js          (browser tab on rottentomatoes.com)
"""
import json, re, sys, os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("America/Los_Angeles")
RT_CACHE = os.path.join(HERE, "data", "rt.json")
OUT = os.path.join(HERE, "data", "movies.json")
THEATRES = [
    {"id": "regal", "name": "Regal Old Mill", "short": "Old Mill", "code": "0758",
     "address": "680 SW Powerhouse Drive, Bend, OR 97702", "url": "https://www.regmovies.com/theatres/regal-old-mill-0758"},
    {"id": "tinpan", "name": "Tin Pan Theater", "short": "Tin Pan",
     "address": "869 NW Tin Pan Alley, Bend, OR 97703", "url": "https://tinpantheater2025.eventive.org/schedule"},
    {"id": "osf", "name": "McMenamins Old St. Francis Theater", "short": "Old St. Francis",
     "address": "700 NW Bond Street, Bend, OR 97703", "url": "https://www.mcmenamins.com/old-st-francis-school/old-st-francis-theater/now-playing/"},
]
TH = {t["id"]: i for i, t in enumerate(THEATRES)}
THEATRE = THEATRES[0]

# Not movies at all: opera/ballet/theatre broadcasts, concerts, TV specials, private rentals. Dropped at every
# theatre (no showtimes, no RT lookup). Film anniversaries, mystery movies and fan screenings of real films stay.
NOT_MOVIE = re.compile(r"^(Met Op\b|Royal Ballet|Bolshoi|National Theatre|NT Live|Royal Opera|Opera:|Ballet:|BTS |Prince 3121|"
                       r"(IMAX: )?George Michael|Andr[eé] Rieu|Doctor Who|Cameron Winter at)|"
                       r"Private (Event|Party|Rental)|Rental at|Concert\b|\bin Concert|:\s*Live$|\bLive in (Cinemas|Concert)", re.I)

# Live events and stage broadcasts: no Rotten Tomatoes page worth looking up.
NO_RT = re.compile(r"^(Met Op|Royal Ballet|BTS |Prince 3121|IMAX: George|George Michael|Andre Rieu|Festive Fun|Monday Mystery|Doctor Who|National Theatre|Bolshoi|Fathom)|Mystery Movie", re.I)
EVENT = re.compile(r"^(Met Op|Royal Ballet|BTS |Prince 3121|IMAX: George|George Michael|Andre Rieu|Monday Mystery|Doctor Who|National Theatre|Bolshoi|Festive Fun)|Live$|Concert|Fan Event|Insider Screening|Early Access|Mystery Movie", re.I)
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
    # Matched after series prefixes are stripped (see SERIES_PREFIX).
    "Krampus on Krampusnacht": ("Krampus", 2015), "Eight Crazy Nights": ("Adam Sandler's Eight Crazy Nights", 2002),
    "The Grinch": ("Dr. Seuss' The Grinch", 2018), "King of Kings": ("The King of Kings", 2025),
    'Spider-Man: "Brand New" Brand New Day': ("Spider-Man: Brand New Day", 2026),
}
# Series / programme labels Regal puts in front of a title ("Naughty List: Brazil", "CUT26: Hoosiers (1986)",
# "HS26: Elf (2003)"). Stripped before the Rotten Tomatoes lookup. Any CODE26-style tag is covered automatically.
SERIES_PREFIX = re.compile(r"^(?:[A-Z]{2,6}\d{2}|Naughty List|Nice List|Vice Films|Fangoria|Fathom(?: Events)?|RealD 3D|"
                           r"Studio Ghibli Fest(?: \d{4})?|Cult Classics?|Throwback Thursday|Flashback Cinema|IMAX)\s*:\s*", re.I)
# Variant suffixes folded into the base movie (shown as a tag on the showtime).
VARIANTS = [(re.compile(r"\s*\(Open Cap/Eng Sub\)\s*$", re.I), "Open caption"), (re.compile(r"\s*\(Sensory\)\s*$", re.I), "Sensory friendly"),
            (re.compile(r"\s+OCAP\s*$", re.I), "Open caption"), (re.compile(r"\s+\(?Open Caption(ed)?\)?\s*$", re.I), "Open caption")]
FLAGS = {"3D": "3D", "IMAX": "IMAX", "ScreenX": "ScreenX", "ScreenX 3D": "ScreenX 3D", "InfinityVi": "InfinityVision", "OC": "Open caption",
         "Sub-Titled": "Subtitled", "Japanese": "Japanese", "Korean": "Korean", "Spanish": "Spanish", "Sensory": "Sensory friendly", "WatchParty": "Watch party"}


def slugify(t):
    t = t.lower().replace("&", "")
    t = re.sub(r"[^a-z0-9\s-]", "", t).replace("-", "")
    return re.sub(r"\s+", "-", t.strip())


def norm_title(t):
    """Key used to match the same film across theatres."""
    for rx, _ in VARIANTS:
        t = rx.sub("", t)
    t = re.sub(r"\s*\((19|20)\d{2}\)\s*$", "", t)
    return re.sub(r"[^a-z0-9]", "", t.lower().replace("&", "and"))


def split_variant(t):
    for rx, label in VARIANTS:
        if rx.search(t):
            return rx.sub("", t).strip(), label
    return t, ""


def rt_key(m):
    """Rotten Tomatoes lookup key "Title|Year". Year 0 means "any year, exact title" (a series re-run with no year given)."""
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
    title, n = SERIES_PREFIX.subn("", title)
    title = re.sub(r"\s+(4K|\d+(st|nd|rd|th) Anniversary.*|Early Access|Insider Screenings|RealD 3D Fan Event|- Director's Cut)$", "", title, flags=re.I).strip()
    if title in RT_OVERRIDE:
        t, y = RT_OVERRIDE[title]
        return f"{t}|{y}"
    if title == "Sunrise on the Reaping":
        title = "The Hunger Games: Sunrise on the Reaping"
    if year is None and n:
        year = 0          # a re-run in a series: its opening date is not the film's year
    if year is None:
        year = int((m.get("OpeningDate") or "2026")[:4])
    return f"{title}|{year}"


def indie_rt_key(title, year):
    if NO_RT.search(title):
        return None
    t = SERIES_PREFIX.sub("", re.sub(r"\s*\((19|20)\d{2}\)\s*$", "", title).strip())
    if t in RT_OVERRIDE:
        t, y = RT_OVERRIDE[t]
        return f"{t}|{y}"
    return f"{t}|{year or datetime.now(TZ).year}"


def load(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except (FileNotFoundError, TypeError):
        return default


def kind_of(title):
    return "event" if EVENT.search(title) else ("classic" if CLASSIC.search(title) else "film")


def clean_desc(d):
    d = re.sub(r"\s+", " ", d or "").strip()
    m = re.search(r"\d+\s*minutes\s*\|[^|]*\|\s*\d{4}\s*", d)   # Eventive card header glued onto the text
    if m:
        d = d[m.end():]
    return re.sub(r"\s*More details\W*.*$", "", d).strip()


# ---------- per-theatre readers: each returns (movies: {key: movie}, shows: [dict]) ----------

def read_regal(raw, cache):
    by_code = {m["MasterMovieCode"]: m for m in raw["movies"]}
    slugs = raw.get("slugs", {})
    base_of, variant_of = {}, {}
    title_to_code = {m["Title"]: c for c, m in by_code.items()}
    for c, m in by_code.items():
        base_of[c], variant_of[c] = c, ""
        for rx, label in VARIANTS:
            if rx.search(m["Title"]):
                bt = rx.sub("", m["Title"])
                if bt in title_to_code:
                    base_of[c], variant_of[c] = title_to_code[bt], label
    movies, shows = {}, []
    for code, local, perf, aud, attrs in raw["shows"]:
        b = base_of.get(code, code)
        m = by_code[b]
        key = norm_title(m["Title"])
        if key not in movies:
            media = m.get("Media") or []
            pick = lambda st: next((x.get("SecureUrl") for x in media if x.get("SubType") == st and x.get("SecureUrl")), "")
            k = rt_key(m)
            rt = cache.get(k, {}) if k else {}
            title = m["Title"]
            movies[key] = {
                "id": b, "title": title, "rating": m.get("Rating") or "", "runtime": m.get("Duration") or 0,
                "genre": " / ".join(x for x in [m.get("GenrePrimary"), m.get("GenreSecondary")] if x),
                "opens": (m.get("OpeningDate") or "")[:10], "desc": re.sub(r"\s+", " ", m.get("Description") or "").strip(),
                "directors": ", ".join((m.get("Directors") or [])[:3]), "cast": ", ".join((m.get("Actors") or [])[:5]),
                "poster": pick("TV_SmallPosterImage") or pick("Mobile_MovieThumbnail"), "wide": pick("Mobile_MovieFeed"),
                "trailer": m.get("TrailerUrl") or pick("Trailer_Youtube") or "", "rt": rt.get("score", ""), "rtUrl": rt.get("url", ""),
                "kind": kind_of(title), "rtKey": k,
                "pages": {"regal": f"https://www.regmovies.com/movies/{slugs.get(b) or slugify(title) + '-' + b.lower()}?site={THEATRE['code']}"},
            }
        tags = [FLAGS[a] for a in attrs.split("|") if a in FLAGS]
        if variant_of.get(code) and variant_of[code] not in tags:
            tags.append(variant_of[code])
        slug = slugs.get(code) or slugify(by_code[code]["Title"]) + "-" + code.lower()
        shows.append({"key": key, "local": local[:16], "aud": aud, "tags": " · ".join(tags), "link": slug, "perf": perf, "th": "regal"})
    return movies, shows


def read_tinpan(raw, cache):
    movies, shows = {}, []
    for fid, local, label in raw["shows"]:
        f = raw["films"].get(fid)
        if not f:
            continue
        full = f["title"].strip()
        title, _, note = full.partition(" | ")       # e.g. "The Cycle of Love | Bend Film Festival Alum!"
        title, var = split_variant(title)
        key = norm_title(title)
        if key not in movies:
            k = indie_rt_key(title, f.get("year"))
            rt = cache.get(k, {}) if k else {}
            movies[key] = {"id": "tp-" + fid, "title": title, "rating": f.get("rating") or "", "runtime": f.get("runtime") or 0,
                           "genre": "", "opens": "", "desc": clean_desc(f.get("desc")), "directors": "", "cast": "",
                           "poster": f.get("poster") or "", "wide": "", "trailer": "", "rt": rt.get("score", ""), "rtUrl": rt.get("url", ""),
                           "kind": kind_of(full), "rtKey": k, "pages": {"tinpan": f["url"]}}
        tags = [x for x in [var, note.strip(" !").strip(), label] if x]
        shows.append({"key": key, "local": local[:16], "aud": "", "tags": " · ".join(tags), "link": f["url"],
                      "perf": f"tp-{fid}-{local[:16].replace('-', '').replace(':', '').replace('T', '')}", "th": "tinpan"})
    return movies, shows


def read_osf(raw, cache):
    movies, shows = {}, []
    year = datetime.now(TZ).year
    for title_raw, local, pid, url in raw["shows"]:
        f = raw["films"].get(title_raw, {})
        title, var = split_variant(title_raw)
        key = norm_title(title)
        if key not in movies:
            k = indie_rt_key(title, year)
            rt = cache.get(k, {}) if k else {}
            movies[key] = {"id": "osf-" + slugify(title), "title": title, "rating": (f.get("rating") or "").replace("-", ""),
                           "runtime": f.get("runtime") or 0, "genre": "", "opens": "", "desc": "", "directors": "", "cast": "",
                           "poster": f.get("poster") or "", "wide": "", "trailer": "", "rt": rt.get("score", ""), "rtUrl": rt.get("url", ""),
                           "kind": kind_of(title), "rtKey": k, "pages": {"osf": THEATRES[TH["osf"]]["url"]}}
        shows.append({"key": key, "local": local[:16], "aud": "", "tags": var, "link": url, "perf": f"osf-{pid or title + local}", "th": "osf"})
    return movies, shows


def read_previous(prev, th_id, cache):
    """Showtimes for one theatre from the current data/movies.json (old single-theatre format = all Regal)."""
    if not prev or not prev.get("shows"):
        return {}, []
    multi = "theatres" in prev
    ths = [t["id"] for t in prev["theatres"]] if multi else ["regal"]
    links = prev.get("links") or prev.get("slugs") or []
    movies, shows = {}, []
    for s in prev["shows"]:
        th = ths[s[7]] if multi and len(s) > 7 else "regal"
        if th != th_id:
            continue
        pm = dict(prev["movies"][s[0]])
        key = norm_title(pm["title"])
        if key not in movies:
            pages = pm.get("pages")
            if isinstance(pages, list):
                pages = {ths[i]: u for i, u in pages}
            pages = {k: v for k, v in (pages or {"regal": pm.get("regal", "")}).items() if k == th_id}
            k = pm.get("rtKey")
            rt = cache.get(k, {}) if k else {}
            pm.update({"pages": pages, "rtKey": k, "rt": rt.get("score", pm.get("rt", "")), "rtUrl": rt.get("url", pm.get("rtUrl", ""))})
            for x in ("i", "first", "last", "days", "shows", "theatres", "regal"):
                pm.pop(x, None)
            movies[key] = pm
        shows.append({"key": key, "local": s[1], "aud": s[3], "tags": s[4], "link": links[s[5]], "perf": s[6], "th": th})
    return movies, shows


def gather(args, cache, report):
    prev = load(OUT, None)
    parts = []
    for th_id, reader in (("regal", read_regal), ("tinpan", read_tinpan), ("osf", read_osf)):
        raw = load(args.get(th_id), None) if args.get(th_id) else None
        if raw and raw.get("shows"):
            mv, sh = reader(raw, cache)
            report[th_id] = f"new pull ({len(sh)} shows)"
        else:
            mv, sh = read_previous(prev, th_id, cache)
            report[th_id] = f"kept previous data ({len(sh)} shows)" + (" - pull missing or empty" if args.get(th_id) else "")
        drop = {k for k, m in mv.items() if NOT_MOVIE.search(m["title"])}
        if drop:
            report.setdefault("droppedNonMovies", []).extend(sorted(mv[k]["title"] for k in drop))
            mv = {k: m for k, m in mv.items() if k not in drop}
            sh = [x for x in sh if x["key"] not in drop]
        parts.append((th_id, mv, sh))
    return parts


def queries(args):
    cache = load(RT_CACHE, {})
    now = datetime.now(timezone.utc)
    out = set()
    for _, mv, _ in gather(args, cache, {}):
        for m in mv.values():
            k = m.get("rtKey")
            if not k:
                continue
            c = cache.get(k)
            recent = int(k.rsplit("|", 1)[1] or 0) >= now.year - 1
            stale = not c or not c.get("score") or (recent and c.get("checked", "") < (now - timedelta(days=6)).strftime("%Y-%m-%d"))
            if stale:
                out.add(k)
    return sorted(out)


def build(args):
    cache = load(RT_CACHE, {})
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    for k, v in (load(args.get("rt"), {}) or {}).items():
        if v and v[0] not in ("NOMATCH", "ERR"):
            cache[k] = {"title": v[0], "year": v[1], "score": v[2] or "", "url": v[3], "checked": today}
        elif k not in cache:
            cache[k] = {"title": "", "year": None, "score": "", "url": "", "checked": today}
    os.makedirs(os.path.dirname(RT_CACHE), exist_ok=True)
    with open(RT_CACHE, "w") as f:
        json.dump(dict(sorted(cache.items())), f, indent=0)

    report = {}
    parts = gather(args, cache, report)
    # Merge: Regal's richer record wins; the indies add their page link and fill gaps.
    merged, all_shows = {}, []
    for th_id, mv, sh in parts:
        for key, m in mv.items():
            if key not in merged:
                merged[key] = m
            else:
                base = merged[key]
                base["pages"].update(m["pages"])
                for fld in ("poster", "desc", "rating", "runtime", "trailer", "rtKey"):
                    if not base.get(fld) and m.get(fld):
                        base[fld] = m[fld]
                if not base.get("rt") and m.get("rt"):
                    base["rt"], base["rtUrl"] = m["rt"], m["rtUrl"]
        all_shows += sh

    now_local = datetime.now(TZ).replace(tzinfo=None)
    movies, idx, shows, links, link_idx = [], {}, [], [], {}
    for s in sorted(all_shows, key=lambda s: (s["local"], TH[s["th"]])):
        dt = datetime.fromisoformat(s["local"])
        if dt < now_local - timedelta(hours=1):
            continue
        if s["key"] not in idx:
            idx[s["key"]] = len(movies)
            movies.append(merged[s["key"]])
        if s["link"] not in link_idx:
            link_idx[s["link"]] = len(links); links.append(s["link"])
        utc = dt.replace(tzinfo=TZ).astimezone(timezone.utc)
        shows.append([idx[s["key"]], s["local"], int(utc.timestamp()), s["aud"], s["tags"], link_idx[s["link"]], s["perf"], TH[s["th"]]])

    for i, m in enumerate(movies):
        mine = [s for s in shows if s[0] == i]
        days = sorted({s[1][:10] for s in mine})
        m["first"], m["last"], m["days"], m["shows"] = days[0], days[-1], len(days), len(mine)
        m["theatres"] = sorted({s[7] for s in mine})
        m["pages"] = sorted([[TH[k], v] for k, v in m["pages"].items() if v and TH[k] in m["theatres"]])
        m.pop("regal", None)

    if not shows:
        sys.exit("no upcoming shows from any theatre; refusing to overwrite data")
    counts = {t["id"]: sum(1 for s in shows if s[7] == TH[t["id"]]) for t in THEATRES}
    out = {"theatres": THEATRES, "theatre": THEATRE, "updated": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"),
           "fetched": {k: (load(args.get(k), {}) or {}).get("fetched") for k in TH}, "movies": movies, "links": links,
           "showFields": ["movie", "local", "utc", "auditorium", "tags", "link", "performanceId", "theatre"], "shows": shows}
    prev = load(OUT, {}) or {}
    pf = prev.get("fetched")
    for k in TH:  # keep the previous pull time for theatres not pulled this run
        if not out["fetched"][k]:
            out["fetched"][k] = pf.get(k) if isinstance(pf, dict) else (pf if k == "regal" else None)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(json.dumps({"movies": len(movies), "shows": len(shows), "perTheatre": counts, "sources": report,
                      "range": [shows[0][1], shows[-1][1]] if shows else None,
                      "withRT": sum(1 for m in movies if m["rt"]), "multiTheatre": [m["title"] for m in movies if len(m["theatres"]) > 1]}))


def parse(argv):
    mode, rest, args = argv[1], argv[2:], {}
    i = 0
    pos = []
    while i < len(rest):
        if rest[i].startswith("--"):
            args[rest[i][2:]] = rest[i + 1]; i += 2
        else:
            pos.append(rest[i]); i += 1
    if pos:                       # legacy: build.py build RAW.json [RT_NEW.json]
        args.setdefault("regal", pos[0])
        if len(pos) > 1:
            args.setdefault("rt", pos[1])
    return mode, args


if __name__ == "__main__":
    mode, args = parse(sys.argv)
    for th in ("regal", "tinpan", "osf"):
        if args.get(th) and not os.path.exists(args[th]):
            print(f"warning: {th} file {args[th]} not found; keeping previous {th} data", file=sys.stderr)
    if mode == "queries":
        print(json.dumps(queries(args)))
    else:
        build(args)
