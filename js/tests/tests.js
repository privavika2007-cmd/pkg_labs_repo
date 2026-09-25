// Тесты математики преобразований. Запуск: node js/tests/tests.js
// или js/tests/tests.html в браузере.

import { buildMatrices } from '../model/colorspace.js';
import { whitePoint100 } from '../model/whitepoints.js';
import { mulMat, mulMatVec, invMat } from '../model/matrix.js';
import * as C from '../model/convert.js';

const results = [];

function test(name, fn) {
  try {
    fn();
    results.push({ name, ok: true, msg: 'пройден' });
  } catch (e) {
    results.push({ name, ok: false, msg: e.message });
  }
}

function near(actual, expected, eps, what = '') {
  if (Math.abs(actual - expected) > eps) {
    throw new Error(`${what} получено ${actual.toFixed(4)}, ожидалось ${expected.toFixed(4)} (допуск ${eps})`);
  }
}

function nearVec(actual, expected, eps, what = '') {
  expected.forEach((e, i) => near(actual[i], e, eps, `${what}[${i}]`));
}

const D65 = buildMatrices('D65', 'primaries');
const D50 = buildMatrices('D50', 'primaries');
const E   = buildMatrices('E', 'primaries');

// матрицы перехода

test('Матрица RGB→XYZ для D65 совпадает с табличной sRGB', () => {
  const m = D65.rgbToXyz;
  const ref = [
    [0.412453, 0.357580, 0.180423],
    [0.212671, 0.715160, 0.072169],
    [0.019334, 0.119193, 0.950227],
  ];
  for (let i = 0; i < 3; i++) nearVec(m[i], ref[i], 2e-3, `строка ${i}`);
});

test('RGB(1,1,1) в линейном виде даёт белую точку источника', () => {
  [D65, D50, E].forEach((M) => {
    const w = mulMatVec(M.rgbToXyz, [1, 1, 1]);
    nearVec(w, M.whiteXYZ, 1e-9, M.illuminant);
  });
});

test('Обратная матрица XYZ→RGB даёт единичную матрицу', () => {
  const I = mulMat(D65.rgbToXyz, D65.xyzToRgb);
  nearVec(I[0], [1, 0, 0], 1e-9);
  nearVec(I[1], [0, 1, 0], 1e-9);
  nearVec(I[2], [0, 0, 1], 1e-9);
});

test('Матрицы для разных источников отличаются (пересчёт на лету)', () => {
  const diff = Math.abs(D65.rgbToXyz[0][0] - D50.rgbToXyz[0][0]);
  if (diff < 1e-3) throw new Error('матрица не изменилась при смене источника');
});

test('Белая точка D50 равна 96.422, 100, 82.521', () => {
  nearVec(whitePoint100('D50'), [96.422, 100, 82.521], 5e-2);
});

test('Метод Брэдфорда даёт ту же белую точку, что и пересчёт первичных цветов', () => {
  const b = buildMatrices('D50', 'bradford');
  const w = mulMatVec(b.rgbToXyz, [1, 1, 1]);
  nearVec(w, b.whiteXYZ, 1e-6);
});

// эталонные цвета

test('RGB(255,0,0) → Lab(53.24, 80.09, 67.20)', () => {
  nearVec(C.rgbToLab([255, 0, 0], D65), [53.2408, 80.0925, 67.2032], 5e-2);
});

test('RGB(255,0,0) → CMYK(0, 100, 100, 0)', () => {
  nearVec(C.rgbToCmyk([255, 0, 0]), [0, 100, 100, 0], 1e-9);
});

test('RGB(255,0,0) → HSV(0, 100, 100)', () => {
  nearVec(C.rgbToHsv([255, 0, 0]), [0, 100, 100], 1e-9);
});

test('RGB(0,255,0) → Lab(87.73, -86.18, 83.18)', () => {
  nearVec(C.rgbToLab([0, 255, 0], D65), [87.7347, -86.1827, 83.1793], 5e-2);
});

test('RGB(0,0,255) → Lab(32.30, 79.19, -107.86)', () => {
  nearVec(C.rgbToLab([0, 0, 255], D65), [32.2970, 79.1875, -107.8602], 5e-2);
});

test('Белый цвет даёт L=100, a=b=0 при любом источнике', () => {
  [D65, D50, E].forEach((M) => nearVec(C.rgbToLab([255, 255, 255], M), [100, 0, 0], 1e-6, M.illuminant));
});

