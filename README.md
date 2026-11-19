# Old Mill Movies

A cleaner way to browse what's playing at Regal Old Mill (Bend, OR): a day-by-day timeline, a month calendar,
daily showtimes, trailers, Rotten Tomatoes scores, add-to-calendar buttons, and booking links that open the
showtime on regmovies.com (sign in there with your own Regal Crown Club account).

Static site for GitHub Pages: `index.html`, `sw.js` (offline cache), `data/movies.json` (showtimes), `data/rt.json` (RT score cache).
Stars, plans and notes live in each visitor's browser (localStorage); "Share with friends" passes them by link.

## Weekly refresh

1. In a browser tab on https://www.regmovies.com/theatres/regal-old-mill-0758 run `scripts/scrape_regal.js`
   (it downloads `regal-0758-YYYY-MM-DD.json` to Downloads).
2. `python3 -I build.py queries RAW.json` prints the Rotten Tomatoes lookups still needed.
3. In a tab on https://www.rottentomatoes.com run `scripts/scrape_rt.js` with `__QUERIES__` replaced by that list; save the returned JSON as RT_NEW.json.
4. `python3 -I build.py build RAW.json RT_NEW.json` rewrites `data/movies.json` and `data/rt.json`.
5. Commit and push to `main`.

Regal's showtimes API: `/api/getShowtimes?theatres=0758&date=MM-DD-YYYY` (same-origin only).
Booking link format: `/movies/<slug>?site=0758&id=<PerformanceId>&date=MM-DD-YYYY`.
