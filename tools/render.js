const katex = require('katex');
let input = '';
process.stdin.on('data', d => input += d);
process.stdin.on('end', () => {
  const items = JSON.parse(input);
  const out = items.map(it => {
    let err = '';
    try {
      katex.renderToString(it.tex, {displayMode: it.display, throwOnError: true, strict: 'ignore', trust: false});
    } catch (e) { err = String(e.message || e); }
    const html = katex.renderToString(it.tex, {
      displayMode: it.display, throwOnError: false, errorColor: '#cc0000',
      strict: 'ignore', trust: false, output: 'htmlAndMathml'
    });
    return {html, err};
  });
  process.stdout.write(JSON.stringify(out));
});
