"use strict";

// Target: Firefox 68. No ?. or ??, no replaceChildren. ASCII only (accents as \u escapes).
// Screens, chosen by the URL hash:
//   #/                      home: favourite cards
//   #/stop/30101/A/A        detail of one stop of a line
//   #/alerts                traffic alerts
//   #/edit                  manage the favourites
//   #/browse                browse every line, its stops and its map

const REFRESH_MS = 30000; // ask the server every 30 s
const TICK_MS = 15000; // redraw the countdowns every 15 s
const NIGHT_FROM = 20; // night theme from 20:00...
const NIGHT_UNTIL = 7; // ...until 07:00

const DAYS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
const MONTHS = [
  "janvier", "f\u00e9vrier", "mars", "avril", "mai", "juin",
  "juillet", "ao\u00fbt", "septembre", "octobre", "novembre", "d\u00e9cembre",
];
const SHORT_MONTHS = [
  "janv.", "f\u00e9vr.", "mars", "avr.", "mai", "juin",
  "juil.", "ao\u00fbt", "sept.", "oct.", "nov.", "d\u00e9c.",
];
// Leaflet (the map library) is only loaded when the browse screen opens.
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/";
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const MODES = [["metro", "M\u00e9tro"], ["tram", "Tram"], ["bus", "Bus"]];

let data = null; // the last answer for the current screen
let theme = remembered("theme") || "auto"; // "auto" (by the hour), "day" or "night"
let reachable = true; // false when our own server does not answer
let clockOffset = 0; // server time minus tablet time, in ms
let renderedHash = null; // the screen drawn last, to keep its scroll on a redraw

// ---------------------------------------------------------------- scaling

// The design is 1024x768 (the tablet). The CSS uses rem everywhere, so setting
// the root font size scales the whole dashboard to the display.
// (CSS min()/clamp() would do it without JS, but Firefox 68 lacks them.)
function fitToScreen() {
  const portrait = window.innerHeight > window.innerWidth;
  const scale = portrait
    ? Math.min(window.innerWidth / 600, window.innerHeight / 1100)
    : Math.min(window.innerWidth / 1024, window.innerHeight / 768);
  document.documentElement.style.fontSize = 16 * scale + "px";
}

// ---------------------------------------------------------------- helpers

// localStorage can be missing or blocked: the dashboard must work without it.
function remembered(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function remember(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    // not remembered across reloads, but still applied now
  }
}

function nextTheme() {
  theme = { auto: "day", day: "night", night: "auto" }[theme];
  remember("theme", theme);
  render();
}

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.documentElement.requestFullscreen();
  }
}

// "2026-10-16T08:05:00.123456" -> a Date, read as local time.
function parseTime(text) {
  const [day, time] = text.slice(0, 19).split("T");
  const [year, month, date] = day.split("-").map(Number);
  const [hours, minutes, seconds] = time.split(":").map(Number);
  return new Date(year, month - 1, date, hours, minutes, seconds);
}

// The tablet's clock drifts: we keep the server's time, measured at each answer.
function serverNow() {
  return new Date(Date.now() + clockOffset);
}

function minutesUntil(departure, now) {
  return Math.floor((parseTime(departure.time) - now) / 60000);
}

function clock(date) {
  const two = (n) => String(n).padStart(2, "0");
  return two(date.getHours()) + ":" + two(date.getMinutes());
}

function shortDate(date) {
  return date.getDate() + " " + SHORT_MONTHS[date.getMonth()];
}

function countdown(minutes) {
  return minutes < 1 ? "Proche" : minutes + " min";
}

// Creates <tag class="className">text</tag>. textContent, never innerHTML.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// The mockup's stroke icons (24x24). innerHTML is safe here: constant markup, never data.
const ICONS = {
  settings: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  warning: '<path d="M12 3 2 21h20L12 3z"/><path d="M12 10v5M12 18h.01"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  left: '<path d="m15 6-6 6 6 6"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  realtime: '<circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.48M7.76 16.24a6 6 0 0 1 0-8.48M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  auto: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
  swap: '<path d="m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3z"/>',
};

function icon(name, size) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.style.width = size / 16 + "rem"; // sizes are given in px at 1024x768
  svg.style.height = size / 16 + "rem";
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONS[name];
  return svg;
}

// An icon followed by a text, e.g. the clock and "Horaire prevu".
function withIcon(className, name, text) {
  const node = el("span", className ? className + " with-icon" : "with-icon");
  node.appendChild(icon(name, 18));
  node.appendChild(el("span", "", text));
  return node;
}

// A departure time, with where it comes from: live (green waves) or the timetable (clock).
function departureTime(departure) {
  const live = departure.realtime;
  const node = withIcon(live ? "time live" : "time", live ? "realtime" : "clock", clock(parseTime(departure.time)));
  node.title = live ? "Temps r\u00e9el" : "Horaire pr\u00e9vu";
  return node;
}

function button(className, text, onclick) {
  const node = el("button", className, text);
  node.type = "button";
  node.onclick = onclick;
  return node;
}