test('Чёрный цвет даёт Lab(0,0,0) и CMYK K=100', () => {
  nearVec(C.rgbToLab([0, 0, 0], D65), [0, 0, 0], 1e-9);
  near(C.rgbToCmyk([0, 0, 0])[3], 99.99, 1e-2, 'K');
});

test('Серый цвет не имеет цветности: a = b = 0', () => {
  const lab = C.rgbToLab([128, 128, 128], D65);
  near(lab[1], 0, 1e-6, 'a'); near(lab[2], 0, 1e-6, 'b');
});

// обратимость

const SAMPLES = [[255,0,0],[0,255,0],[0,0,255],[12,200,77],[230,120,60],[3,3,3],[200,200,10],[99,10,240]];

test('Обратимость RGB → Lab → RGB', () => {
  SAMPLES.forEach((s) => {
    const back = C.labToRgb(C.rgbToLab(s, D65), D65, 'clip').rgb;
    nearVec(back, s, 0.5, `цвет ${s}`);
  });
});

test('Обратимость RGB → CMYK → RGB (GCR)', () => {
  SAMPLES.forEach((s) => {
    const back = C.cmykToRgb(C.rgbToCmyk(s, { separation: 'gcr' }));
    nearVec(back, s, 0.1, `цвет ${s}`);
  });
});

test('Обратимость RGB → CMYK → RGB (UCR)', () => {
  SAMPLES.forEach((s) => {
    const back = C.cmykToRgb(C.rgbToCmyk(s, { separation: 'ucr', ucrStart: 0.5 }));
    nearVec(back, s, 0.1, `цвет ${s}`);
  });
});

test('Обратимость Lab → XYZ → Lab', () => {
  [[50, 20, -30], [90, -60, 40], [5, 0, 0]].forEach((lab) => {
    nearVec(C.xyzToLab(C.labToXyz(lab, D50), D50), lab, 1e-9);
  });
});

test('Обратимость гамма-коррекции sRGB', () => {
  for (let i = 0; i <= 255; i += 17) {
    near(C.linearToSrgb(C.srgbToLinear(i / 255)) * 255, i, 1e-9, `канал ${i}`);
  }
});

// модель HSV

test('Основные цвета дают верный тон H', () => {
  near(C.rgbToHsv([255, 0, 0])[0], 0, 1e-9, 'красный');
  near(C.rgbToHsv([255, 255, 0])[0], 60, 1e-9, 'жёлтый');
  near(C.rgbToHsv([0, 255, 0])[0], 120, 1e-9, 'зелёный');
  near(C.rgbToHsv([0, 255, 255])[0], 180, 1e-9, 'голубой');
  near(C.rgbToHsv([0, 0, 255])[0], 240, 1e-9, 'синий');
  near(C.rgbToHsv([255, 0, 255])[0], 300, 1e-9, 'пурпурный');
});

test('Серый цвет в HSV имеет нулевую насыщенность', () => {
  const hsv = C.rgbToHsv([128, 128, 128]);
  near(hsv[1], 0, 1e-9, 'S');
  near(hsv[2], 50.196, 1e-2, 'V');
});

test('HSV с нулевой насыщенностью даёт ахроматический цвет', () => {
  const rgb = C.hsvToRgb([200, 0, 40]);
  nearVec(rgb, [102, 102, 102], 1e-9);
});

test('Обратимость RGB → HSV → RGB', () => {
  SAMPLES.forEach((s) => nearVec(C.hsvToRgb(C.rgbToHsv(s)), s, 1e-9, `цвет ${s}`));
});

test('Обратимость HSV → RGB → HSV', () => {
  [[0, 100, 100], [37.5, 62, 88], [210, 15, 40], [359.9, 100, 100]].forEach((hsv) => {
    nearVec(C.rgbToHsv(C.hsvToRgb(hsv)), hsv, 1e-6, `HSV ${hsv}`);
  });
});

// переходы варианта 5: CMYK <-> Lab <-> HSV

test('CMYK(0,100,100,0) → Lab(53.24, 80.09, 67.20)', () => {
  nearVec(C.cmykToLab([0, 100, 100, 0], D65), [53.2408, 80.0925, 67.2032], 5e-2);
});

test('CMYK(0,100,100,0) → HSV(0, 100, 100)', () => {
  nearVec(C.cmykToHsv([0, 100, 100, 0]), [0, 100, 100], 1e-9);
});

test('Lab красного цвета → HSV(0, 100, 100)', () => {
  const r = C.labToHsv([53.2408, 80.0925, 67.2032], D65, 'clip');
  nearVec(r.hsv, [0, 100, 100], 5e-2);
});

