const { chromium } = require('playwright-core');
const fs = require('fs');
(async () => {
  const [inp, outSvg, outPng] = process.argv.slice(2);
  const xml = fs.readFileSync(inp, 'utf8');
  const lib = fs.readFileSync(require.resolve('bpmn-js/dist/bpmn-viewer.production.min.js'), 'utf8');
  const css = ['diagram-js.css','bpmn-js.css'].map(f => fs.readFileSync(require.resolve('bpmn-js/dist/assets/' + f), 'utf8')).join('\n');
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell' });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  await p.setContent(`<html><head><style>${css} body{margin:0;background:#fff;font-family:Arial} #c{width:100vw;height:100vh}</style></head><body><div id="c"></div><script>${lib}</script></body></html>`);
  const res = await p.evaluate(async (xml) => {
    const v = new BpmnJS({ container: '#c' });
    const { warnings } = await v.importXML(xml);
    const { svg } = await v.saveSVG();
    const reg = v.get('elementRegistry');
    return { warnings: warnings.map(w => w.message), svg, n: reg.getAll().length };
  }, xml);
  fs.writeFileSync(outSvg, res.svg);
  // PNG: render saved SVG at 1.5x
  const m = res.svg.match(/width="([\d.]+)" height="([\d.]+)"/);
  const w = Math.ceil(+m[1]), h = Math.ceil(+m[2]);
  const q = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1.5 });
  await q.setContent(`<html><body style="margin:0;background:#fff">${res.svg}</body></html>`);
  await q.screenshot({ path: outPng, fullPage: true });
  console.log(JSON.stringify({ file: inp.split('/').pop(), warnings: res.warnings, elements: res.n, size: [w, h] }));
  await b.close();
})();