function go(hash) {
  location.hash = hash;
}

// The official pictogram if it exists, else a badge in the line colour.
function lineBadge(code, colour, size) {
  const badge = el("span", "badge", code);
  const known = demo.lines !== null && demo.lines[code] ? demo.lines[code].colour : "";
  badge.style.background = colour || known || "#596069";
  badge.style.fontSize = (size * 0.7) / 16 + "rem";
  if (window.DEMO) {
    return badge; // the demo has no pictograms (their licence is unclear)
  }
  const img = el("img", "picto");
  img.src = "pictos/" + encodeURIComponent(code) + ".svg"; // relative: works under a sub-path
  img.alt = code;
  img.style.height = size / 16 + "rem";
  img.onerror = () => img.replaceWith(badge);
  return img;
}

// One button for the direction: it shows where the line goes, a tap turns it around.
function directionButton(line, sens, choose) {
  const other = Object.keys(line.destinations).filter((s) => s !== sens)[0];
  const node = button("choice direction with-icon", "", () => choose(other));
  if (other) {
    node.appendChild(icon("swap", 22));
  } else {
    node.disabled = true; // a loop line: a single direction
  }
  node.appendChild(el("span", "", "vers " + line.destinations[sens]));
  return node;
}

function backButton(text) {
  const node = button("back with-icon", "", () => go("#/"));
  node.appendChild(icon("left", 22));
  node.appendChild(el("span", "", text));
  return node;
}

async function api(path, options) {
  if (window.DEMO) {
    return demoApi(path, options);
  }
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.join(", ") : body.detail;
    throw new Error(String(detail));
  }
  return body;
}

// ---------------------------------------------------------------- demo

// On GitHub Pages there is no server: the Pages workflow sets window.DEMO, and
// api() answers from the JSON files that scripts/snapshot_demo.py recorded.
const demo = { snapshot: null, lines: null, offset: 0, offsetSince: 0 };
const DEMO_REPLAY_MS = 45 * 60000; // the recorded departures last about an hour

async function demoFile(name) {
  const response = await fetch("demo/" + name);
  if (!response.ok) {
    throw new Error("Pas de donn\u00e9es pour cet arr\u00eat dans la d\u00e9mo");
  }
  return response.json();
}

// A Date -> "2026-10-16T20:26:40", local time, like the server sends.
function isoLocal(date) {
  const two = (n) => String(n).padStart(2, "0");
  const day = date.getFullYear() + "-" + two(date.getMonth() + 1) + "-" + two(date.getDate());
  return day + "T" + clock(date) + ":" + two(date.getSeconds());
}

// The recording is replayed from the visitor's arrival: every time in it moves
// by the time elapsed since then. Started again when the departures run out.
async function demoStart() {
  if (demo.snapshot === null) {
    demo.snapshot = await demoFile("snapshot.json");
  }
  if (Date.now() - demo.offsetSince > DEMO_REPLAY_MS) {
    demo.offset = Date.now() - parseTime(demo.snapshot.now);
    demo.offsetSince = Date.now();
  }
}

function demoShift(value) {
  if (typeof value === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(value)) {
    return isoLocal(new Date(parseTime(value).getTime() + demo.offset));
  }
  if (Array.isArray(value)) {
    return value.map(demoShift);
  }
  if (value !== null && typeof value === "object") {
    const copy = {};
    Object.keys(value).forEach((key) => {
      copy[key] = demoShift(value[key]);
    });
    return copy;
  }
  return value;
}

// The visitor's own favourites stay in their browser; the recorded ones first.
function demoFavourites() {
  try {
    const saved = JSON.parse(remembered("demo-favourites"));
    return Array.isArray(saved) ? saved : demo.snapshot.favourites;
  } catch (error) {
    return demo.snapshot.favourites;
  }
}

// Every line by code (colour, destinations), from the three tabs.
async function demoLines() {
  if (demo.lines === null) {
    const tabs = await Promise.all(MODES.map(([mode]) => demoFile("lines-" + mode + ".json")));
    demo.lines = {};
    tabs.forEach((lines) => lines.forEach((line) => {
      demo.lines[line.code] = line;
    }));
  }
  return demo.lines;
}

// A stop the recording has no departures for (a bus added in the demo): its
// names and next stops, without departures.
async function demoStopWithoutDepartures(platform, line, sens) {
  const info = (await demoLines())[line];
  const stops = await demoFile("stops/" + line + "-" + sens + ".json");
  const index = stops.map((stop) => stop.platform).indexOf(platform);
  if (!info || index < 0) {
    throw new Error("Pas de donn\u00e9es pour cet arr\u00eat dans la d\u00e9mo");
  }
  const shown = stops.slice(index, index + 7).map((stop) => stop.name);
  return {
    line: line,
    colour: info.colour,
    platform_name: stops[index].name,
    destination: info.destinations[sens],
    departures: [],
    next_stops: shown,
    remaining: stops.length - index - shown.length,
    stale: false,
  };
}

