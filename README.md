# Linear Algebra and Optimization: web notes

Open `index.html` to start. One page per section, with a contents sidebar and Previous / Next buttons.

## 1. Add your figures
Copy your image files into the `images/` folder, keeping the names used in LaTeX
(list in `images/README.txt`). png, jpg, jpeg, webp, svg and gif all work.
Missing images show a dashed placeholder with the expected file name.
On GitHub the names are case-sensitive (`LinCombV.png` is not `lincombv.png`).

## 2. Publish for free (GitHub Pages)
1. Create a new public repository on github.com, e.g. `linear-algebra-notes`.
2. Upload everything in this folder (including `images/`, `assets/` and the hidden `.nojekyll` file) to the repository root.
3. Repository Settings > Pages > Source: "Deploy from a branch", Branch: `main`, folder `/ (root)`, then Save.
4. After a minute the site is live at `https://<your-username>.github.io/linear-algebra-notes/`.

Alternatives (also free, no Git needed): drag this folder onto https://app.netlify.com/drop
or create a Cloudflare Pages project with "Direct upload".

## 3. Updating
Edit `tools/LinearAlgebra.tex`, run the builder (see `tools/README.md`), and upload the changed files again.
