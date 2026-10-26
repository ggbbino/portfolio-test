// Frame-by-frame renderer for scene.html (headless Chromium via Playwright).
//   node src/render.js <outDir> [fps=30] [duration=28] [--times=3.5,10.2,...]
// Motion-blur windows are rendered as 5 sub-frames (180° shutter) and merged by merge.py.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const BLUR = [[13.98, 14.56], [18.8, 19.45], [19.95, 20.6], [21.1, 22.0]];
const SUB = 5;

(async () => {
  const args = process.argv.slice(2);
  const out = args[0];
  const fps = +(args[1] || 30), dur = +(args[2] || 28);
  const timesArg = args.find((a) => a.startsWith('--times='));
  fs.mkdirSync(out, { recursive: true });
  const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'assets', 'meta.json'), 'utf8'));
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.addInitScript((m) => { window.__META__ = m; }, meta);
  await page.goto('file://' + path.join(ROOT, 'src', 'scene.html'));
  await page.evaluate(() => window.__setup__());
  await page.waitForTimeout(300);

  const jobs = [];
  if (timesArg) {
    timesArg.slice(8).split(',').forEach((s) => jobs.push({ name: `t_${(+s).toFixed(2)}`, times: [+s] }));
  } else {
    const n = Math.round(fps * dur);
    for (let i = 0; i < n; i++) {
      const t = i / fps;
      const blur = BLUR.some(([a, b]) => t >= a && t <= b);
      const times = blur ? [...Array(SUB).keys()].map((k) => t + (k / (SUB - 1) - 0.5) * (0.5 / fps)) : [t];
      jobs.push({ name: `f_${String(i).padStart(4, '0')}`, times });
    }
  }
  for (const j of jobs) {
    for (let k = 0; k < j.times.length; k++) {
      await page.evaluate((tt) => window.render(tt), j.times[k]);
      const file = path.join(out, j.times.length > 1 ? `${j.name}_s${k}.png` : `${j.name}.png`);
      await page.screenshot({ path: file });
    }
  }
  await browser.close();
  console.log(`rendered ${jobs.length} frames -> ${out}`);
})();