async function demoDetail(platform, line, sens) {
  let detail;
  try {
    detail = demoShift(await demoFile("detail/" + platform + "-" + line + "-" + sens + ".json"));
  } catch (error) {
    detail = await demoStopWithoutDepartures(platform, line, sens);
  }
  const here = { line: line, sens: sens, platform: platform };
  detail.favourite = demoFavourites().some((f) => sameFavourite(f, here));
  detail.now = isoLocal(new Date());
  return detail;
}

async function demoCard(favourite, alerts) {
  const card = {
    line: favourite.line,
    sens: favourite.sens,
    platform: favourite.platform,
    colour: "",
    platform_name: favourite.platform,
    destination: "",
    departures: [],
    disrupted: alerts.some((a) => a.line === favourite.line && a.kind === "Perturbation"),
  };
  const detail = await demoDetail(favourite.platform, favourite.line, favourite.sens);
  const now = new Date();
  return Object.assign(card, {
    colour: detail.colour,
    platform_name: detail.platform_name,
    destination: detail.destination,
    departures: detail.departures.filter((d) => parseTime(d.time) >= now).slice(0, 3),
  });
}

async function demoAlerts() {
  const page = await demoFile("alerts.json");
  const lines = demoFavourites().map((f) => f.line);
  page.mine = page.network.filter((alert) => lines.indexOf(alert.line) >= 0);
  page.updated_at = isoLocal(new Date());
  return page;
}

async function demoBoard() {
  await demoLines(); // the banner's badge takes its line colour from them
  const favourites = demoFavourites();
  const alerts = (await demoAlerts()).mine;
  const cards = await Promise.all(favourites.map((f) => demoCard(f, alerts)));
  let banner = null;
  if (alerts.length > 0) {
    const worst = alerts.slice().sort((a, b) => a.severity - b.severity)[0];
    banner = { line: worst.line, title: worst.title, count: alerts.length };
  }
  const now = isoLocal(new Date());
  return { cards: cards, banner: banner, now: now, updated_at: now, stale: false };
}

// The same answers as the server's /api routes.
async function demoApi(path, options) {
  await demoStart();
  const [route, query] = path.split("?");
  const parts = route.split("/").slice(2).map(decodeURIComponent); // after "/api/"
  if (parts[0] === "favourites") {
    if (options && options.method === "PUT") {
      remember("demo-favourites", options.body);
      return JSON.parse(options.body);
    }
    return demoFavourites();
  }
  if (parts[0] === "board") {
    return demoBoard();
  }
  if (parts[0] === "alerts") {
    return demoAlerts();
  }
  if (parts[0] === "stops") {
    return demoDetail(parts[1], parts[2], parts[3]);
  }
  if (parts[0] === "lines" && parts.length === 1) {
    return demoFile("lines-" + query.split("mode=")[1] + ".json");
  }
  if (parts[0] === "lines") {
    const folder = parts[3] === "map" ? "maps/" : "stops/";
    return demoFile(folder + parts[1] + "-" + parts[2] + ".json");
  }
  throw new Error("Pas dans la d\u00e9mo : " + path);
}

function putFavourites(favourites) {
  return api("/api/favourites", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(favourites),
  });
}

function sameFavourite(a, b) {
  return a.line === b.line && a.sens === b.sens && a.platform === b.platform;
}

// ---------------------------------------------------------------- router

function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] === "stop" && parts.length === 4) {
    return { name: "stop", platform: parts[1], line: parts[2], sens: parts[3] };
  }
  if (parts[0] === "alerts" || parts[0] === "edit" || parts[0] === "browse") {
    return { name: parts[0] };
  }
  return { name: "home" };
}

async function load() {
  const screen = route();
  const hash = location.hash;
  let answer = null;
  try {
    if (screen.name === "home") {
      answer = await api("/api/board");
    } else if (screen.name === "stop") {
      const path = [screen.platform, screen.line, screen.sens].map(encodeURIComponent);
      answer = await api("/api/stops/" + path.join("/"));
    } else if (screen.name === "alerts") {
      answer = await api("/api/alerts");
    } else if (screen.name === "browse") {
      answer = {}; // the browse screen loads what the user picks, step by step
    } else {
      // The board's cards give the names of the favourites, in the same order.
      const [favourites, board] = await Promise.all([api("/api/favourites"), api("/api/board")]);
      answer = { favourites: favourites, cards: board.cards };
    }
  } catch (error) {
    if (location.hash !== hash) {
      return;
    }
    reachable = false; // keep the last answer, shown as offline
    if (data === null) {
      showError(error.message);
    }
    render();
    return;
  }
  // The user may have changed screen while we waited: this answer is for the old one.
  if (location.hash !== hash) {
    return;
  }
  data = answer;
  if (data.now) {
    clockOffset = parseTime(data.now) - Date.now();
  }
  reachable = true;
  render();
}

