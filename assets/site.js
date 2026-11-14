(function () {
  var d = document, b = d.body, root = d.documentElement;

  /* ---------- mobile menu ---------- */
  var menuBtn = d.getElementById('menu-btn'), scrim = d.getElementById('scrim');
  function setMenu(open) {
    b.classList.toggle('menu-open', open);
    if (menuBtn) menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  if (menuBtn) menuBtn.addEventListener('click', function () { setMenu(!b.classList.contains('menu-open')); });
  if (scrim) scrim.addEventListener('click', function () { setMenu(false); });
  d.querySelectorAll('#sidebar a').forEach(function (a) {
    a.addEventListener('click', function () { setMenu(false); });
  });

  /* ---------- theme toggle ---------- */
  function icons() {
    var ic = root.dataset.theme === 'dark' ? '\u2600' : '\u263E';
    d.querySelectorAll('#theme-btn, #theme-fab').forEach(function (x) { x.textContent = ic; });
  }
  function toggleTheme() {
    var t = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = t;
    try { localStorage.setItem('theme', t); } catch (e) {}
    icons();
  }
  var tb = d.getElementById('theme-btn');
  if (tb) tb.addEventListener('click', toggleTheme);
  var fab = d.createElement('button');
  fab.id = 'theme-fab'; fab.type = 'button'; fab.innerHTML = '&#9680;'; fab.setAttribute('aria-label', 'Toggle dark mode');
  fab.addEventListener('click', toggleTheme);
  b.appendChild(fab);
  icons();

  /* ---------- reading progress ---------- */
  var bar = d.getElementById('progress');
  function onScroll() {
    var h = root.scrollHeight - root.clientHeight;
    if (bar) bar.style.width = (h > 0 ? (root.scrollTop / h) * 100 : 0) + '%';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- keyboard navigation (left / right arrows) ---------- */
  d.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var t = e.target, tag = t && t.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
    var sel = e.key === 'ArrowRight' ? 'a.pg.next' : e.key === 'ArrowLeft' ? 'a.pg.prev' : null;
    var link = sel && d.querySelector(sel);
    if (link) location.href = link.href;
  });

  /* ---------- scroll-spy: highlight the current topic in the sidebar ---------- */
  var heads = Array.prototype.slice.call(d.querySelectorAll('.content h2[id]'));
  var links = {};
  d.querySelectorAll('.toc-sec.current ol a').forEach(function (a) {
    var id = decodeURIComponent((a.getAttribute('href').split('#')[1] || ''));
    if (id) links[id] = a;
  });
  var active = null;
  function spy() {
    if (!heads.length) return;
    var cur = null, y = 110;
    heads.forEach(function (h) { if (h.getBoundingClientRect().top <= y) cur = h; });
    var a = cur ? links[cur.id] : null;
    if (a === active) return;
    if (active) active.classList.remove('active');
    active = a;
    if (a) {
      a.classList.add('active');
      var sb = d.getElementById('sidebar'), r = a.getBoundingClientRect(), s = sb.getBoundingClientRect();
      if (r.top < s.top + 60 || r.bottom > s.bottom - 40) sb.scrollTop += r.top - s.top - s.height / 2;
    }
  }
  window.addEventListener('scroll', spy, { passive: true });
  spy();
  var cs = d.querySelector('.toc-sec.current');
  if (cs && !location.hash) {
    var sb0 = d.getElementById('sidebar');
    sb0.scrollTop = Math.max(0, cs.offsetTop - 120);
  }

  /* ---------- figures: try several image extensions, then show a placeholder ---------- */
  var EXT = ['png', 'jpg', 'jpeg', 'webp', 'svg', 'gif'];
  function candidates(name) {
    var out = [], lower = name.toLowerCase();
    [name, lower].forEach(function (n, i) {
      if (i === 1 && lower === name) return;
      EXT.forEach(function (e) { out.push('images/' + encodeURIComponent(n).replace(/%2F/g, '/') + '.' + e); });
    });
    return out;
  }
  function wire(img) {
    var name = img.getAttribute('data-name'), list = candidates(name), i = 0;
    function next() {
      i++;
      if (i < list.length) { img.src = list[i]; return; }
      var ph = d.createElement('div');
      ph.className = 'fig-missing';
      ph.textContent = 'Image not found: images/' + name + '.png (or .jpg / .jpeg / .webp / .svg)';
      img.replaceWith(ph);
    }
    img.addEventListener('error', next);
    if (img.complete && img.naturalWidth === 0) next();
  }
  d.querySelectorAll('img[data-name]').forEach(wire);

  /* ---------- very wide inline formulas: give them their own scrollable line ---------- */
  function fitMath() {
    d.querySelectorAll('span.math.inline').forEach(function (m) {
      if (m.closest('.table-wrap')) return;
      m.classList.remove('wide');
      var host = m.parentElement;
      if (host && m.getBoundingClientRect().width > host.clientWidth + 1) m.classList.add('wide');
    });
  }
  fitMath();
  window.addEventListener('resize', fitMath);
  window.addEventListener('load', fitMath);

  /* ---------- copy buttons on code blocks ---------- */
  d.querySelectorAll('.code-block .copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var code = btn.closest('.code-block').querySelector('code').innerText;
      function done() { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = 'Copy'; }, 1400); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(code).then(done, done);
      else {
        var ta = d.createElement('textarea'); ta.value = code; d.body.appendChild(ta); ta.select();
        try { d.execCommand('copy'); } catch (e) {} d.body.removeChild(ta); done();
      }
    });
  });
})();
