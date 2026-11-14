#!/usr/bin/env python3
"""Convert LinearAlgebra.tex into a multi-page static website (one page per \\section)."""
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import textwrap
from urllib.parse import quote

from bs4 import BeautifulSoup, NavigableString
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# usage: python3 build.py [path/to/notes.tex] [output_folder]
SRC = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/LinearAlgebra.tex"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/outputs/linear-algebra-notes"

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def find_group(s, i):
    """s[i] == '{' -> index just after the matching '}'."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError("unbalanced braces near: " + s[i : i + 80])


def macro_to_env(s, name, env):
    out, i = [], 0
    pat = re.compile(r"\\" + name + r"(?![a-zA-Z])\s*\{")
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i : m.start()])
        st = m.end() - 1
        en = find_group(s, st)
        out.append("\n\n\\begin{%s}\n%s\n\\end{%s}\n\n" % (env, s[st + 1 : en - 1], env))
        i = en
    return "".join(out)


_pandoc_cache = {}


def pandoc(fragment, inline=False):
    key = (fragment, inline)
    if key in _pandoc_cache:
        return _pandoc_cache[key]
    p = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "html5", "--wrap=none", "--mathjax", "--shift-heading-level-by=1"],
        input=fragment, capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    out = p.stdout.strip()
    if inline:
        out = re.sub(r"^<p>(.*)</p>$", r"\1", out, flags=re.S)
    _pandoc_cache[key] = out
    return out


def slugify(t):
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return t[:48].strip("-")


def plain(t):
    return re.sub(r"\s+", " ", BeautifulSoup(t, "lxml").get_text()).strip()


# --------------------------------------------------------------------------
# read + clean source
# --------------------------------------------------------------------------
raw = open(SRC, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").replace("\r", "\n")
book_title = re.search(r"\\title\{(.*?)\}", raw, re.S).group(1).strip()
book_author = re.sub(r"\s+", " ", re.search(r"\\author\{(.*?)\}", raw, re.S).group(1)).strip()
body = raw.split("\\begin{document}", 1)[1].split("\\end{document}", 1)[0]
dropped_tail = raw.split("\\end{document}", 1)[1].strip()

# 1) code listings -> placeholders (before comment stripping: code may contain %)
listings = []


def grab_listing(m):
    opts, code = m.group(1) or "", m.group(2)
    cap = re.search(r"caption\s*=\s*([^,\]]*)", opts)
    lang = re.search(r"language\s*=\s*([A-Za-z+#]*)", opts)
    code = textwrap.dedent(code.expandtabs(4)).strip("\n")
    listings.append(
        dict(code=code, caption=(cap.group(1).strip().rstrip(":").strip() if cap else ""),
             lang=(lang.group(1) if lang else "text"))
    )
    return "\n\nLSTPH%dZZ\n\n" % (len(listings) - 1)


body = re.sub(r"\\begin\{lstlisting\}(\[[^\]]*\])?\n?(.*?)\\end\{lstlisting\}", grab_listing, body, flags=re.S)

# 2) strip comments
body = re.sub(r"(?<!\\)%.*", "", body)

# 3) figures + tables -> placeholders (numbered in document order)
figures, tables, labels = [], [], {}
fig_n = tab_n = 0


def caption_of(b):
    m = re.search(r"\\caption\s*\{", b)
    if not m:
        return "", len(b)
    st = m.end() - 1
    en = find_group(b, st)
    return b[st + 1 : en - 1].strip(), m.start()


def grab_float(m):
    global fig_n, tab_n
    kind, b = m.group(1), m.group(3)
    cap, cap_pos = caption_of(b)
    lab = re.search(r"\\label\{([^}]*)\}", b)
    if kind == "figure":
        fig_n += 1
        pre = b[:cap_pos]
        rows = []
        for chunk in re.split(r"\\vspace\*?\{[^}]*\}", pre):
            imgs = []
            for opt, name in re.findall(r"\\includegraphics(?:\[([^\]]*)\])?\{(.*?)\}", chunk):
                w = re.search(r"width\s*=\s*([\d.]+)", opt or "")
                imgs.append(dict(name=name.strip().strip('"'), frac=float(w.group(1)) if w and w.group(1) != "." else 1.0))
            if imgs:
                rows.append(imgs)
        sub = re.findall(r"\\makebox\[[^\]]*\]\{([^}]*)\}", pre)
        figures.append(dict(n=fig_n, rows=rows, sub=sub, caption=cap))
        if lab:
            labels[lab.group(1)] = fig_n
        return "\n\nFIGPH%dZZ\n\n" % (len(figures) - 1)
    tab_n += 1
    tab = re.search(r"\\begin\{tabular\}.*\\end\{tabular\}", b, re.S).group(0)
    tables.append(dict(n=tab_n, tex=tab, caption=cap))
    if lab:
        labels[lab.group(1)] = tab_n
    return "\n\nTBLPH%dZZ\n\n" % (len(tables) - 1)


body = re.sub(r"\\begin\{(figure|table)(\*?)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\2\}", grab_float, body, flags=re.S)
body = re.sub(r"\\ref\{([^}]*)\}", lambda m: str(labels.get(m.group(1), "?")), body)

# 4) custom macros -> markers / environments
body = macro_to_env(body, "insight", "insightbox")
body = macro_to_env(body, "takeaway", "takeawaybox")
prob_n = 0


def marker(m):
    global prob_n
    name = m.group(1)
    if name == "problem":
        prob_n += 1
        return "\n\nZZMARKproblem%dZZ " % prob_n
    return "\n\nZZMARK%sZZ " % name


body = re.sub(r"\\(example|deff|solution|proof|problem|note)(?![a-zA-Z])[ \t]*:?", marker, body)

# 5) layout-only commands that have no web meaning
body = re.sub(r"\\(renewcommand)\{[^}]*\}\{[^}]*\}", "", body)
body = re.sub(r"\\(vspace|hspace)\*?\{[^}]*\}", "", body)
body = re.sub(r"\\(noindent|centering|hfill|maketitle|newpage|clearpage)(?![a-zA-Z])", "", body)
body = re.sub(r"\\date\{\}", "", body)
body = re.sub(r"\\par(?![a-zA-Z])", "\n\n", body)
body = re.sub(r"\\label\{[^}]*\}", "", body)
body = re.sub(r"\\begin\{(itemize|enumerate)\}\[[^\]]*\]", r"\\begin{\1}", body)
body = body.replace("green!50!black", "#1b7a3a")

# 6) split into sections
parts = re.split(r"\\section\*?\{([^}]*)\}", body)
preamble_text = parts[0].strip()
sections = []
for i in range(1, len(parts), 2):
    title = re.sub(r"[:\s]+$", "", parts[i].strip())
    src = parts[i + 1]
    src = re.sub(r"\\subsection\*?\{(\s*)([a-z])", lambda m: "\\subsection{" + m.group(1) + m.group(2).upper(), src)
    src = re.sub(r"\\subsection(\*?)\{", r"\\section\1{", src)
    src = re.sub(r"\\subsubsection(\*?)\{", r"\\subsection\1{", src)
    sections.append(dict(title=title, src=src))
assert not preamble_text, "text before first \\section: " + preamble_text[:80]

warnings = []


def fix_envs(src, where):
    """Drop \\end{X} that has no matching \\begin{X} (LaTeX tolerates it, pandoc does not)."""
    stack, out, last = [], [], 0
    for m in re.finditer(r"\\(begin|end)\{([A-Za-z*]+)\}", src):
        kind, env = m.group(1), m.group(2)
        if kind == "begin":
            stack.append(env)
        elif stack and stack[-1] == env:
            stack.pop()
        else:
            line = src.count("\n", 0, m.start()) + 1
            warnings.append("%s: removed unmatched \\end{%s} (line %d of that section)" % (where, env, line))
            out.append(src[last : m.start()])
            last = m.end()
    out.append(src[last:])
    return "".join(out)


for s in sections:
    s["src"] = fix_envs(s["src"], "Section '%s'" % s["title"])

for k, s in enumerate(sections, 1):
    s["num"] = k
    s["file"] = "%02d-%s.html" % (k, slugify(s["title"]))

# --------------------------------------------------------------------------
# placeholder -> html
# --------------------------------------------------------------------------
IMG_EXTS = "png"


def fig_html(f):
    rows_html = []
    sub = f["sub"] if len(f["sub"]) == sum(len(r) for r in f["rows"]) else []
    k = 0
    alt = plain(pandoc(f["caption"], True)) if f["caption"] else ""
    for row in f["rows"]:
        n = len(row)
        items = []
        for im in row:
            if n == 1:
                w = min(100, max(40, im["frac"] * 100))
            else:
                w = min(48, (100 - 2 * (n - 1)) / n)
            label = '<span class="sublabel">%s</span>' % htmllib.escape(sub[k]) if sub else ""
            k += 1
            items.append(
                '<div class="fig-item" style="--w:%.1f"><img src="images/%s.%s" data-name="%s" alt="%s" loading="lazy">%s</div>'
                % (w, quote(im["name"]), IMG_EXTS, htmllib.escape(im["name"], True), htmllib.escape(alt or im["name"], True), label)
            )
        rows_html.append('<div class="fig-row">%s</div>' % "".join(items))
    cap = ""
    if f["caption"]:
        cap = "<figcaption><strong>Figure %d.</strong> %s</figcaption>" % (f["n"], pandoc(f["caption"], True))
    return '<figure class="fig" id="fig-%d">%s%s</figure>' % (f["n"], "".join(rows_html), cap)


def table_html(t):
    cap = "<figcaption><strong>Table %d.</strong> %s</figcaption>" % (t["n"], pandoc(t["caption"], True)) if t["caption"] else ""
    return '<figure class="tbl" id="tbl-%d"><div class="table-wrap">%s</div>%s</figure>' % (t["n"], pandoc(t["tex"]), cap)


PY_FMT = HtmlFormatter(nowrap=True, classprefix="tok-")


def code_html(c):
    if c["caption"].lower().startswith("output") or c["lang"].lower() not in ("python", "py"):
        inner = htmllib.escape(c["code"])
        lang = "Output" if c["caption"].lower().startswith("output") else (c["lang"] or "text")
        cls = "out"
    else:
        inner = highlight(c["code"], PythonLexer(), PY_FMT)
        lang, cls = "Python", "py"
    cap = htmllib.escape(c["caption"]) if c["caption"] else ""
    return (
        '<figure class="code-block %s"><div class="code-head"><span class="lang">%s</span>'
        '<span class="code-cap">%s</span><button class="copy" type="button" aria-label="Copy code">Copy</button></div>'
        "<pre><code>%s</code></pre></figure>" % (cls, lang, cap, inner)
    )


TAGS = {"example": "Example", "deff": "Definition", "solution": "Solution", "proof": "Proof", "note": "Note", "problem": "Problem"}


def markers_html(h):
    def sub(m):
        name, n = m.group(1), m.group(2)
        label = TAGS[name] + (" " + n if n else "")
        return '<span class="tag tag-%s">%s</span>' % (name, label)

    return re.sub(r"ZZMARK([a-z]+?)(\d*)ZZ", sub, h)


# --------------------------------------------------------------------------
# convert each section
# --------------------------------------------------------------------------
def convert(sec):
    h = pandoc(sec["src"])
    h = re.sub(r"<p>FIGPH(\d+)ZZ</p>", lambda m: fig_html(figures[int(m.group(1))]), h)
    h = re.sub(r"<p>TBLPH(\d+)ZZ</p>", lambda m: table_html(tables[int(m.group(1))]), h)
    h = re.sub(r"<p>LSTPH(\d+)ZZ</p>", lambda m: code_html(listings[int(m.group(1))]), h)
    h = markers_html(h)
    soup = BeautifulSoup("<div id='root'>%s</div>" % h, "lxml")
    root = soup.find(id="root")

    # --- heading cleanup, numbering, anchors
    sec["subs"] = []
    sub_i = 0
    for hd in root.find_all(["h2", "h3"]):
        inner = hd.decode_contents()
        inner = re.sub(r"(?:[:\s]|&nbsp;|\xa0)+$", "", inner)
        hd.clear()
        hd.append(BeautifulSoup(inner, "lxml").body or "")
        if hd.name == "h2":
            sub_i += 1
            numtxt = "%d.%d" % (sec["num"], sub_i)
            sec["subs"].append(dict(id=hd.get("id"), num=numtxt, el=hd))
        else:
            numtxt = ""
        if numtxt:
            sp = soup.new_tag("span", attrs={"class": "num"})
            sp.string = numtxt
            hd.insert(0, sp)
        a = soup.new_tag("a", href="#" + (hd.get("id") or ""), attrs={"class": "anchor", "aria-label": "Link to this heading"})
        a.string = "#"
        hd.append(a)

    # --- callout boxes
    for cls, title in (("insightbox", "Insight"), ("takeawaybox", "Key takeaway")):
        for d in root.find_all("div", class_=cls):
            t = soup.new_tag("div", attrs={"class": "box-title"})
            t.string = title
            d.insert(0, t)

    # --- wrap Example / Problem / Solution / Definition / Proof runs into blocks
    WRAP = {"example", "problem", "solution", "deff", "proof"}

    def lead_tag(el):
        if getattr(el, "name", None) != "p":
            return None
        for c in el.children:
            if isinstance(c, NavigableString) and not c.strip():
                continue
            if getattr(c, "name", None) == "span" and "tag" in (c.get("class") or []):
                return [x for x in c["class"] if x.startswith("tag-")][0][4:]
            return None
        return None

    cur = None
    for el in list(root.children):
        if isinstance(el, NavigableString):
            continue
        lt = lead_tag(el)
        is_end = el.name in ("h2", "h3") or (el.name == "div" and any(c in (el.get("class") or []) for c in ("insightbox", "takeawaybox")))
        if is_end:
            cur = None
            continue
        if lt in WRAP:
            cur = soup.new_tag("div", attrs={"class": "blk blk-" + lt})
            el.insert_before(cur)
            cur.append(el.extract())
        elif lt == "note":
            cur = None
        elif cur is not None:
            cur.append(el.extract())

    # --- table scroll wrappers for bare tables
    for t in root.find_all("table"):
        if not t.find_parent(class_="table-wrap"):
            w = soup.new_tag("div", attrs={"class": "table-wrap"})
            t.insert_before(w)
            w.append(t.extract())

    return soup, root


def render_math(soup, root):
    spans = root.select("span.math")
    items = [dict(tex=re.sub(r"^\\[\(\[]|\\[\)\]]$", "", s.get_text()).strip(), display="display" in s.get("class", [])) for s in spans]
    p = subprocess.run(["node", os.path.join(HERE, "render.js")], input=json.dumps(items), capture_output=True, text=True, cwd=HERE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    res = json.loads(p.stdout)
    errs = []
    for s, it, r in zip(spans, items, res):
        if r["err"]:
            errs.append((it["tex"][:90], r["err"][:90]))
        frag = BeautifulSoup(r["html"], "lxml").body
        s.clear()
        for ch in list(frag.children):
            s.append(ch)
    return len(spans), errs


pages = []
all_errs = []
for sec in sections:
    soup, root = convert(sec)
    n, errs = render_math(soup, root)
    all_errs += [(sec["num"],) + e for e in errs]
    sec["html"] = root.decode_contents()
    sec["math_count"] = n
    # re-read headings as html for sidebar (after math rendering)
    for s in sec["subs"]:
        h = s["el"]
        clone = BeautifulSoup(h.decode_contents(), "lxml").body
        for x in clone.select("span.num, a.anchor"):
            x.decompose()
        s["title_html"] = clone.decode_contents().strip()
    for s in sec["subs"]:
        del s["el"]

# --------------------------------------------------------------------------
# page template
# --------------------------------------------------------------------------
def sidebar(current):
    items = []
    for sec in sections:
        is_cur = current == sec["num"]
        subs = "".join(
            '<li><a href="%s#%s"><span class="num">%s</span><span class="t">%s</span></a></li>'
            % (sec["file"], s["id"], s["num"], s["title_html"])
            for s in sec["subs"]
        )
        items.append(
            '<li class="toc-sec%s"><details%s><summary><a class="sec-link" href="%s"><span class="num">%d</span><span class="t">%s</span></a></summary><ol>%s</ol></details></li>'
            % (" current" if is_cur else "", " open" if is_cur else "", sec["file"], sec["num"], htmllib.escape(sec["title"]), subs)
        )
    return (
        '<nav id="sidebar" aria-label="Table of contents">'
        '<a class="brand" href="index.html"><span class="brand-t">%s</span><span class="brand-s">%s</span></a>'
        '<div class="toc-label">Contents</div><ol class="toc">%s</ol></nav>'
        % (htmllib.escape(book_title), htmllib.escape(book_author), "".join(items))
    )


def pager(idx, cls):
    prev = sections[idx - 2] if idx and idx > 1 else None
    nxt = sections[idx] if idx is not None and idx < len(sections) else (sections[0] if idx is None else None)
    left = (
        '<a class="pg prev" rel="prev" href="%s"><span class="dir">&larr; Previous</span><span class="pt">%s</span></a>' % (prev["file"], htmllib.escape(prev["title"]))
        if prev
        else ('<a class="pg prev" rel="prev" href="index.html"><span class="dir">&larr; Back</span><span class="pt">Contents</span></a>' if idx else "<span></span>")
    )
    right = (
        '<a class="pg next" rel="next" href="%s"><span class="dir">%s &rarr;</span><span class="pt">%s</span></a>' % (nxt["file"], "Start reading" if idx is None else "Next", htmllib.escape(nxt["title"]))
        if nxt
        else '<a class="pg next" href="index.html"><span class="dir">Finished &rarr;</span><span class="pt">Back to contents</span></a>'
    )
    return '<div class="pager %s">%s%s</div>' % (cls, left, right)


def shell(title, content, current, idx):
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{book}: lecture notes by {author}">
<script>(function(){{try{{var t=localStorage.getItem('theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.dataset.theme=t}}catch(e){{document.documentElement.dataset.theme='light'}}}})()</script>
<link rel="stylesheet" href="assets/katex/katex.min.css">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="progress"></div>
<header id="topbar">
  <button id="menu-btn" aria-label="Open table of contents" aria-expanded="false">&#9776;</button>
  <a class="top-title" href="index.html">{book}</a>
  <button id="theme-btn" aria-label="Toggle dark mode">&#9680;</button>
</header>
<div id="scrim"></div>
{sidebar}
<main id="main">
<article class="content">
{content}
</article>
{pager}
<footer class="foot">{book} &middot; {author}</footer>
</main>
<script src="assets/site.js"></script>
</body>
</html>
""".format(
        title=htmllib.escape(title), book=htmllib.escape(book_title), author=htmllib.escape(book_author),
        sidebar=sidebar(current), content=content, pager=pager(idx, "bottom"),
    )