function render() {
  const now = serverNow();
  const hour = now.getHours();
  const night = theme === "night" || (theme === "auto" && (hour >= NIGHT_FROM || hour < NIGHT_UNTIL));
  document.body.className = night ? "night" : "";
  if (data === null) {
    return; // still "Chargement..."
  }
  const app = document.getElementById("app");
  const scrolls = location.hash === renderedHash ? scrollPositions(app) : null;
  app.innerHTML = ""; // clearing is fine; data always goes through textContent
  const screen = route();
  if (screen.name === "home") {
    renderHome(app, now);
  } else if (screen.name === "stop") {
    renderStop(app, screen, now);
  } else if (screen.name === "alerts") {
    renderAlerts(app);
  } else if (screen.name === "browse") {
    renderBrowse(app);
  } else {
    renderEdit(app);
  }
  if (scrolls) {
    restoreScrolls(app, scrolls);
  }
  renderedHash = location.hash;
}

// Redrawing empties the page, which scrolls it back to the top: remember where
// the page and its scrolling boxes were, to put them back after the redraw.
const SCROLLERS = ".panel, .stops, .choices, .browse-lines, .alerts";

function scrollPositions(app) {
  const boxes = [];
  app.querySelectorAll(SCROLLERS).forEach((box) => boxes.push(box.scrollTop));
  return { page: window.pageYOffset, boxes: boxes };
}

function restoreScrolls(app, scrolls) {
  app.querySelectorAll(SCROLLERS).forEach((box, i) => {
    box.scrollTop = scrolls.boxes[i] || 0;
  });
  window.scrollTo(0, scrolls.page);
}

// ---------------------------------------------------------------- home

function statusChip(now) {
  if (window.DEMO) {
    const recorded = parseTime(demo.snapshot.now);
    const when = recorded.getDate() + " " + MONTHS[recorded.getMonth()] + " " + clock(recorded);
    const status = el("div", "status demo");
    status.appendChild(el("span", "status-dot"));
    status.appendChild(el("span", "", "D\u00e9mo \u00b7 horaires du " + when));
    return status;
  }
  const offline = data.stale || !reachable;
  const status = el("div", offline ? "status offline" : "status");
  status.appendChild(el("span", "status-dot"));
  let text = "Hors ligne";
  if (data.updated_at) {
    const age = Math.round((now - parseTime(data.updated_at)) / 1000);
    const ago = age < 60 ? age + " s" : Math.floor(age / 60) + " min";
    text = offline ? "Hors ligne \u00b7 donn\u00e9es d'il y a " + ago : "Mis \u00e0 jour il y a " + ago;
  }
  status.appendChild(el("span", "", text));
  return status;
}

function renderHome(app, now) {
  const header = el("header", "header");
  const left = el("div");
  left.appendChild(el("span", "clock", clock(now)));
  const date = DAYS[now.getDay()] + " " + now.getDate() + " " + MONTHS[now.getMonth()];
  left.appendChild(el("span", "date", date));
  header.appendChild(left);
  const right = el("div", "header-right");
  right.appendChild(statusChip(now));
  const themeLabels = { auto: "Th\u00e8me : auto", day: "Th\u00e8me : jour", night: "Th\u00e8me : nuit" };
  const themeButton = button("icon-button", "", nextTheme);
  themeButton.setAttribute("aria-label", themeLabels[theme]);
  themeButton.title = themeLabels[theme];
  themeButton.appendChild(icon({ auto: "auto", day: "sun", night: "moon" }[theme], 26));
  right.appendChild(themeButton);
  if (document.fullscreenEnabled) {
    const full = button("icon-button", "", toggleFullscreen);
    full.setAttribute("aria-label", "Plein \u00e9cran");
    full.appendChild(icon("expand", 26));
    right.appendChild(full);
  }
  const browseButton = button("icon-button", "", () => go("#/browse"));
  browseButton.setAttribute("aria-label", "Parcourir les lignes");
  browseButton.appendChild(icon("map", 26));
  right.appendChild(browseButton);
  const settings = button("icon-button", "", () => go("#/edit"));
  settings.setAttribute("aria-label", "G\u00e9rer mes arr\u00eats");
  settings.appendChild(icon("settings", 26));
  right.appendChild(settings);
  header.appendChild(right);
  app.appendChild(header);

  if (data.banner) {
    const banner = button("banner", "", () => go("#/alerts"));
    banner.appendChild(icon("warning", 22));
    banner.appendChild(lineBadge(data.banner.line, "", 24));
    banner.appendChild(el("span", "banner-title", data.banner.title));
    const count = data.banner.count === 1 ? "1 alerte" : data.banner.count + " alertes";
    banner.appendChild(el("strong", "", count));
    banner.appendChild(icon("right", 20));
    app.appendChild(banner);
  }
  if (data.cards.length === 0) {
    app.appendChild(el("p", "empty", "Aucun arr\u00eat. Ajoutez-en depuis G\u00e9rer mes arr\u00eats."));
    return;
  }
  let className = data.cards.length > 4 ? "cards compact" : "cards";
  if (data.stale || !reachable) {
    className += " offline"; // the mockup greys the countdowns out
  }
  const cards = el("section", className);
  data.cards.forEach((card) => cards.appendChild(renderCard(card, now)));
  app.appendChild(cards);
}

