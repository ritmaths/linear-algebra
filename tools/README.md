# Rebuilding the site after you edit the LaTeX

Needs: pandoc, Python 3 (with `beautifulsoup4`, `lxml`, `pygments`) and Node.js.

    cd tools
    pip install beautifulsoup4 lxml pygments
    npm install
    python3 build.py LinearAlgebra.tex ..

This regenerates every page in the parent folder from `LinearAlgebra.tex`.
Your `images/` folder is never touched.
(Folder `tools/` is only for you; the website does not use it.)
