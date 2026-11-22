// Tin Pan Theater (Eventive) showtimes, one week per run.
// Open https://tinpantheater2025.eventive.org/schedule?date=YYYY-MM-DD (start with today), then run this whole file.
// It waits for the page, clicks each of the 7 day tabs, and reads every film's title, film page, poster, runtime,
// description and showtimes from what the page shows. Results build up in this tab's sessionStorage across weeks
// (a pull older than 2 hours is discarded), so for the next week navigate the same tab to ?date=<start + 7 days>
// and run the file again. Each run returns a JSON string:
// {theatre:"tinpan", fetched, week:"YYYY-MM-DD", weekShows, days, films:{<filmId>:{title,url,poster,desc,runtime,year}}, shows:[[filmId,"YYYY-MM-DDTHH:MM",""]]}
(async () => {
  const KEY = "tinpan.acc";
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const MON = {JAN:1,FEB:2,MAR:3,APR:4,MAY:5,JUN:6,JUL:7,AUG:8,SEP:9,OCT:10,NOV:11,DEC:12};
  const pad = n => String(n).padStart(2, "0");
  const timeRx = /^(\d{1,2}):(\d{2})\s*([ap])m?$/i;
  const norm = t => t.replace(/\s+/g, " ").trim();
  const dayRx = /^(SUN|MON|TUE|WED|THU|FRI|SAT)[A-Z]*\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*(\d{1,2})/i;
  const dayBtns = () => [...document.querySelectorAll("button")].filter(b => dayRx.test(norm(b.textContent)));
  const now = new Date();
  const dateOf = txt => {
    const m = norm(txt).toUpperCase().match(dayRx), mo = MON[m[2]], d = +m[3];
    let y = now.getFullYear(); if (mo < now.getMonth()) y++; // more than a month before now means next year
    return `${y}-${pad(mo)}-${pad(d)}`;
  };
  let acc; try { acc = JSON.parse(sessionStorage.getItem(KEY)); } catch (e) {}
  if (!acc || Date.now() - acc.started > 2 * 3600e3) acc = {started: Date.now(), films: {}, shows: [], weeks: []};
  const seen = new Set(acc.shows.map(s => s[0] + s[1]));

  for (let i = 0; i < 40 && !dayBtns().length; i++) await sleep(500);
  const n = dayBtns().length;
  if (!n) return JSON.stringify({error: "no day tabs found; page did not load or its layout changed"});
  let weekShows = 0, week = dateOf(dayBtns()[0].textContent);
  const read = date => {
    const links = [...document.querySelectorAll('a[href*="/films/"]')];
    const ids = [...new Set(links.map(a => (a.getAttribute("href").match(/\/films\/([a-z0-9]+)/i) || [])[1]).filter(Boolean))];
    for (const id of ids) {
      const own = links.filter(a => a.getAttribute("href").includes(id));
      // Smallest ancestor that holds this film's links plus its time buttons, and no other film.
      let box = own[0];
      while (box && box.parentElement) {
        box = box.parentElement;
        if ([...box.querySelectorAll('a[href*="/films/"]')].some(a => !a.getAttribute("href").includes(id))) { box = null; break; }
        if ([...box.querySelectorAll("button")].some(b => timeRx.test(b.textContent.trim()))) break;
      }
      if (!box) continue;
      const text = norm(box.innerText || box.textContent);
      const title = own.map(a => norm(a.textContent)).find(t => t && !/more details/i.test(t)) || "";
      const bg = [box, ...box.querySelectorAll("*")].map(e => e.style && e.style.backgroundImage).find(Boolean) || "";
      const img = (bg.match(/url\(["']?([^"')]+)/) || [])[1] || box.querySelector("img")?.src || "";
      const runtime = +((text.match(/(\d+)\s*minutes/i) || [])[1] || 0);
      const year = +((text.match(/minutes[^\n]*?\b((?:19|20)\d{2})\b/i) || [])[1] || 0) || null;
      const desc = [...box.querySelectorAll("p,div,span")].filter(e => e.childElementCount <= 2).map(e => norm(e.textContent))
        .filter(t => t.length > 60 && !/\bminutes\b/.test(t)).sort((a, b) => a.length - b.length)[0] || "";
      const f = acc.films[id] ||= {title, url: location.origin + "/films/" + id, poster: "", desc: "", runtime: 0, year: null};
      f.poster ||= img; f.desc ||= desc.replace(/\s*More details\W*$/i, ""); f.runtime ||= runtime; f.year ||= year;
      for (const b of box.querySelectorAll("button")) {
        const m = b.textContent.trim().match(timeRx); if (!m) continue;
        let h = +m[1] % 12; if (m[3].toLowerCase() === "p") h += 12;
        const local = `${date}T${pad(h)}:${m[2]}`;
        if (seen.has(id + local)) continue;
        seen.add(id + local); acc.shows.push([id, local, ""]); weekShows++;
      }
    }
  };
  for (let i = 0; i < n; i++) {
    const b = dayBtns()[i]; const date = dateOf(b.textContent);
    b.click(); await sleep(1800);
    read(date);
  }
  acc.weeks.push(week);
  sessionStorage.setItem(KEY, JSON.stringify(acc));
  acc.shows.sort((a, b) => a[1].localeCompare(b[1]));
  return JSON.stringify({theatre: "tinpan", fetched: new Date().toISOString(), week, weekShows, days: n, weeks: acc.weeks, films: acc.films, shows: acc.shows});
})()
