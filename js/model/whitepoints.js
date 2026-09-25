// Исходные данные колориметрии: координаты цветности источников света
// и первичных цветов sRGB. Матрицы перехода из них считаются в colorspace.js.

// CIE 1931, 2-градусный наблюдатель
export const ILLUMINANTS = {
  D65: { name: 'D65 — средний дневной свет (стандарт sRGB)', x: 0.31272, y: 0.32903 },
  D50: { name: 'D50 — тёплый дневной свет (стандарт полиграфии)', x: 0.34567, y: 0.35850 },
  E:   { name: 'E — равноэнергетический источник', x: 1 / 3, y: 1 / 3 },
};

// ITU-R BT.709
export const SRGB_PRIMARIES = {
  r: { x: 0.6400, y: 0.3300 },
  g: { x: 0.3000, y: 0.6000 },
  b: { x: 0.1500, y: 0.0600 },
};

// (x, y) -> XYZ при Y = 1, где z = 1 - x - y
export function xyToXYZ(x, y) {
  return [x / y, 1, (1 - x - y) / y];
}

// Белая точка в шкале 0..100 (для D65 получается 95.047, 100, 108.883)
export function whitePoint100(key) {
  const ill = ILLUMINANTS[key];
  return xyToXYZ(ill.x, ill.y).map((v) => v * 100);
}