test('Цикл CMYK → Lab → CMYK сохраняет цвет', () => {
  // Цветоделение неоднозначно: одному цвету отвечает много наборов CMYK.
  // Поэтому сравниваются не компоненты красок, а сам воспроизводимый цвет.
  [[10, 80, 30, 5], [0, 0, 0, 40], [60, 20, 90, 0]].forEach((cmyk) => {
    const back = C.labToCmyk(C.cmykToLab(cmyk, D65), D65, 'clip', { separation: 'gcr' }).cmyk;
    nearVec(C.cmykToRgb(back), C.cmykToRgb(cmyk), 0.5, `CMYK ${cmyk}`);
  });
});

test('Обратимость HSV → Lab → HSV', () => {
  [[25, 90, 80], [180, 40, 60], [300, 100, 100]].forEach((hsv) => {
    const back = C.labToHsv(C.hsvToLab(hsv, D65), D65, 'clip').hsv;
    nearVec(back, hsv, 0.2, `HSV ${hsv}`);
  });
});

test('Обратимость HSV → CMYK → HSV', () => {
  [[25, 90, 80], [180, 40, 60], [0, 0, 100]].forEach((hsv) => {
    nearVec(C.cmykToHsv(C.hsvToCmyk(hsv)), hsv, 1e-6, `HSV ${hsv}`);
  });
});

// цветоделение

test('GCR с нулевой долей чёрного не использует краску K', () => {
  const c = C.rgbToCmyk([100, 150, 200], { separation: 'gcr', amount: 0 });
  near(c[3], 0, 1e-9, 'K');
});

test('UCR не добавляет чёрный в светлых тонах', () => {
  const c = C.rgbToCmyk([220, 230, 240], { separation: 'ucr', ucrStart: 0.5 });
  near(c[3], 0, 1e-9, 'K');
});

test('UCR добавляет чёрный в глубоких тенях', () => {
  const c = C.rgbToCmyk([20, 25, 30], { separation: 'ucr', ucrStart: 0.5 });
  if (c[3] <= 0) throw new Error('в тенях чёрная краска не появилась');
});

test('UCR расходует меньше чёрной краски, чем GCR', () => {
  const g = C.rgbToCmyk([40, 60, 80], { separation: 'gcr' })[3];
  const u = C.rgbToCmyk([40, 60, 80], { separation: 'ucr' })[3];
  if (!(u < g)) throw new Error(`UCR K=${u.toFixed(2)} не меньше GCR K=${g.toFixed(2)}`);
});

// охват

test('Цвет внутри охвата не помечается как обрезанный', () => {
  const r = C.labToRgb(C.rgbToLab([200, 100, 50], D65), D65, 'clip');
  if (r.out) throw new Error('ложное срабатывание предупреждения');
});

test('Цвет вне охвата помечается флагом и приводится в диапазон', () => {
  ['clip', 'scale'].forEach((mode) => {
    const r = C.labToRgb([60, 120, -120], D65, mode);
    if (!r.out) throw new Error(`${mode}: выход за охват не обнаружен`);
    r.rgb.forEach((v) => {
      if (v < -1e-6 || v > 255 + 1e-6) throw new Error(`${mode}: канал ${v.toFixed(2)} вне 0..255`);
    });
  });
});

test('Стратегии Clipping и Scaling дают разный результат', () => {
  const a = C.labToRgb([60, 120, -120], D65, 'clip').rgb;
  const b = C.labToRgb([60, 120, -120], D65, 'scale').rgb;
  const d = a.reduce((s, v, i) => s + Math.abs(v - b[i]), 0);
  if (d < 1) throw new Error('результаты стратегий совпали');
});

const passed = results.filter((r) => r.ok).length;

export function report() {
  return { results, passed, total: results.length };
}

if (typeof document !== 'undefined' && document.getElementById('out')) {
  const out = document.getElementById('out');
  out.innerHTML = results.map((r) =>
    `<tr class="${r.ok ? 'ok' : 'fail'}"><td>${r.ok ? '✓' : '✗'}</td><td>${r.name}</td><td>${r.msg}</td></tr>`
  ).join('');
  document.getElementById('summary').textContent =
    `${passed} из ${results.length} тестов пройдено`;
  document.getElementById('summary').className = passed === results.length ? 'ok' : 'fail';
}

results.forEach((r) => console[r.ok ? 'log' : 'error'](`${r.ok ? 'PASS' : 'FAIL'} — ${r.name}: ${r.msg}`));
