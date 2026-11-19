// Run in a browser tab open on https://www.regmovies.com/theatres/regal-old-mill-0758 (javascript_tool).
// Pulls every listed date from Regal's showtimes API and downloads regal-0758-YYYY-MM-DD.json to the Downloads folder.
await new Promise(r => setTimeout(r, 2000));
const T = '0758';
const api = d => `/api/getShowtimes?theatres=${T}&date=${d}&hoCode=&ignoreCache=false&moviesOnly=false`;
const today = new Date().toLocaleDateString('en-US', {timeZone: 'America/Los_Angeles', month: '2-digit', day: '2-digit', year: 'numeric'}).replace(/\//g, '-');
const base = await (await fetch(api(today))).json();
const dates = base.datesWithShows.map(d => { const [y, m, dd] = d.slice(0, 10).split('-'); return `${m}-${dd}-${y}`; });
const shows = [], movies = {}, fails = [];
const add = ms => (ms || []).forEach(m => { movies[m.MasterMovieCode] = m; });
add(base.movies);
for (let i = 0; i < dates.length; i += 10) {
  await Promise.all(dates.slice(i, i + 10).map(async d => {
    try {
      const r = await (await fetch(api(d))).json(); add(r.movies);
      (r.shows || []).forEach(s => s.Film.forEach(f => f.Performances.forEach(p =>
        shows.push([f.MasterMovieCode, p.CalendarShowTime, p.PerformanceId, p.Auditorium, (p.PerformanceAttributes || []).join('|')]))));
    } catch (e) { fails.push(d); }
  }));
}
const used = [...new Set(shows.map(s => s[0]))];
const slugs = {};
document.querySelectorAll('a[href*="/movies/"]').forEach(a => { const m = a.href.match(/movies\/([^?#]+?-(ho\d+))/i); if (m) slugs[m[2].toUpperCase()] = m[1]; });
const raw = {fetched: new Date().toISOString(), theatre: T, movies: used.map(c => movies[c]).filter(Boolean),
  slugs: Object.fromEntries(used.filter(c => slugs[c]).map(c => [c, slugs[c]])), shows, fails};
const name = `regal-${T}-${new Date().toISOString().slice(0, 10)}.json`;
const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(raw)], {type: 'application/json'}));
a.download = name; document.body.appendChild(a); a.click();
({file: name, dates: dates.length, shows: shows.length, movies: raw.movies.length, fails});