function renderCard(card, now) {
  const node = el("article", "card");
  node.onclick = () => go("#/stop/" + card.platform + "/" + card.line + "/" + card.sens);

  const top = el("div", "card-top");
  top.appendChild(lineBadge(card.line, card.colour, 30));
  top.appendChild(el("span", "stop", card.platform_name));
  if (card.disrupted) {
    top.appendChild(el("span", "pill", "Perturbation"));
  }
  const head = el("div");
  head.appendChild(top);
  head.appendChild(el("div", "destination", "vers " + card.destination));
  node.appendChild(head);

  const upcoming = card.departures.filter((d) => minutesUntil(d, now) >= 0);
  const countdowns = el("div", "countdowns");
  if (upcoming.length === 0) {
    countdowns.appendChild(el("span", "empty", "Pas de d\u00e9part pr\u00e9vu"));
  } else {
    const first = minutesUntil(upcoming[0], now);
    const next = el("div");
    next.appendChild(el("span", "next", first < 1 ? "Proche" : String(first)));
    if (first >= 1) {
      next.appendChild(el("span", "unit", "min"));
    }
    countdowns.appendChild(next);
    const later = el("div", "later");
    if (upcoming.length > 1) {
      later.appendChild(el("div", "", countdown(minutesUntil(upcoming[1], now))));
    }
    if (upcoming.length > 2) {
      const third = "puis " + countdown(minutesUntil(upcoming[2], now));
      later.appendChild(el("div", "later-small", third));
    }
    countdowns.appendChild(later);
  }
  node.appendChild(countdowns);

  const bottom = el("div", "card-bottom");
  upcoming.forEach((d) => bottom.appendChild(departureTime(d)));
  node.appendChild(bottom);
  return node;
}

// ---------------------------------------------------------------- stop detail

function renderStop(app, screen, now) {
  const header = el("header", "header");
  header.appendChild(backButton("Mes arr\u00eats"));
  header.appendChild(lineBadge(data.line, data.colour, 36));
  const title = el("div", "title");
  title.appendChild(el("div", "title-main", data.platform_name));
  title.appendChild(el("div", "destination", "vers " + data.destination));
  header.appendChild(title);
  const here = { line: screen.line, sens: screen.sens, platform: screen.platform };
  const star = button("chip with-icon", "", () => toggleFavourite(here, !data.favourite));
  const starIcon = icon("star", 22);
  starIcon.setAttribute("stroke", data.colour);
  starIcon.setAttribute("fill", data.favourite ? data.colour : "none");
  star.appendChild(starIcon);
  star.appendChild(el("span", "", data.favourite ? "Dans mes arr\u00eats" : "Ajouter \u00e0 mes arr\u00eats"));
  header.appendChild(star);
  app.appendChild(header);

  const body = el("div", "columns");
  const left = el("section", "panel wide");
  const leftHead = el("div", "panel-head");
  leftHead.appendChild(el("h2", "", "Prochains d\u00e9parts"));
  const offline = data.stale || !reachable;
  if (offline) {
    leftHead.appendChild(withIcon("source offline-text", "clock", "Hors ligne"));
  }
  left.appendChild(leftHead);
  const upcoming = upcomingOf(now);
  if (upcoming.length === 0) {
    left.appendChild(el("p", "empty", "Pas de d\u00e9part pr\u00e9vu"));
  }
  upcoming.forEach((d, i) => {
    const row = el("div", i === 0 ? "row first" : "row");
    row.appendChild(el("span", "", countdown(minutesUntil(d, now))));
    row.appendChild(departureTime(d));
    left.appendChild(row);
  });
  body.appendChild(left);

  const right = el("section", "panel");
  right.appendChild(el("h2", "", "Arr\u00eats suivants"));
  const list = el("ol", "timeline");
  list.style.borderColor = data.colour;
  data.next_stops.forEach((name, i) => {
    const item = el("li", i === 0 ? "current" : "", name);
    item.style.borderColor = data.colour;
    list.appendChild(item);
  });
  right.appendChild(list);
  if (data.remaining > 0) {
    right.appendChild(el("p", "muted", "+ " + data.remaining + " arr\u00eats jusqu'\u00e0 " + data.destination));
  } else if (data.next_stops.length === 1) {
    right.appendChild(el("p", "muted", "Terminus de la ligne."));
  }
  body.appendChild(right);
  app.appendChild(body);
}

function upcomingOf(now) {
  return data.departures.filter((d) => minutesUntil(d, now) >= 0);
}

async function toggleFavourite(here, add) {
  try {
    const favourites = await api("/api/favourites");
    const kept = favourites.filter((f) => !sameFavourite(f, here));
    await putFavourites(add ? kept.concat([here]) : kept);
    await load();
  } catch (error) {
    showError(error.message);
  }
}

// ---------------------------------------------------------------- alerts

let alertsTab = "mine";
const openAlerts = {}; // alerts unfolded by a tap, by line and title

