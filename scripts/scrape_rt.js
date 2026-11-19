// Run in a browser tab open on https://www.rottentomatoes.com (javascript_tool), after replacing __QUERIES__
// with the JSON list printed by `python3 -I build.py queries RAW.json`. Returns {"Title|Year": [title, year, score, url]}.
const Q = __QUERIES__;
const norm = s => s.toLowerCase().replace(/william shakespeare's/, '').replace(/&/g, 'and').replace(/[^a-z0-9]/g, '');
const res = {};
for (let i = 0; i < Q.length; i += 8) {
  await Promise.all(Q.slice(i, i + 8).map(async q => {
    const [t, y] = q.split('|'); const Y = +y;
    try {
      const h = await (await fetch('/search?search=' + encodeURIComponent(t))).text();
      const doc = new DOMParser().parseFromString(h, 'text/html');
      const rows = [...doc.querySelectorAll('search-page-result[type=movie] search-page-media-row')].map(e => ({
        t: e.querySelector('[data-qa=info-name]')?.textContent.trim(), y: +(e.getAttribute('release-year') || 0),
        s: e.getAttribute('tomatometer-score'), u: e.querySelector('a[data-qa=info-name]')?.getAttribute('href')}));
      const ok = r => Math.abs(r.y - Y) <= 1;
      const m = rows.find(r => norm(r.t) === norm(t) && ok(r)) || rows.find(r => (norm(r.t).includes(norm(t)) || norm(t).includes(norm(r.t))) && ok(r));
      res[q] = m ? [m.t, m.y, m.s || '', m.u] : ['NOMATCH', rows.slice(0, 3).map(r => r.t + ' ' + r.y).join('; ')];
    } catch (e) { res[q] = ['ERR', String(e)]; }
  }));
}
JSON.stringify(res);