os.makedirs(os.path.join(OUT, "assets", "katex", "fonts"), exist_ok=True)
os.makedirs(os.path.join(OUT, "images"), exist_ok=True)

for sec in sections:
    head = '<p class="eyebrow">Section %d of %d</p><h1>%s</h1>' % (sec["num"], len(sections), htmllib.escape(sec["title"]))
    open(os.path.join(OUT, sec["file"]), "w", encoding="utf-8").write(
        shell("%d. %s | %s" % (sec["num"], sec["title"], book_title), head + sec["html"], sec["num"], sec["num"])
    )

cards = "".join(
    '<a class="card" href="%s"><span class="card-n">%d</span><span class="card-t">%s</span><ul>%s</ul></a>'
    % (s["file"], s["num"], htmllib.escape(s["title"]), "".join("<li>%s</li>" % x["title_html"] for x in s["subs"]))
    for s in sections
)
home = (
    '<div class="hero"><p class="eyebrow">Lecture notes</p><h1>%s</h1><p class="by">%s</p>'
    '<p class="lead">%d sections, each on its own page. Use the contents panel on the left to jump to any topic, '
    'or the Previous / Next buttons (or the &larr; &rarr; keys) to read in order.</p>'
    '<a class="start" href="%s">Start reading &rarr;</a></div><div class="cards">%s</div>'
    % (htmllib.escape(book_title), htmllib.escape(book_author), len(sections), sections[0]["file"], cards)
)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(shell(book_title, home, None, None))

# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------
shutil.copy(os.path.join(HERE, "style.css"), os.path.join(OUT, "assets", "style.css"))
shutil.copy(os.path.join(HERE, "site.js"), os.path.join(OUT, "assets", "site.js"))
kd = os.path.join(HERE, "node_modules", "katex", "dist")
css = open(os.path.join(kd, "katex.min.css"), encoding="utf-8").read()
css = re.sub(r",url\([^)]*\.woff\) format\(\"woff\"\)", "", css)
css = re.sub(r",url\([^)]*\.ttf\) format\(\"truetype\"\)", "", css)
open(os.path.join(OUT, "assets", "katex", "katex.min.css"), "w", encoding="utf-8").write(css)
for f in os.listdir(os.path.join(kd, "fonts")):
    if f.endswith(".woff2"):
        shutil.copy(os.path.join(kd, "fonts", f), os.path.join(OUT, "assets", "katex", "fonts", f))

pyg_light = HtmlFormatter(style="default", classprefix="tok-").get_style_defs(".code-block.py")
pyg_dark = HtmlFormatter(style="monokai", classprefix="tok-").get_style_defs('[data-theme="dark"] .code-block.py')
with open(os.path.join(OUT, "assets", "style.css"), "a", encoding="utf-8") as fh:
    fh.write("\n/* syntax highlighting */\n" + pyg_light + "\n" + pyg_dark + "\n")

# image checklist
names = []
for f in figures:
    for r in f["rows"]:
        for im in r:
            if im["name"] not in names:
                names.append(im["name"])
open(os.path.join(OUT, "images", "README.txt"), "w", encoding="utf-8").write(
    "Put your figure files in THIS folder, keeping the same names as in your LaTeX file.\n"
    "Accepted extensions: png, jpg, jpeg, webp, svg, gif (the site tries each one).\n"
    "On GitHub Pages file names are case-sensitive: 'LinCombV.png' is not the same as 'lincombv.png'.\n\n"
    "Images the notes expect (%d):\n" % len(names) + "\n".join("  - " + n for n in names) + "\n"
)
open(os.path.join(OUT, ".nojekyll"), "w").write("")

# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
print("sections:", [(s["num"], s["file"], len(s["subs"]), s["math_count"]) for s in sections])
print("figures:", len(figures), "tables:", len(tables), "listings:", len(listings), "problems:", prob_n)
print("images:", names)
print("math errors:", len(all_errs))
for e in all_errs[:40]:
    print("  ", e)
print("warnings:", warnings)
print("dropped text after \\end{document}: %d chars" % len(dropped_tail))