function renderAlerts(app) {
  const header = el("header", "header");
  header.appendChild(backButton("Mes arr\u00eats"));
  header.appendChild(el("h1", "title-main grow", "Alertes trafic"));
  const tabs = el("div", "tabs");
  [["mine", "Mes lignes", data.mine], ["network", "Tout le r\u00e9seau", data.network]].forEach(
    ([tab, label, alerts]) => {
      const node = button(tab === alertsTab ? "tab on" : "tab", label + " \u00b7 " + alerts.length, () => {
        alertsTab = tab;
        render();
      });
      tabs.appendChild(node);
    }
  );
  header.appendChild(tabs);
  app.appendChild(header);

  const list = el("div", "alerts");
  const alerts = alertsTab === "mine" ? data.mine : data.network;
  if (alerts.length === 0) {
    list.appendChild(el("p", "empty", "Aucune alerte."));
  }
  alerts.forEach((alert) => {
    const key = alert.line + "|" + alert.title;
    const item = el("article", openAlerts[key] ? "panel alert open" : "panel alert");
    item.onclick = () => {
      openAlerts[key] = !openAlerts[key];
      render();
    };
    const badge = el("div", "alert-line");
    badge.appendChild(lineBadge(alert.line, "", 32));
    item.appendChild(badge);
    const text = el("div", "grow");
    const meta = el("div", "meta");
    const pill = el("span", alert.kind === "Perturbation" ? "pill" : "pill info", alert.kind);
    meta.appendChild(pill);
    const period = "Du " + shortDate(parseTime(alert.start)) + " au " + shortDate(parseTime(alert.end));
    meta.appendChild(el("span", "muted", period));
    text.appendChild(meta);
    text.appendChild(el("h2", "", alert.title));
    text.appendChild(el("p", "message", alert.message));
    item.appendChild(text);
    list.appendChild(item);
  });
  app.appendChild(list);
  app.appendChild(el("p", "muted", "Source : SYTRAL Mobilit\u00e9s - data.grandlyon.com"));
}

// ---------------------------------------------------------------- edit

// What the user has picked so far in "Ajouter un arret".
const pick = { mode: null, lines: [], line: null, sens: null, stops: [], platform: null };
let editError = "";

function renderEdit(app) {
  const header = el("header", "header");
  header.appendChild(backButton("Termin\u00e9"));
  header.appendChild(el("h1", "title-main grow", "G\u00e9rer mes arr\u00eats"));
  app.appendChild(header);

  const body = el("div", "columns");
  body.appendChild(renderFavouriteList());
  body.appendChild(renderAddStop());
  app.appendChild(body);
  if (editError) {
    app.appendChild(el("p", "error", editError));
  }
}

function iconButton(name, label, onclick) {
  const node = button("icon", "", onclick);
  node.setAttribute("aria-label", label);
  node.appendChild(icon(name, 20));
  return node;
}

function renderFavouriteList() {
  const favourites = data.favourites;
  const panel = el("section", "panel favourites");
  const head = el("div", "panel-head");
  head.appendChild(el("h2", "", "Sur l'accueil"));
  head.appendChild(el("span", "muted", favourites.length + " / 6"));
  panel.appendChild(head);
  favourites.forEach((f, i) => {
    const card = data.cards[i];
    const row = el("div", "fav");
    row.appendChild(lineBadge(card.line, card.colour, 26));
    const text = el("div", "grow");
    text.appendChild(el("div", "fav-stop", card.platform_name));
    text.appendChild(el("div", "muted", "vers " + card.destination));
    row.appendChild(text);
    if (i > 0) {
      row.appendChild(iconButton("up", "Monter", () => {
        const moved = favourites.slice();
        moved.splice(i - 1, 0, moved.splice(i, 1)[0]);
        saveFavourites(moved);
      }));
    }
    row.appendChild(iconButton("close", "Retirer", () => saveFavourites(favourites.filter((_, j) => j !== i))));
    panel.appendChild(row);
  });
  panel.appendChild(el("p", "muted", "Jusqu'\u00e0 6 arr\u00eats. L'ordre ici est celui de l'accueil."));
  return panel;
}

function renderAddStop() {
  const panel = el("section", "panel wide");
  panel.appendChild(el("h2", "", "Ajouter un arr\u00eat"));

  panel.appendChild(el("div", "step", "Mode"));
  const modes = el("div", "choices");
  MODES.forEach(([mode, label]) => {
    modes.appendChild(button(pick.mode === mode ? "choice on" : "choice", label, () => chooseMode(mode)));
  });
  panel.appendChild(modes);

  if (pick.mode) {
    panel.appendChild(el("div", "step", "Ligne"));
    const lines = el("div", "choices wrap");
    pick.lines.forEach((line) => {
      const node = button(pick.line === line ? "choice on" : "choice", "", () => chooseLine(line));
      node.appendChild(lineBadge(line.code, line.colour, 26));
      lines.appendChild(node);
    });
    panel.appendChild(lines);
  }

  if (pick.sens) {
    panel.appendChild(el("div", "step", "Direction"));
    panel.appendChild(directionButton(pick.line, pick.sens, chooseSens));
  }

  if (pick.sens) {
    panel.appendChild(el("div", "step", "Arr\u00eat"));
    const stops = el("div", "stops");
    const onHome = data.favourites.filter((f) => f.line === pick.line.code && f.sens === pick.sens);
    pick.stops.forEach((stop) => {
      const already = onHome.some((f) => f.platform === stop.platform);
      const className = stop.platform === pick.platform ? "stop-row on" : "stop-row";
      const row = button(className, "", () => {
        pick.platform = stop.platform;
        render();
      });
      row.appendChild(el("span", "", stop.name));
      row.appendChild(el("span", "muted", already ? "d\u00e9j\u00e0 sur l'accueil" : ""));
      stops.appendChild(row);
    });
    panel.appendChild(stops);
  }

  if (pick.platform) {
    const chosen = pick.stops.filter((s) => s.platform === pick.platform)[0];
    if (data.favourites.length >= 6) {
      panel.appendChild(el("p", "add disabled", "6 arr\u00eats maximum : retirez-en un pour ajouter " + chosen.name));
    } else {
      panel.appendChild(button("add", "Ajouter " + chosen.name, addFavourite));
    }
  }
  return panel;
}

