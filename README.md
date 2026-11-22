# Old Mill Movies

A cleaner way to browse what's playing in Bend, OR at three theaters: **Regal Old Mill**, **Tin Pan Theater** and
**McMenamins Old St. Francis Theater**. Day-by-day timeline, month calendar, daily showtimes, trailers, Rotten Tomatoes
scores, add-to-calendar buttons, and booking links that open each showtime on the theater's own ticketing site.

Theater chips in the filter bar switch each theater on or off (saved per browser). Every showtime carries its theater's
color and label; a film playing at more than one theater lists its times grouped by theater.

Static site for GitHub Pages: `index.html`, `sw.js` (offline cache), `data/movies.json` (showtimes), `data/rt.json` (RT score cache).
Stars, plans and notes live in each visitor's browser (localStorage); "Share with friends" passes them by link.

## Weekly refresh

Each pull is a browser step; save each result as JSON. A theater whose pull fails is simply left out of the build
command and keeps its showtimes from the current `data/movies.json`.

1. **Regal** (`REGAL.json`): in a tab on https://www.regmovies.com/theatres/regal-old-mill-0758 run `scripts/scrape_regal.js`, then call
   `await window.__regalStep()` until it returns status `done` (it downloads `regal-0758-YYYY-MM-DD.json` to Downloads).
   It fetches one date every 1.5 s, about 30 s per call, and keeps progress in sessionStorage. Regal's Cloudflare rate
   limit allows only about 23 requests at a time: on status `blocked`, wait about 10 minutes and call it again.
   `__regalStep({finish: true})` finalizes early with what was fetched.
2. **Tin Pan** (`TINPAN.json`): open https://tinpantheater2025.eventive.org/schedule?date=TODAY (YYYY-MM-DD) and run
   `scripts/scrape_tinpan.js`; it clicks through the week's 7 day tabs. Navigate the same tab to `?date=` + 7 days and run
   it again; results accumulate in the tab, and each run returns the full set so far. Stop after a week that returns
   `weekShows: 0` or after 4 weeks. Save the last run's output.
3. **Old St. Francis** (`OSF.json`): in a tab on https://www.mcmenamins.com/old-st-francis-school/old-st-francis-theater/now-playing/
   run `scripts/scrape_mcmenamins.js` (one call, reads the whole listing, usually about 11 days ahead).
4. `python3 -I build.py queries --regal REGAL.json --tinpan TINPAN.json --osf OSF.json` prints the Rotten Tomatoes lookups still needed.
5. In a tab on https://www.rottentomatoes.com run `scripts/scrape_rt.js` with `__QUERIES__` replaced by that list; save the returned JSON as RT_NEW.json.
6. `python3 -I build.py build --regal REGAL.json --tinpan TINPAN.json --osf OSF.json --rt RT_NEW.json` rewrites
   `data/movies.json` and `data/rt.json`, and prints per-theater show counts and which theaters used new vs kept data.
7. Commit and push to `main`.

Films are matched across theaters by title (punctuation, a trailing "(1988)" year and open-caption suffixes ignored); Regal's
record supplies the details and the other theaters add their own page links.

Regal's showtimes API: `/api/getShowtimes?theatres=0758&date=MM-DD-YYYY` (same-origin only).
Booking links: Regal `/movies/<slug>?site=0758&id=<PerformanceId>&date=MM-DD-YYYY`; Tin Pan uses the film's Eventive page;
Old St. Francis uses each showtime's Veezi purchase link.
