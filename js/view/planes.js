// Двумерные палитры моделей: третий способ задания цвета, помимо
// ползунка и числового поля.

import * as C from '../model/convert.js';

const RES = 130; // палитра рисуется в этом разрешении и растягивается на canvas

function paint(canvas, colorAt) {
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(RES, RES);
  const d = img.data;
  for (let j = 0; j < RES; j++) {
    for (let i = 0; i < RES; i++) {
      const rgb = colorAt(i / (RES - 1), 1 - j / (RES - 1));
      const p = (j * RES + i) * 4;
      d[p] = Math.round(Math.min(255, Math.max(0, rgb[0])));
      d[p + 1] = Math.round(Math.min(255, Math.max(0, rgb[1])));
      d[p + 2] = Math.round(Math.min(255, Math.max(0, rgb[2])));
      d[p + 3] = 255;
    }
  }
  const tmp = document.createElement('canvas');
  tmp.width = tmp.height = RES;
  tmp.getContext('2d').putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(tmp, 0, 0, canvas.width, canvas.height);
}

function marker(canvas, u, v) {
  const ctx = canvas.getContext('2d');
  const x = u * canvas.width;
  const y = (1 - v) * canvas.height;
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#000';
  ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = '#fff';
  ctx.beginPath(); ctx.arc(x, y, 5.5, 0, Math.PI * 2); ctx.stroke();
}

// C по горизонтали, M по вертикали, Y и K берём текущие
export function drawCmykPlane(canvas, state) {
  const [, , y, k] = state.cmyk;
  paint(canvas, (u, v) => C.cmykToRgb([u * 100, (1 - v) * 100, y, k]));
  marker(canvas, state.cmyk[0] / 100, 1 - state.cmyk[1] / 100);
}

// плоскость a-b при текущем L
export function drawLabPlane(canvas, state, M, gamut) {
  const L = state.lab[0];
  paint(canvas, (u, v) => C.labToRgb([L, -128 + u * 255, -128 + v * 255], M, gamut).rgb);
  marker(canvas, (state.lab[1] + 128) / 255, (state.lab[2] + 128) / 255);
}

// привычный квадрат насыщенность-яркость при текущем тоне
export function drawHsvPlane(canvas, state) {
  const h = state.hsv[0];
  paint(canvas, (u, v) => C.hsvToRgb([h, u * 100, v * 100]));
  marker(canvas, state.hsv[1] / 100, state.hsv[2] / 100);
}

export function drawHueStrip(canvas, state) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  for (let i = 0; i < w; i++) {
    ctx.fillStyle = C.rgbToHex(C.hsvToRgb([(i / (w - 1)) * 360, 100, 100]));
    ctx.fillRect(i, 0, 1, canvas.height);
  }
  const x = (state.hsv[0] / 360) * w;
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#000';
  ctx.strokeRect(x - 3, 1, 6, canvas.height - 2);
  ctx.strokeStyle = '#fff';
  ctx.strokeRect(x - 1.5, 2.5, 3, canvas.height - 5);
}

export function pickPoint(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  return {
    u: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
    v: Math.min(1, Math.max(0, 1 - (event.clientY - rect.top) / rect.height)),
  };
}
