// Функции сопоставления цветов CIE 1931 и контур спектральных цветов
// для графика МКО. Кривые считаются по гауссовой аппроксимации
// (Wyman, Sloan, Shirley, JCGT 2013), чтобы не таскать таблицу наблюдателя.

function g(x, mu, s1, s2) {
  const t = (x - mu) * (x < mu ? 1 / s1 : 1 / s2);
  return Math.exp(-0.5 * t * t);
}

export function cmf(l) {
  const x = 1.056 * g(l, 599.8, 37.9, 31.0)
          + 0.362 * g(l, 442.0, 16.0, 26.7)
          - 0.065 * g(l, 501.1, 20.4, 26.2);
  const y = 0.821 * g(l, 568.8, 46.9, 40.5)
          + 0.286 * g(l, 530.9, 16.3, 31.1);
  const z = 1.217 * g(l, 437.0, 11.8, 36.0)
          + 0.681 * g(l, 459.0, 26.0, 13.8);
  return [x, y, z];
}

// Подкова спектральных цветов в координатах цветности
export function spectralLocus(step = 1) {
  const pts = [];
  for (let l = 380; l <= 700; l += step) {
    const [X, Y, Z] = cmf(l);
    const s = X + Y + Z;
    if (s <= 0) continue;
    pts.push({ l, x: X / s, y: Y / s });
  }
  return pts;
}
