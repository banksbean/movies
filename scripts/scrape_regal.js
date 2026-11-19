// Run in a browser tab open on https://www.regmovies.com/theatres/regal-old-mill-0758 (javascript_tool).
// Re-runnable and paced: each run fetches dates one at a time (PACE ms apart) for at most BUDGET ms, saves progress
// in sessionStorage, and returns {status:'running', done, total}. After the first run, call `await window.__regalStep()` (or rerun this file) until it returns status 'done';
// it then downloads regal-0758-YYYY-MM-DD.json to Downloads and returns {status:'done', file, dates, shows, movies, fails, chunks}.
// status 'blocked' means Regal's rate limit kicked in (429 / Cloudflare challenge, which shows up as a hung request).
// Do not try to get past it: wait a few minutes, then call __regalStep() again; progress is kept and it resumes.
// `await window.__regalStep({finish: true})` finalizes early with the dates fetched so far (rest listed in `unfetched`).
// Fallback when the download can't be reached: window.__regalChunk(i) returns chunk i (of `chunks`) of the raw JSON.
window.__regalStep = async (opts = {}) => {
  const T = '0758', KEY = 'regal_scrape_' + T, BUDGET = 30000, PACE = 1500, TIMEOUT = 10000;
  const t0 = Date.now();
  const api = d => `/api/getShowtimes?theatres=${T}&date=${d}&hoCode=&ignoreCache=false&moviesOnly=false`;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const get = u => Promise.race([
    fetch(u).then(async r => {
      const ct = r.headers.get('content-type') || '';
      if (r.status === 429 || r.status === 403 || !ct.includes('json')) return {blocked: r.status};
      if (!r.ok) return {err: r.status};
      return {body: await r.json()};
    }).catch(e => ({err: String(e)})),
    sleep(TIMEOUT).then(() => ({blocked: 'timeout'}))]);
  let st; try { st = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { st = null; }
  if (st && st.day !== new Date().toISOString().slice(0, 10)) st = null;
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { window.__regalState = st; } };
  if (!st && window.__regalState) st = window.__regalState;
  let out;
  if (!st) {
    const today = new Date().toLocaleDateString('en-US', {timeZone: 'America/Los_Angeles', month: '2-digit', day: '2-digit', year: 'numeric'}).replace(/\//g, '-');
    const r = await get(api(today));
    if (r.blocked) out = {status: 'blocked', http: r.blocked, at: 'first date'};
    else if (!r.body) out = {status: 'error', error: r.err, at: 'first date'};
    else {
      const dates = r.body.datesWithShows.map(d => { const [y, m, dd] = d.slice(0, 10).split('-'); return `${m}-${dd}-${y}`; });
      st = {day: new Date().toISOString().slice(0, 10), dates, next: 0, shows: [], movies: {}, fails: [], retried: []};
      (r.body.movies || []).forEach(m => { st.movies[m.MasterMovieCode] = m; });
      save();
    }
  }
  while (!out && !opts.finish && st.next < st.dates.length && Date.now() - t0 < BUDGET - TIMEOUT - PACE) {
    await sleep(PACE);
    const d = st.dates[st.next];
    const r = await get(api(d));
    if (r.blocked) { st.blocks = (st.blocks || 0) + 1; save(); out = {status: 'blocked', http: r.blocked, at: d, done: st.next, total: st.dates.length, shows: st.shows.length, blocks: st.blocks}; break; }
    if (r.body) {
      (r.body.movies || []).forEach(m => { st.movies[m.MasterMovieCode] = m; });
      (r.body.shows || []).forEach(s => s.Film.forEach(f => f.Performances.forEach(p =>
        st.shows.push([f.MasterMovieCode, p.CalendarShowTime, p.PerformanceId, p.Auditorium, (p.PerformanceAttributes || []).join('|')]))));
    } else if (!st.retried.includes(d)) { st.retried.push(d); save(); continue; }  // retry a failed date once
    else st.fails.push(d);
    st.next++; save();
  }
  if (!out && !opts.finish && st.next < st.dates.length) out = {status: 'running', done: st.next, total: st.dates.length, shows: st.shows.length};
  if (!out) {
    const used = [...new Set(st.shows.map(s => s[0]))];
    const slugs = {};
    document.querySelectorAll('a[href*="/movies/"]').forEach(a => { const m = a.href.match(/movies\/([^?#]+?-(ho\d+))/i); if (m) slugs[m[2].toUpperCase()] = m[1]; });
    const raw = {fetched: new Date().toISOString(), theatre: T, movies: used.map(c => st.movies[c]).filter(Boolean),
      slugs: Object.fromEntries(used.filter(c => slugs[c]).map(c => [c, slugs[c]])), shows: st.shows, fails: st.fails,
      unfetched: st.dates.slice(st.next)};
    const json = JSON.stringify(raw), CH = 40000;
    window.__regalRaw = json;
    window.__regalChunk = i => json.slice(i * CH, (i + 1) * CH);
    const name = `regal-${T}-${st.day}.json`;
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([json], {type: 'application/json'}));
    a.download = name; document.body.appendChild(a); a.click();
    out = {status: 'done', file: name, dates: st.dates.length, fetched: st.next, lastFetched: st.dates[st.next - 1], shows: st.shows.length, movies: raw.movies.length, fails: st.fails,
      bytes: json.length, chunks: Math.ceil(json.length / CH)};
  }
  return out;
};
await window.__regalStep();
