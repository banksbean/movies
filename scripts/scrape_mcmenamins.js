// McMenamins Old St. Francis Theater showtimes. Run in a browser tab on
// https://www.mcmenamins.com/old-st-francis-school/old-st-francis-theater/now-playing/ once it has loaded.
// Reads the showtime cards on the page (one card per film per day, each time linking to its Veezi purchase page).
// Returns a JSON string: {theatre:"osf", fetched, films:{<title>:{title, rating, runtime, poster}}, shows:[[title, "YYYY-MM-DDTHH:MM", perfId, url]]}
(() => {
  const pad = n => String(n).padStart(2, "0");
  const films = {}, shows = [], seen = new Set();
  for (const card of document.querySelectorAll(".tm-panel-card.movie")) {
    const js = [...card.querySelectorAll('a[href^="javascript"]')].map(a => a.getAttribute("href")).find(h => /showTheaterMovie/.test(h)) || "";
    const m = js.match(/showTheaterMovie\('([^']*)','((?:[^'\\]|\\.)*)','(\d{1,2})\/(\d{1,2})\/(\d{4})'\)/);
    if (!m || !/St\.? Francis/i.test(m[1])) continue;
    const title = (card.querySelector(".tm-panel-titlebg .uk-panel-title")?.textContent || m[2]).trim();
    const date = `${m[5]}-${pad(m[3])}-${pad(m[4])}`;
    const info = card.querySelector(".uk-panel-time")?.textContent || "";
    const rating = (info.match(/\(([^)]+)\)/) || [])[1] || "";
    const runtime = +((info.match(/(\d+)\s*min/i) || [])[1] || 0);
    const bg = card.querySelector(".uk-panel-teaser")?.style.backgroundImage || "";
    const poster = (bg.match(/url\(["']?([^"')]+)/) || [])[1] || "";
    const f = films[title] ||= {title, rating: "", runtime: 0, poster: ""};
    f.rating ||= rating; f.runtime ||= runtime; f.poster ||= poster;
    for (const a of card.querySelectorAll('.uk-panel-movietimes a[href*="veezi"]')) {
      const t = a.textContent.trim().match(/^(\d{1,2})(?::(\d{2}))?\s*([ap])m$/i); if (!t) continue;
      let h = +t[1] % 12; if (t[3].toLowerCase() === "p") h += 12;
      const id = (a.href.match(/purchase\/(\d+)/) || [])[1] || "";
      const local = `${date}T${pad(h)}:${t[2] || "00"}`, k = id || title + local;
      if (seen.has(k)) continue; seen.add(k);
      shows.push([title, local, id, a.href]);
    }
  }
  const prices = (document.body.innerText.match(/Adults?:[^\n]{0,80}/) || [""])[0];
  return JSON.stringify({theatre: "osf", fetched: new Date().toISOString(), prices, films, shows});
})()
