// Преобразования цветовых моделей. Формулы взяты из методички и реализованы
// вручную, библиотеки конвертации не используются.

import { mulMatVec } from './matrix.js';

// --- гамма sRGB ---

export function srgbToLinear(c) {
  return c >= 0.04045 ? Math.pow((c + 0.055) / 1.055, 2.4) : c / 12.92;
}

export function linearToSrgb(c) {
  return c >= 0.0031308 ? 1.055 * Math.pow(c, 1 / 2.4) - 0.055 : 12.92 * c;
}

// --- выход за охват ---

// Приводит линейный RGB в [0, 1]. strategy: 'clip' или 'scale'.
// Второе значение out говорит, был ли цвет вне охвата.
export function fitToGamut(lin, strategy = 'clip') {
  const eps = 1e-6;
  const out = lin.some((v) => v < -eps || v > 1 + eps);
  if (!out) return { rgb: lin.slice(), out: false };

  if (strategy === 'scale') {
    let v = lin.slice();
    const min = Math.min(...v);
    if (min < 0) v = v.map((c) => c - min);   // сдвигаем вверх, если ушли в минус
    const max = Math.max(...v);
    if (max > 1) v = v.map((c) => c / max);   // сжимаем, если вылезли за единицу
    return { rgb: v, out: true };
  }

  return { rgb: lin.map((c) => Math.min(1, Math.max(0, c))), out: true };
}

// --- RGB <-> XYZ ---

export function rgbToXyz(rgb, M) {
  const lin = rgb.map((c) => srgbToLinear(c / 255) * 100);
  return mulMatVec(M.rgbToXyz, lin);
}

export function xyzToRgb(xyz, M, strategy = 'clip') {
  const lin = mulMatVec(M.xyzToRgb, xyz.map((v) => v / 100));
  const fit = fitToGamut(lin, strategy);
  return { rgb: fit.rgb.map((c) => linearToSrgb(c) * 255), out: fit.out };
}

// --- XYZ <-> Lab ---

const LAB_EPS = 0.008856;
const LAB_K = 7.787;

function fLab(t) {
  return t >= LAB_EPS ? Math.cbrt(t) : LAB_K * t + 16 / 116;
}

function fLabInv(t) {
  const t3 = t * t * t;
  return t3 >= LAB_EPS ? t3 : (t - 16 / 116) / LAB_K;
}

export function xyzToLab(xyz, M) {
  const W = M.whiteXYZ100;
  const fx = fLab(xyz[0] / W[0]);
  const fy = fLab(xyz[1] / W[1]);
  const fz = fLab(xyz[2] / W[2]);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

export function labToXyz(lab, M) {
  const W = M.whiteXYZ100;
  const fy = (lab[0] + 16) / 116;
  const fx = fy + lab[1] / 500;
  const fz = fy - lab[2] / 200;
  return [fLabInv(fx) * W[0], fLabInv(fy) * W[1], fLabInv(fz) * W[2]];
}

// --- RGB <-> Lab ---

export function rgbToLab(rgb, M) {
  return xyzToLab(rgbToXyz(rgb, M), M);
}

export function labToRgb(lab, M, strategy = 'clip') {
  return xyzToRgb(labToXyz(lab, M), M, strategy);
}

// --- RGB <-> HSV ---

// H в градусах, S и V в процентах
export function rgbToHsv(rgb) {
  const r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;

  let h = 0;
  if (d > 0) {
    if (max === r)      h = 60 * (((g - b) / d) % 6);
    else if (max === g) h = 60 * ((b - r) / d + 2);
    else                h = 60 * ((r - g) / d + 4);
  }
  if (h < 0) h += 360;

  return [h, max === 0 ? 0 : (d / max) * 100, max * 100];
}

// По блок-схеме из методички: I = Ent(H/60), F = H/60 - I,
// M = V(1-S), N = V(1-S*F), K = V(1-S(1-F))
export function hsvToRgb(hsv) {
  let h = hsv[0] % 360;
  if (h < 0) h += 360;
  if (h === 360) h = 0;
  const s = hsv[1] / 100;
  const v = hsv[2] / 100;

  if (s === 0) return [v * 255, v * 255, v * 255];

  const hh = h / 60;
  const i = Math.floor(hh);
  const f = hh - i;
  const m = v * (1 - s);
  const n = v * (1 - s * f);
  const k = v * (1 - s * (1 - f));

  let rgb;
  switch (i) {
    case 0: rgb = [v, k, m]; break;
    case 1: rgb = [n, v, m]; break;
    case 2: rgb = [m, v, k]; break;
    case 3: rgb = [m, n, v]; break;
    case 4: rgb = [k, m, v]; break;
    default: rgb = [v, m, n];
  }
  return rgb.map((c) => c * 255);
}

// --- RGB <-> CMYK ---

// separation: 'gcr' - серая составляющая заменяется чёрным во всём диапазоне,
//             'ucr' - чёрный добавляется только в тенях, начиная с порога ucrStart.
// amount задаёт долю чёрной краски. Возвращает проценты 0..100.
export function rgbToCmyk(rgb, opts = {}) {
  const separation = opts.separation || 'gcr';
  const amount = opts.amount === undefined ? 1 : opts.amount;
  const start = opts.ucrStart === undefined ? 0.5 : opts.ucrStart;

  const c1 = 1 - rgb[0] / 255;
  const m1 = 1 - rgb[1] / 255;
  const y1 = 1 - rgb[2] / 255;
  const gray = Math.min(c1, m1, y1);

  let k;
  if (separation === 'ucr') {
    k = gray <= start ? 0 : ((gray - start) / (1 - start)) * gray * amount;
  } else {
    k = gray * amount;
  }
  if (k > 0.9999) k = 0.9999; // иначе деление на ноль в чистом чёрном

  const d = 1 - k;
  return [(c1 - k) / d * 100, (m1 - k) / d * 100, (y1 - k) / d * 100, k * 100]
    .map((v) => Math.min(100, Math.max(0, v)));
}

export function cmykToRgb(cmyk) {
  const [c, m, y, k] = cmyk.map((v) => v / 100);
  return [255 * (1 - c) * (1 - k), 255 * (1 - m) * (1 - k), 255 * (1 - y) * (1 - k)];
}

// --- переходы варианта: CMYK <-> Lab <-> HSV через RGB ---

export function labToHsv(lab, M, strategy = 'clip') {
  const r = labToRgb(lab, M, strategy);
  return { hsv: rgbToHsv(r.rgb), out: r.out };
}

export function hsvToLab(hsv, M) {
  return rgbToLab(hsvToRgb(hsv), M);
}

export function cmykToHsv(cmyk) {
  return rgbToHsv(cmykToRgb(cmyk));
}

export function hsvToCmyk(hsv, opts = {}) {
  return rgbToCmyk(hsvToRgb(hsv), opts);
}

export function labToCmyk(lab, M, strategy = 'clip', opts = {}) {
  const r = labToRgb(lab, M, strategy);
  return { cmyk: rgbToCmyk(r.rgb, opts), out: r.out };
}

export function cmykToLab(cmyk, M) {
  return rgbToLab(cmykToRgb(cmyk), M);
}

// --- вспомогательное ---

export function xyzToChromaticity(xyz) {
  const s = xyz[0] + xyz[1] + xyz[2];
  return s === 0 ? [0, 0] : [xyz[0] / s, xyz[1] / s];
}

export function rgbToHex(rgb) {
  return '#' + rgb.map((c) => {
    const v = Math.round(Math.min(255, Math.max(0, c)));
    return v.toString(16).padStart(2, '0');
  }).join('');
}

export function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}
