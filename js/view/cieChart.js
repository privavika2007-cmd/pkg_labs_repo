// График МКО: подкова спектральных цветов, треугольник охвата sRGB,
// белая точка источника и текущий цвет.

import { spectralLocus } from '../model/cie.js';
import { SRGB_PRIMARIES } from '../model/whitepoints.js';
import { mulMatVec } from '../model/matrix.js';
import { linearToSrgb, xyzToChromaticity } from '../model/convert.js';

const PAD = { l: 42, r: 12, t: 12, b: 34 };
const XMAX = 0.8;
const YMAX = 0.9;

const locus = spectralLocus(1);
let cache = { key: null, canvas: null };

function toPx(c, x, y) {
  const w = c.width - PAD.l - PAD.r;
  const h = c.height - PAD.t - PAD.b;
  return [PAD.l + (x / XMAX) * w, PAD.t + h - (y / YMAX) * h];
}

function inLocus(x, y) {
  let inside = false;
  for (let i = 0, j = locus.length - 1; i < locus.length; j = i++) {
    const xi = locus[i].x, yi = locus[i].y;
    const xj = locus[j].x, yj = locus[j].y;
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Подложка тяжёлая, поэтому рисуется один раз на источник освещения
function buildBackground(canvas, M) {
  const off = document.createElement('canvas');
  off.width = canvas.width;
  off.height = canvas.height;
  const ctx = off.getContext('2d');
  const w = canvas.width - PAD.l - PAD.r;
  const h = canvas.height - PAD.t - PAD.b;
  const img = ctx.createImageData(w, h);
  const d = img.data;

  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      const x = (i / w) * XMAX;
      const y = (1 - j / h) * YMAX;
      const p = (j * w + i) * 4;
      if (y <= 0 || !inLocus(x, y)) { d[p + 3] = 0; continue; }

      let lin = mulMatVec(M.xyzToRgb, [x / y, 1, (1 - x - y) / y]);
      const min = Math.min(...lin);
      if (min < 0) lin = lin.map((v) => v - min);
      const max = Math.max(...lin);
      if (max > 0) lin = lin.map((v) => v / max);

      const rgb = lin.map((v) => linearToSrgb(v) * 255);
      d[p] = rgb[0]; d[p + 1] = rgb[1]; d[p + 2] = rgb[2]; d[p + 3] = 255;
    }
  }
  ctx.putImageData(img, PAD.l, PAD.t);
  return off;
}

function drawAxes(ctx, c) {
  ctx.strokeStyle = '#c9ccd3';
  ctx.fillStyle = '#6b7280';
  ctx.font = '11px ui-monospace, Menlo, monospace';
  ctx.lineWidth = 1;

  for (let x = 0; x <= XMAX + 1e-9; x += 0.1) {
    const [px, py] = toPx(c, x, 0);
    ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, py + 4); ctx.stroke();
    ctx.textAlign = 'center';
    ctx.fillText(x.toFixed(1), px, py + 16);
  }
  for (let y = 0; y <= YMAX + 1e-9; y += 0.1) {
    const [px, py] = toPx(c, 0, y);
    ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px - 4, py); ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(y.toFixed(1), px - 7, py + 4);
  }

  const o = toPx(c, 0, 0);
  const ex = toPx(c, XMAX, 0);
  const ey = toPx(c, 0, YMAX);
  ctx.strokeStyle = '#9aa0ab';
  ctx.beginPath();
  ctx.moveTo(ey[0], ey[1]); ctx.lineTo(o[0], o[1]); ctx.lineTo(ex[0], ex[1]);
  ctx.stroke();
  ctx.textAlign = 'center';
  ctx.fillText('x', ex[0], ex[1] + 28);
  ctx.fillText('y', ey[0] - 26, ey[1] + 4);
}

export function drawCieChart(canvas, state) {
  const M = state.matrices;
  const ctx = canvas.getContext('2d');
  const key = M.illuminant + '|' + M.method;

  if (cache.key !== key) cache = { key, canvas: buildBackground(canvas, M) };

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(cache.canvas, 0, 0);
  drawAxes(ctx, canvas);

  ctx.strokeStyle = '#3a3f4a';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  locus.forEach((p, i) => {
    const [px, py] = toPx(canvas, p.x, p.y);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  });
  ctx.closePath();
  ctx.stroke();

  ctx.strokeStyle = 'rgba(255,255,255,.9)';
  ctx.lineWidth = 1.6;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  [SRGB_PRIMARIES.r, SRGB_PRIMARIES.g, SRGB_PRIMARIES.b].forEach((p, i) => {
    const [px, py] = toPx(canvas, p.x, p.y);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  });
  ctx.closePath();
  ctx.stroke();
  ctx.setLineDash([]);

  const wxy = xyzToChromaticity(M.whiteXYZ100);
  const [wx, wy] = toPx(canvas, wxy[0], wxy[1]);
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(wx - 5, wy); ctx.lineTo(wx + 5, wy);
  ctx.moveTo(wx, wy - 5); ctx.lineTo(wx, wy + 5);
  ctx.stroke();
  ctx.fillStyle = '#000';
  ctx.font = '11px ui-monospace, Menlo, monospace';
  ctx.textAlign = 'left';
  ctx.fillText(M.illuminant, wx + 8, wy - 6);

  const cxy = xyzToChromaticity(state.xyz);
  const [cx, cy] = toPx(canvas, cxy[0], cxy[1]);
  ctx.beginPath();
  ctx.arc(cx, cy, 6, 0, Math.PI * 2);
  ctx.fillStyle = state.hex;
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#111';
  ctx.stroke();
}
