/* Storyboard player.
 *
 * Data in: window.STORYBOARD = { title, episodes: [...] } — see MODEL.md.
 * Everything below is generic: no episode, plate or palette is hard-coded.
 */
(function () {
  "use strict";

  var SB = window.STORYBOARD || { title: "Storyboard", episodes: [] };
  var EPISODES = SB.episodes || [];
  if (!EPISODES.length) return;

  var css = getComputedStyle(document.documentElement);
  var C = {
    accent: css.getPropertyValue("--accent").trim() || "#C51A4A",
    signal: css.getPropertyValue("--signal").trim() || "#7BB02A",
    alarm: css.getPropertyValue("--alarm").trim() || "#E0563D",
    line: css.getPropertyValue("--line").trim() || "#3A3242",
    dim: css.getPropertyValue("--dimmer").trim() || "#6E6678",
    plate: css.getPropertyValue("--plate").trim() || "#0E0B12"
  };

  /* ══════════════════════════ glyphs ══════════════════════════
     Generic marks, drawn in a 200×130 box. A plate picks one by name;
     unknown names fall back to `spark`. */
  var GLYPHS = {
    spark: '<path d="M100 18 L112 62 L156 74 L112 86 L100 130 L88 86 L44 74 L88 62 Z" fill="' + C.accent + '"/>',
    key: '<circle cx="62" cy="65" r="26" fill="none" stroke="' + C.signal + '" stroke-width="8"/>' +
         '<path d="M88 65 H170 M150 65 v22 M132 65 v16" stroke="' + C.signal + '" stroke-width="8" stroke-linecap="round"/>',
    cloud: '<path d="M60 92 a26 26 0 0 1 2 -52 a34 34 0 0 1 64 -6 a24 24 0 0 1 12 58 Z" fill="none" stroke="' + C.accent + '" stroke-width="7" stroke-linejoin="round"/>' +
           '<path d="M100 96 v26 M86 110 l14 14 l14 -14" stroke="' + C.dim + '" stroke-width="6" fill="none" stroke-linecap="round"/>',
    chip: '<rect x="56" y="34" width="88" height="70" rx="8" fill="none" stroke="' + C.signal + '" stroke-width="7"/>' +
          '<rect x="82" y="60" width="36" height="20" rx="3" fill="' + C.signal + '"/>' +
          '<g stroke="' + C.dim + '" stroke-width="6" stroke-linecap="round">' +
          '<path d="M74 34 V18 M100 34 V18 M126 34 V18 M74 104 V120 M100 104 V120 M126 104 V120"/>' +
          '<path d="M56 54 H38 M56 84 H38 M144 54 H162 M144 84 H162"/></g>',
    box: '<path d="M100 20 L166 52 V98 L100 130 L34 98 V52 Z" fill="none" stroke="' + C.accent + '" stroke-width="7" stroke-linejoin="round"/>' +
         '<path d="M34 52 L100 84 L166 52 M100 84 V130" stroke="' + C.dim + '" stroke-width="5" fill="none"/>',
    arrow: '<path d="M26 75 H150" stroke="' + C.accent + '" stroke-width="10" stroke-linecap="round"/>' +
           '<path d="M136 52 L172 75 L136 98 Z" fill="' + C.accent + '"/>' +
           '<rect x="18" y="40" width="10" height="70" rx="4" fill="' + C.dim + '"/>',
    check: '<circle cx="100" cy="72" r="48" fill="none" stroke="' + C.signal + '" stroke-width="8"/>' +
           '<path d="M76 72 l18 20 l32 -40" stroke="' + C.signal + '" stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    alert: '<path d="M100 20 L172 120 H28 Z" fill="none" stroke="' + C.alarm + '" stroke-width="8" stroke-linejoin="round"/>' +
           '<path d="M100 56 v34" stroke="' + C.alarm + '" stroke-width="9" stroke-linecap="round"/>' +
           '<circle cx="100" cy="104" r="5.5" fill="' + C.alarm + '"/>',
    doc: '<path d="M56 16 h64 l28 28 v82 a6 6 0 0 1 -6 6 H56 a6 6 0 0 1 -6 -6 V22 a6 6 0 0 1 6 -6 z" fill="none" stroke="' + C.dim + '" stroke-width="7"/>' +
         '<path d="M118 16 v30 h30" stroke="' + C.dim + '" stroke-width="7" fill="none"/>' +
         '<g stroke="' + C.accent + '" stroke-width="6" stroke-linecap="round"><path d="M68 70 h60 M68 90 h60 M68 110 h34"/></g>'
  };

  function glyph(name) { return GLYPHS[name] || GLYPHS.spark; }

  /* ══════════════════════════ dom helpers ══════════════════════════ */

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function bg(fill) {
    return '<svg class="bg" viewBox="0 0 360 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' +
           '<rect width="360" height="640" fill="' + (fill || C.plate) + '"/></svg>';
  }
  function tc(s) {
    var m = Math.floor(s / 60), r = Math.floor(s % 60);
    return m + ":" + (r < 10 ? "0" : "") + r;
  }
  function clamp01(x) { return Math.max(0, Math.min(1, x)); }

  /* reveal a typed terminal script by progress 0..1 */
  function typeScript(script, p) {
    if (!script || !script.length) return "";
    var w = script.map(function (l) { return l[1] === "o" ? 7 : Math.max(4, l[0].length); });
    var total = w.reduce(function (a, b) { return a + b; }, 0) || 1;
    var seen = p * total, acc = 0, out = "";
    for (var i = 0; i < script.length; i++) {
      var line = script[i][0], kind = script[i][1];
      if (seen <= acc) break;
      var got = seen - acc;
      if (kind === "o") {
        out += line + "\n";
      } else {
        var n = Math.min(line.length, Math.round(got));
        out += line.slice(0, n);
        if (n < line.length) return out;
        if (kind !== "k") out += "\n";
      }
      acc += w[i];
    }
    return out;
  }

  function reveal(str, p, a, b) {
    if (p <= a) return "";
    return str.slice(0, Math.round(clamp01((p - a) / (b - a)) * str.length));
  }

  /* ══════════════════════════ plate builders ══════════════════════════
     Each returns { el, update(progress, time) }. Progress is 0..1 across
     the shot; time is the episode clock, for blinks and ticks. */

  var BUILD = {

    term: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0E0B12");
      var wrap = el("div", "term-wrap");
      var a = el("div", "term" + (spec.split ? " split" : ""));
      wrap.appendChild(a);
      var b = null;
      if (spec.split) {
        b = el("div", "term split");
        wrap.appendChild(b);
        a.appendChild(el("div", "term-head", spec.headL || ""));
        b.appendChild(el("div", "term-head", spec.headR || ""));
      }
      root.appendChild(wrap);
      var outA = el("span"), outB = el("span");
      a.appendChild(outA); if (b) b.appendChild(outB);
      var carA = el("i", "caret"), carB = el("i", "caret");
      a.appendChild(carA); if (b) b.appendChild(carB);

      return { el: root, update: function (p, t) {
        outA.textContent = typeScript(spec.script, p);
        if (b) outB.textContent = typeScript(spec.script2 || spec.script, p);
        var blink = Math.floor(t * 2) % 2 ? "1" : "0";
        carA.style.opacity = blink; carB.style.opacity = blink;
      } };
    },

    file: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0E0B12");
      var box = el("div", "file");
      box.appendChild(el("div", "file-name", spec.name || "file"));
      var body = el("div", "file-body");
      var lines = (spec.lines || []).map(function (L) {
        var ln = el("div", "ln");
        ln.textContent = Array.isArray(L) ? L[0] : String(L);
        ln.dataset.hi = (Array.isArray(L) && L[1]) ? "1" : "";
        body.appendChild(ln);
        return ln;
      });
      box.appendChild(body);
      if (spec.note) box.appendChild(el("div", "file-note", spec.note));
      root.appendChild(box);

      return { el: root, update: function (p) {
        var shown = Math.ceil(p * 2.4 * lines.length);
        lines.forEach(function (ln, i) {
          ln.style.opacity = i < shown ? "1" : "0.12";
          ln.classList.toggle("hi", !!ln.dataset.hi && p > 0.45);
        });
      } };
    },

    card: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0B090D");
      var wrap = el("div", "card-plate");
      var g = el("div", "card-glyph");
      g.innerHTML = '<svg viewBox="0 0 200 130" aria-hidden="true" style="width:100%;height:100%">' +
                    glyph(spec.glyph) + "</svg>";
      wrap.appendChild(g);
      var line = el("p", "card-line");
      line.textContent = spec.line || "";
      wrap.appendChild(line);
      root.appendChild(wrap);

      return { el: root, update: function (p) {
        var s = 0.94 + Math.min(1, p * 4) * 0.06;
        g.style.transform = "scale(" + s.toFixed(3) + ")";
        g.style.opacity = Math.min(1, p * 5).toFixed(2);
        line.style.opacity = clamp01((p - 0.12) * 4).toFixed(2);
      } };
    },

    head: function () {
      var root = el("div", "plate");
      root.innerHTML = '<svg class="bg" viewBox="0 0 360 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' +
        '<rect width="360" height="640" fill="#141019"/><circle cx="270" cy="120" r="150" fill="#1B1524"/></svg>';
      var holder = el("div");
      holder.innerHTML = '<svg class="head-fig" viewBox="0 0 200 220" aria-hidden="true">' +
        '<circle cx="100" cy="66" r="46" fill="#2E2735"/>' +
        '<path d="M12 220 C 18 148, 60 116, 100 116 C 140 116, 182 148, 188 220 Z" fill="#262030"/>' +
        '<path d="M100 116 L100 220" stroke="#1B1524" stroke-width="3"/></svg>';
      root.appendChild(holder.firstChild);
      return { el: root, update: function (p) { root.style.setProperty("--p", p.toFixed(3)); } };
    },

    /* Abstract b-roll: a mark, the shot's own words, and a slow drift so the
       frame is never dead while you are judging timing. */
    scene: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0B090D");
      var holder = el("div", "scene");
      var hatch = el("div", "hatch");
      hatch.innerHTML = '<svg viewBox="0 0 360 640" preserveAspectRatio="none" style="width:100%;height:100%" aria-hidden="true">' +
        '<defs><pattern id="h' + (spec.uid || Math.random().toString(36).slice(2)) +
        '" width="18" height="18" patternTransform="rotate(35)" patternUnits="userSpaceOnUse">' +
        '<line x1="0" y1="0" x2="0" y2="18" stroke="' + C.line + '" stroke-width="2"/></pattern></defs>' +
        '<rect width="360" height="640" fill="url(#h' + (spec.uid || "") + ')" opacity="0.35"/></svg>';
      holder.appendChild(hatch);
      var g = el("div", "glyph");
      g.innerHTML = '<svg viewBox="0 0 200 130" aria-hidden="true" style="width:100%;height:100%">' +
                    glyph(spec.glyph) + "</svg>";
      holder.appendChild(g);
      holder.appendChild(el("span", "kind", spec.kind || "b-roll"));
      var label = el("p", "label");
      label.textContent = spec.label || "";
      holder.appendChild(label);
      root.appendChild(holder);

      return { el: root, update: function (p) {
        g.style.setProperty("--k", (1 + p * 0.06).toFixed(3));
        g.style.setProperty("--dy", (-p * 1.4).toFixed(2) + "cqh");
        label.style.opacity = clamp01(p * 6).toFixed(2);
      } };
    },

    wait: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0B090D");
      var w = el("div", "wait-plate");
      var inner = el("div", "wait-inner");
      inner.appendChild(el("span", "eyebrow", spec.eyebrow || "elapsed · not faked"));
      var clock = el("div", "wait-clock", "0:00");
      inner.appendChild(clock);
      var stamps = el("div", "wait-stamps");
      var led = null;
      if (spec.label2) {
        stamps.innerHTML = "<span><b>" + spec.label + "</b></span><span>↓</span><span><b>" + spec.label2 + "</b></span>";
      } else {
        if (spec.label) stamps.appendChild(el("span", "", spec.label));
        led = el("i", "led");
        stamps.appendChild(led);
      }
      inner.appendChild(stamps);
      w.appendChild(inner);
      root.appendChild(w);

      return { el: root, update: function (p, t) {
        var s = Math.floor(p * (spec.to || 60));
        clock.textContent = Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
        if (led) led.style.opacity = Math.floor(t * 4) % 2 ? "1" : "0.2";
      } };
    },

    /* A window with rows that resolve as the shot plays — dashboards, lists,
       settings panes, node tables. rows: [label, endState, startState?] */
    app: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0E0B12");
      var app = el("div", "app");
      var rows = (spec.rows || []).map(function (r, i) {
        var label = Array.isArray(r) ? r[0] : String(r);
        return '<div class="row" data-row><span>' + label + '</span><span class="pill off" data-pill></span></div>';
      }).join("");
      app.innerHTML =
        '<div class="app-bar"><i class="dot"></i><i class="dot"></i><i class="dot"></i><b>' +
        (spec.title || "") + "</b></div>" +
        '<div class="app-body">' + rows + "</div>";
      if (spec.note) app.querySelector(".app-body").appendChild(el("div", "file-note", spec.note));
      root.appendChild(app);
      var rowEls = [].slice.call(app.querySelectorAll("[data-row]"));
      var flip = typeof spec.flip === "number" ? spec.flip : 0.45;

      function state(name) {
        if (/fail|error|down|offline|red|bad|killed/i.test(name)) return "bad";
        if (/wait|pending|warn|amber|partial/i.test(name)) return "warn";
        if (/off|idle|—|-/i.test(name)) return "off";
        return "on";
      }

      return { el: root, update: function (p) {
        rowEls.forEach(function (r, i) {
          var spec_r = spec.rows[i] || [];
          var endTxt = (Array.isArray(spec_r) ? spec_r[1] : "") || "ready";
          var startTxt = (Array.isArray(spec_r) ? spec_r[2] : "") || "—";
          var when = flip * (0.55 + 0.45 * (i + 1) / rowEls.length);
          var done = p > when;
          r.style.opacity = p > when * 0.5 ? "1" : "0.15";
          var pill = r.querySelector("[data-pill]");
          pill.className = "pill " + (done ? state(endTxt) : state(startTxt));
          pill.textContent = done ? endTxt : startTxt;
        });
      } };
    },

    progress: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0E0B12");
      var app = el("div", "app");
      app.style.top = "28cqh";
      app.innerHTML =
        '<div class="app-bar"><i class="dot"></i><i class="dot"></i><i class="dot"></i><b>' +
        (spec.title || "working…") + "</b></div>" +
        '<div class="app-body"><div class="bar-track"><i class="bar-fill" data-bar></i></div>' +
        '<div class="bar-meta"><span data-pct>0%</span><span data-stage></span></div></div>';
      root.appendChild(app);
      var bar = app.querySelector("[data-bar]"), pct = app.querySelector("[data-pct]"),
          stage = app.querySelector("[data-stage]");
      var stages = spec.stages && spec.stages.length ? spec.stages : ["running", "verifying", "done"];

      return { el: root, update: function (p) {
        var wr = Math.min(1, p / 0.82);
        bar.style.width = (wr * 100).toFixed(1) + "%";
        pct.textContent = Math.round(wr * 100) + "%";
        // the first stage lasts as long as the bar is filling
        var idx = wr < 1 ? 0 : 1 + Math.floor((p - 0.82) / 0.18 * (stages.length - 1));
        stage.textContent = stages[Math.max(0, Math.min(stages.length - 1, idx))];
      } };
    },

    chat: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0E0B12");
      var app = el("div", "app");
      app.innerHTML = '<div class="app-bar"><i class="dot"></i><i class="dot"></i><i class="dot"></i><b>' +
                      (spec.title || "chat") + '</b></div><div class="app-body" data-body></div>';
      root.appendChild(app);
      if (spec.badge) root.appendChild(el("div", "badge", spec.badge));
      var body = app.querySelector("[data-body]");
      var you = el("div", "msg you"), bot = el("div", "msg bot");
      body.appendChild(you); body.appendChild(bot);
      var q = spec.q || "", a = spec.a || "";
      var thinkTo = typeof spec.think === "number" ? spec.think : 0.42;

      return { el: root, update: function (p, t) {
        you.textContent = reveal(q, p, 0.0, 0.28);
        you.style.opacity = p > 0.01 ? "1" : "0";
        if (p < thinkTo * 0.72) { bot.style.opacity = "0"; return; }
        bot.style.opacity = "1";
        if (p < thinkTo) {
          bot.className = "msg bot thinking";
          bot.textContent = "thinking" + ".".repeat(1 + Math.floor(t * 2) % 3);
        } else {
          bot.className = "msg bot";
          bot.textContent = reveal(a, p, thinkTo, Math.min(0.98, thinkTo + 0.5));
        }
      } };
    },

    /* Narration from a transcript: the words land on the clock, so you can
       see whether the script actually fits the time you have. */
    text: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0B090D");
      var wrap = el("div", "text-plate");
      if (spec.eyebrow) wrap.appendChild(el("span", "eyebrow", spec.eyebrow));
      var body = el("p", "text-body");
      wrap.appendChild(body);
      root.appendChild(wrap);
      var words = String(spec.text || "").split(/\s+/);

      return { el: root, update: function (p) {
        var n = Math.min(words.length, Math.round(clamp01(p * 1.08) * words.length));
        body.textContent = words.slice(0, n).join(" ");
      } };
    },

    /* Once a still or a frame grab exists, drop it straight in. */
    image: function (spec) {
      var root = el("div", "plate");
      root.innerHTML = bg("#0B090D");
      var img = document.createElement("img");
      img.className = "shotimg";
      img.alt = spec.caption || "";
      img.src = spec.src || "";
      if (spec.fit) img.style.objectFit = spec.fit;
      img.addEventListener("error", function () {
        img.remove();
        root.appendChild(el("div", "imgfail", "missing plate image<br>" + (spec.src || "")));
      });
      root.appendChild(img);
      return { el: root, update: function (p) {
        img.style.transform = "scale(" + (1.02 + p * 0.04).toFixed(3) + ")";
      } };
    }
  };

  /* ══════════════════════════ chrome ══════════════════════════ */

  var $ = function (id) { return document.getElementById(id); };
  var platesHost = $("plates"), mlabel = $("mlabel"), lthird = $("lthird"),
      caption = $("caption"), endcard = $("endcard"), ecBig = $("ec-big"),
      ecEyebrow = $("ec-eyebrow"), ecUrl = $("ec-url"), sting = $("sting");
  var elPlay = $("play"), elBack = $("back"), elRate = $("rate"),
      elGuideBtn = $("guidebtn"), elGuides = $("guides"), elScrub = $("scrub"),
      elHead = $("playhead"), elTc = $("tcnow"), elTot = $("tctot"),
      elBeatNow = $("beatnow"), elSegs = $("segs"), elTicks = $("ticks"),
      elBeatList = $("beatlist"), elShotList = $("shotlist"),
      elAssets = $("assetlist"), elAssetSec = $("assetsec"),
      elBeatCount = $("beatcount"), elShotCount = $("shotcount"),
      elNpTitle = $("np-title"), elNpMoment = $("np-moment"),
      elMomentWrap = $("np-moment-wrap");

  var ep = null, plateObjs = [], beatBtns = [], shotBtns = [], segEls = [], live = -1;
  var time = 0, playing = false, rate = 1, last = 0, epIndex = 0;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var epBtns = EPISODES.map(function (E, i) {
    var b = el("button", "ep" + (E.bonus ? " bonus" : ""));
    b.setAttribute("role", "tab");
    b.innerHTML = '<span class="code"></span><span class="ch"></span>';
    b.querySelector(".code").textContent = E.code || E.title || ("#" + (i + 1));
    b.querySelector(".ch").textContent = E.chapter || (E.code ? E.title : "");
    b.addEventListener("click", function () { loadEpisode(i); });
    $("eps").appendChild(b);
    return b;
  });
  if (EPISODES.length < 2) $("eps").hidden = true;

  function loadEpisode(i) {
    epIndex = i;
    ep = EPISODES[i];
    epBtns.forEach(function (b, j) { b.setAttribute("aria-selected", String(j === i)); });

    elNpTitle.textContent = [ep.code, ep.title].filter(Boolean).join(" — ");
    elMomentWrap.hidden = !ep.moment;
    elNpMoment.textContent = ep.moment || "";
    var card = ep.endcard || {};
    ecBig.innerHTML = card.line || "";
    ecEyebrow.textContent = card.eyebrow || "";
    ecUrl.textContent = card.url || "";
    ecUrl.hidden = !card.url;
    elTot.textContent = " / " + tc(ep.dur);
    elScrub.setAttribute("aria-valuemax", String(ep.dur));
    elBeatCount.textContent = ep.beats.length + " beats";
    elShotCount.textContent = ep.shots.length + " shots · click to seek";

    platesHost.innerHTML = "";
    plateObjs = ep.shots.map(function (s, si) {
      var spec = s.plate || { kind: "scene" };
      var build = BUILD[spec.kind] || BUILD.scene;
      spec.uid = "p" + i + "_" + si;
      var obj = build(spec);
      if (ep.problem && s.from < (ep.problemUntil || 0)) {
        var pl = el("p", "problem-line");
        pl.textContent = ep.problem;
        obj.el.appendChild(pl);
      }
      var badgeText = (s.meta || spec.kind).split(" · ")[0];
      obj.el.appendChild(el("span", "plate-badge", badgeText));
      platesHost.appendChild(obj.el);
      return obj;
    });
    live = -1;

    elBeatList.innerHTML = "";
    beatBtns = ep.beats.map(function (b) {
      var e = el("button", "beat");
      e.innerHTML = '<span class="n"></span><span class="nm"></span><span class="bt"></span>';
      e.querySelector(".n").textContent = b.n;
      e.querySelector(".nm").textContent = b.name;
      e.querySelector(".bt").textContent = tc(b.from) + "–" + tc(b.to);
      e.title = b.content ? b.content.replace(/\s+/g, " ").slice(0, 400) : "";
      e.addEventListener("click", function () { seek(b.from); });
      elBeatList.appendChild(e);
      return e;
    });

    elShotList.innerHTML = "";
    shotBtns = ep.shots.map(function (s) {
      var e = el("button", "shot");
      e.innerHTML = '<span class="num"></span><span><span class="ttl"></span>' +
                    '<span class="meta"></span><span class="note"></span></span>';
      e.querySelector(".num").textContent = s.num === "" || s.num == null ? "—" : s.num;
      e.querySelector(".ttl").textContent = s.title;
      e.querySelector(".meta").textContent = tc(s.from) + "–" + tc(s.to) +
        (s.meta ? " · " + s.meta : "");
      e.querySelector(".note").textContent = s.note || "";
      e.addEventListener("click", function () { seek(s.from); });
      elShotList.appendChild(e);
      return e;
    });

    elAssetSec.hidden = !(ep.assets && ep.assets.length);
    elAssets.innerHTML = "";
    (ep.assets || []).forEach(function (a, j) {
      var lab = el("label");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      var sp = el("span");
      sp.textContent = a;
      lab.appendChild(cb); lab.appendChild(sp);
      elAssets.appendChild(lab);
    });

    elSegs.innerHTML = ""; elTicks.innerHTML = "";
    segEls = ep.beats.map(function (b) {
      var e = el("div", "seg");
      e.style.left = (b.from / ep.dur * 100) + "%";
      e.style.width = ((b.to - b.from) / ep.dur * 100) + "%";
      e.textContent = b.n;
      e.title = "Beat " + b.n + " — " + b.name;
      elSegs.appendChild(e);
      return e;
    });
    ep.shots.forEach(function (s) {
      var e = el("div", "tick");
      e.style.left = (s.from / ep.dur * 100) + "%";
      e.style.width = ((s.to - s.from) / ep.dur * 100) + "%";
      e.innerHTML = "<span></span>";
      e.firstChild.textContent = s.num === "" || s.num == null ? "·" : s.num;
      elTicks.appendChild(e);
    });

    time = 0;
    paint(0);
    if (!reduced) play(); else pause();
  }

  function at(list, t) {
    for (var i = 0; i < (list || []).length; i++)
      if (t >= list[i].from && t < list[i].to) return list[i];
    return null;
  }
  function setText(e, v) { if (e.textContent !== v) e.textContent = v; }

  function paint(t) {
    var si = 0;
    for (var i = 0; i < ep.shots.length; i++) {
      if (t >= ep.shots[i].from && t < ep.shots[i].to) { si = i; break; }
      if (t >= ep.shots[i].from) si = i;
    }
    var shot = ep.shots[si];
    var p = clamp01((t - shot.from) / Math.max(0.001, shot.to - shot.from));

    if (live !== si) {
      plateObjs.forEach(function (o, j) { o.el.classList.toggle("is-live", j === si); });
      live = si;
    }
    plateObjs[si].update(p, t);

    var endFrom = ep.endFrom == null ? ep.dur + 1 : ep.endFrom;
    var cap = at(ep.captions, t);
    caption.hidden = !cap || t >= endFrom;
    if (cap) setText(caption, cap.text);

    var lt = at(ep.lower, t);
    lthird.hidden = !lt || t >= endFrom;
    if (lt) setText(lthird, lt.text);

    var ml = at(ep.labels, t);
    mlabel.hidden = !ml || t >= endFrom;
    if (ml) setText(mlabel, ml.text);

    endcard.hidden = t < endFrom;
    sting.style.opacity = t < 0.5 ? (1 - t / 0.5) * 0.9 : 0;

    var beat = at(ep.beats, t) || ep.beats[ep.beats.length - 1] || { n: 1, name: "" };
    segEls.forEach(function (e, i) { e.classList.toggle("active", ep.beats[i] === beat); });
    beatBtns.forEach(function (e, i) { e.classList.toggle("on", ep.beats[i] === beat); });
    shotBtns.forEach(function (e, i) { e.classList.toggle("on", i === si); });
    setText(elBeatNow, "beat " + beat.n + " · " + String(beat.name).toLowerCase());
    setText(elTc, tc(t));
    elHead.style.left = (t / ep.dur * 100) + "%";
    elScrub.setAttribute("aria-valuenow", t.toFixed(0));
    elScrub.setAttribute("aria-valuetext", tc(t) + ", beat " + beat.n + " " + beat.name);
  }

  function loop(ts) {
    if (!playing) return;
    if (!last) last = ts;
    var dt = Math.min(0.25, (ts - last) / 1000);
    last = ts;
    time += dt * rate;
    if (time >= ep.dur) { time = ep.dur; pause(); }
    paint(time);
    requestAnimationFrame(loop);
  }
  function play() {
    if (time >= ep.dur) time = 0;
    playing = true; last = 0;
    elPlay.textContent = "❚❚ pause";
    requestAnimationFrame(loop);
  }
  function pause() { playing = false; elPlay.textContent = "▶ play"; }
  function seek(t) { time = Math.max(0, Math.min(ep.dur, t)); paint(time); }

  elPlay.addEventListener("click", function () { playing ? pause() : play(); });
  elBack.addEventListener("click", function () { seek(0); });
  elRate.addEventListener("click", function () {
    rate = rate === 1 ? 2 : (rate === 2 ? 0.5 : 1);
    elRate.textContent = rate + "×";
    elRate.setAttribute("aria-pressed", String(rate !== 1));
  });
  elGuideBtn.addEventListener("click", function () {
    var on = elGuides.classList.toggle("on");
    elGuideBtn.setAttribute("aria-pressed", String(on));
  });

  function scrubTo(e) {
    var r = elScrub.getBoundingClientRect();
    seek((e.clientX - r.left) / r.width * ep.dur);
  }
  var dragging = false;
  elScrub.addEventListener("pointerdown", function (e) {
    dragging = true; elScrub.setPointerCapture(e.pointerId); scrubTo(e);
  });
  elScrub.addEventListener("pointermove", function (e) { if (dragging) scrubTo(e); });
  elScrub.addEventListener("pointerup", function () { dragging = false; });

  document.addEventListener("keydown", function (e) {
    if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (e.code === "Space") { e.preventDefault(); playing ? pause() : play(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); seek(time + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seek(time - 1); }
    else if (e.key === "[") { loadEpisode(Math.max(0, epIndex - 1)); }
    else if (e.key === "]") { loadEpisode(Math.min(EPISODES.length - 1, epIndex + 1)); }
  });

  /* Deep links: #e=3&t=95 opens that episode, parked on that second, so a
     specific moment can be sent to an editor or a collaborator. */
  function fromHash() {
    var m = /[#&]e=(\d+)/.exec(location.hash);
    var s = /[#&]t=(\d+(?:\.\d+)?)/.exec(location.hash);
    return { e: m ? parseInt(m[1], 10) : null, t: s ? parseFloat(s[1]) : null };
  }
  function toHash() {
    var h = "#e=" + epIndex + "&t=" + Math.round(time);
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  var link = fromHash();
  loadEpisode(Math.max(0, Math.min(
    link.e == null ? (SB.start || 0) : link.e, EPISODES.length - 1)));
  if (link.t != null) { pause(); seek(link.t); }

  window.addEventListener("hashchange", function () {
    var l = fromHash();
    if (l.e != null && l.e !== epIndex) loadEpisode(l.e);
    if (l.t != null) { pause(); seek(l.t); }
  });
  elScrub.addEventListener("pointerup", toHash);
  elPlay.addEventListener("click", toHash);
})();