async function chooseMode(mode) {
  Object.assign(pick, { mode: mode, lines: [], line: null, sens: null, stops: [], platform: null });
  pick.lines = await api("/api/lines?mode=" + mode);
  render();
}

function chooseLine(line) {
  Object.assign(pick, { line: line, sens: null, stops: [], platform: null });
  chooseSens(Object.keys(line.destinations).sort()[0]);
}

async function chooseSens(sens) {
  Object.assign(pick, { sens: sens, stops: [], platform: null });
  pick.stops = await api("/api/lines/" + encodeURIComponent(pick.line.code) + "/" + sens + "/stops");
  render();
}

function addFavourite() {
  const here = { line: pick.line.code, sens: pick.sens, platform: pick.platform };
  const kept = data.favourites.filter((f) => !sameFavourite(f, here));
  saveFavourites(kept.concat([here]));
}

async function saveFavourites(favourites) {
  try {
    await putFavourites(favourites);
    editError = "";
    pick.platform = null;
    await load();
  } catch (error) {
    editError = "Impossible d'enregistrer ce changement (" + error.message + ").";
    render();
  }
}

// ---------------------------------------------------------------- browse

// What the user has picked on the browse screen, kept across redraws.
const browse = {
  mode: null, lines: [], line: null, sens: null, map: null, platform: null, detail: null,
};
let leafletLoading = null; // a Promise, so Leaflet is loaded only once
let browseMap = null; // the Leaflet map currently on screen

function loadLeaflet() {
  if (leafletLoading === null) {
    leafletLoading = new Promise((resolve, reject) => {
      const css = el("link");
      css.rel = "stylesheet";
      css.href = LEAFLET + "leaflet.min.css";
      document.head.appendChild(css);
      const script = el("script");
      script.src = LEAFLET + "leaflet.min.js";
      script.onload = resolve;
      script.onerror = () => reject(new Error("Leaflet: pas d'acc\u00e8s internet"));
      document.head.appendChild(script);
    });
  }
  return leafletLoading;
}

function renderBrowse(app) {
  const header = el("header", "header");
  header.appendChild(backButton("Mes arr\u00eats"));
  header.appendChild(el("h1", "title-main grow", "Parcourir les lignes"));
  app.appendChild(header);

  const body = el("div", "columns");
  const left = el("section", "panel");
  const modes = el("div", "choices");
  MODES.forEach(([mode, label]) => {
    modes.appendChild(button(browse.mode === mode ? "choice on" : "choice", label, () => browseMode(mode)));
  });
  left.appendChild(modes);
  if (browse.mode) {
    const lines = el("div", "choices wrap browse-lines");
    browse.lines.forEach((line) => {
      const node = button(browse.line === line ? "choice on" : "choice", "", () => browseLine(line));
      node.appendChild(lineBadge(line.code, line.colour, 26));
      lines.appendChild(node);
    });
    left.appendChild(lines);
  }
  if (browse.sens) {
    left.appendChild(directionButton(browse.line, browse.sens, browseSens));
  }
  if (browse.map) {
    const stops = el("ol", "timeline browse-stops");
    browse.map.stops.forEach((stop) => {
      const item = el("li", stop.platform === browse.platform ? "current" : "");
      item.style.borderColor = browse.map.colour;
      item.appendChild(button("stop-link", stop.name, () => browseStop(stop.platform)));
      stops.appendChild(item);
    });
    left.appendChild(stops);
  }
  body.appendChild(left);

  const right = el("section", "panel wide browse-right");
  const mapBox = el("div", "browse-map");
  right.appendChild(mapBox);
  right.appendChild(renderBrowseDetail());
  body.appendChild(right);
  app.appendChild(body);

  if (browse.map) {
    drawMap(mapBox);
  } else {
    mapBox.appendChild(el("p", "map-hint", "Choisissez un mode, puis une ligne."));
  }
}

