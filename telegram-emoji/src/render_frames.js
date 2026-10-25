// Renders Lottie JSON files frame by frame with lottie-web in headless Chromium
// (transparent PNGs). This renders the exact animation data that goes into the TGS.
//
//   node render_frames.js <lottie-web.min.js> <json> <outDir> <size> <step>
//
// step = 1 renders all 60 fps frames, step = 2 gives 30 fps.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [lib, json, outDir, size = '512', step = '1'] = process.argv.slice(2);
  const data = JSON.parse(fs.readFileSync(json, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: +size, height: +size } });
  await page.setContent(`<html><body style="margin:0;background:transparent">
    <div id="c" style="width:${size}px;height:${size}px"></div></body></html>`);
  await page.addScriptTag({ path: lib });
  await page.evaluate((d) => {
    window.anim = lottie.loadAnimation({
      container: document.getElementById('c'), renderer: 'svg', loop: false,
      autoplay: false, animationData: d,
    });
  }, data);
  const el = await page.$('#c');
  let n = 0;
  for (let f = data.ip; f < data.op; f += +step) {
    await page.evaluate((fr) => window.anim.goToAndStop(fr, true), f);
    await el.screenshot({ path: path.join(outDir, `f_${String(n++).padStart(4, '0')}.png`),
      omitBackground: true });
  }
  await browser.close();
  console.log(`${path.basename(json)}: ${n} frames -> ${outDir}`);
})();
