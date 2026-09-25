// Построение матриц RGB <-> XYZ. Готовых матриц в коде нет: они выводятся
// из координат цветности первичных цветов и белой точки выбранного источника.

import { mulMat, mulMatVec, invMat, diag } from './matrix.js';
import { ILLUMINANTS, SRGB_PRIMARIES, xyToXYZ } from './whitepoints.js';

// Матрица Брэдфорда - коэффициенты модели хроматической адаптации фон Криза
const BRADFORD = [
  [ 0.8951,  0.2664, -0.1614],
  [-0.7502,  1.7135,  0.0367],
  [ 0.0389, -0.0685,  1.0296],
];

// Вывод матрицы по первичным цветам:
// столбцы Mp - XYZ первичных цветов при Y = 1;
// S = Mp^-1 * W - множители, при которых RGB(1,1,1) даёт белую точку;
// итог M = Mp * diag(S).
export function buildFromPrimaries(whiteXYZ) {
  const R = xyToXYZ(SRGB_PRIMARIES.r.x, SRGB_PRIMARIES.r.y);
  const G = xyToXYZ(SRGB_PRIMARIES.g.x, SRGB_PRIMARIES.g.y);
  const B = xyToXYZ(SRGB_PRIMARIES.b.x, SRGB_PRIMARIES.b.y);
  const Mp = [
    [R[0], G[0], B[0]],
    [R[1], G[1], B[1]],
    [R[2], G[2], B[2]],
  ];
  return mulMat(Mp, diag(mulMatVec(invMat(Mp), whiteXYZ)));
}

// Адаптация src -> dst: M = M_A^-1 * diag(rho_dst / rho_src) * M_A
export function bradfordAdaptation(srcW, dstW) {
  const rs = mulMatVec(BRADFORD, srcW);
  const rd = mulMatVec(BRADFORD, dstW);
  const D = diag([rd[0] / rs[0], rd[1] / rs[1], rd[2] / rs[2]]);
  return mulMat(invMat(BRADFORD), mulMat(D, BRADFORD));
}

// method: 'primaries' - пересчёт первичных цветов под новую белую точку,
//         'bradford'  - адаптация родной для sRGB матрицы D65.
export function buildMatrices(illuminantKey, method = 'primaries') {
  const ill = ILLUMINANTS[illuminantKey];
  const W = xyToXYZ(ill.x, ill.y);

  let rgbToXyz;
  if (method === 'bradford') {
    const d65 = xyToXYZ(ILLUMINANTS.D65.x, ILLUMINANTS.D65.y);
    rgbToXyz = mulMat(bradfordAdaptation(d65, W), buildFromPrimaries(d65));
  } else {
    rgbToXyz = buildFromPrimaries(W);
  }

  return {
    illuminant: illuminantKey,
    method,
    whiteXYZ: W,
    whiteXYZ100: W.map((v) => v * 100),
    rgbToXyz,
    xyzToRgb: invMat(rgbToXyz),
  };
}