function renderBrowseDetail() {
  const box = el("div", "browse-detail");
  if (!browse.platform) {
    if (browse.map) {
      box.appendChild(el("p", "muted", "Touchez un arr\u00eat pour voir ses prochains d\u00e9parts."));
    }
    return box;
  }
  const stop = browse.map.stops.filter((s) => s.platform === browse.platform)[0];
  const head = el("div", "browse-head");
  head.appendChild(lineBadge(browse.line.code, browse.line.colour, 28));
  const title = el("div", "grow");
  title.appendChild(el("div", "fav-stop", stop.name));
  title.appendChild(el("div", "muted", "vers " + browse.line.destinations[browse.sens]));
  head.appendChild(title);
  const open = "#/stop/" + browse.platform + "/" + browse.line.code + "/" + browse.sens;
  const openButton = button("chip with-icon", "", () => go(open));
  openButton.appendChild(el("span", "", "Voir l'arr\u00eat"));
  openButton.appendChild(icon("right", 20));
  head.appendChild(openButton);
  box.appendChild(head);

  if (browse.detail === null) {
    box.appendChild(el("p", "muted", "Chargement..."));
    return box;
  }
  if (browse.detail === "error") {
    box.appendChild(el("p", "muted", "Pas de d\u00e9parts pour cet arr\u00eat."));
    return box;
  }
  const now = serverNow();
  const upcoming = browse.detail.departures.filter((d) => minutesUntil(d, now) >= 0).slice(0, 3);
  if (upcoming.length === 0) {
    box.appendChild(el("p", "muted", "Pas de d\u00e9part pr\u00e9vu"));
    return box;
  }
  const tiles = el("div", "tiles");
  upcoming.forEach((d) => {
    const tile = el("div", "tile");
    tile.style.borderLeftColor = browse.line.colour;
    tile.appendChild(el("div", "tile-wait", countdown(minutesUntil(d, now))));
    tile.appendChild(departureTime(d));
    tiles.appendChild(tile);
  });
  box.appendChild(tiles);
  return box;
}

async function drawMap(box) {
  try {
    await loadLeaflet();
  } catch (error) {
    box.appendChild(el("p", "map-hint", error.message));
    return;
  }
  if (!box.isConnected) {
    return; // the screen was redrawn meanwhile
  }
  if (browseMap !== null) {
    browseMap.remove(); // free the previous map
  }
  const L = window.L;
  browseMap = L.map(box);
  L.tileLayer(TILES, { maxZoom: 18, attribution: "\u00a9 OpenStreetMap" }).addTo(browseMap);
  const colour = browse.map.colour;
  const trace = L.polyline(browse.map.trace, { color: colour, weight: 5 }).addTo(browseMap);
  browse.map.stops.forEach((stop) => {
    const selected = stop.platform === browse.platform;
    const marker = L.circleMarker([stop.lat, stop.lon], {
      radius: selected ? 9 : 5,
      color: colour,
      weight: 3,
      fillColor: selected ? colour : "#FFFFFF",
      fillOpacity: 1,
    }).addTo(browseMap);
    marker.bindTooltip(stop.name);
    marker.on("click", () => browseStop(stop.platform));
  });
  const stop = browse.map.stops.filter((s) => s.platform === browse.platform)[0];
  if (stop) {
    browseMap.setView([stop.lat, stop.lon], 15);
  } else if (browse.map.trace.length > 0) {
    browseMap.fitBounds(trace.getBounds(), { padding: [20, 20] });
  }
}

async function browseMode(mode) {
  Object.assign(browse, { mode: mode, lines: [], line: null, sens: null, map: null, platform: null });
  render();
  browse.lines = await api("/api/lines?mode=" + mode);
  render();
}

function browseLine(line) {
  Object.assign(browse, { line: line, sens: null, map: null, platform: null });
  browseSens(Object.keys(line.destinations).sort()[0]);
}

async function browseSens(sens) {
  Object.assign(browse, { sens: sens, map: null, platform: null });
  render();
  try {
    browse.map = await api("/api/lines/" + encodeURIComponent(browse.line.code) + "/" + sens + "/map");
  } catch (error) {
    browse.map = { colour: browse.line.colour, trace: [], stops: [] };
  }
  render();
}

async function browseStop(platform) {
  Object.assign(browse, { platform: platform, detail: null });
  render();
  try {
    const path = [platform, browse.line.code, browse.sens].map(encodeURIComponent).join("/");
    const detail = await api("/api/stops/" + path);
    clockOffset = parseTime(detail.now) - Date.now();
    browse.detail = detail;
  } catch (error) {
    browse.detail = "error";
  }
  render();
}

// ---------------------------------------------------------------- start

fitToScreen();
window.addEventListener("resize", fitToScreen);

window.onhashchange = () => {
  data = null;
  editError = "";
  document.getElementById("app").textContent = "Chargement...";
  load();
};

load();
// Not on the edit and browse screens: redrawing would reset the user's choices.
const interactive = () => route().name === "edit" || route().name === "browse";
setInterval(() => {
  if (!interactive()) {
    load();
  }
}, REFRESH_MS);
setInterval(() => {
  if (!interactive()) {
    render();
  }
}, TICK_MS);
