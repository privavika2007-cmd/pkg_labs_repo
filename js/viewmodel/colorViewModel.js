// Состояние цвета и настроек. Берёт данные из интерфейса, гоняет их через
// функции модели и отдаёт результат обратно. С DOM тут ничего не связано.

import { buildMatrices } from '../model/colorspace.js';
import * as C from '../model/convert.js';

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export class ColorViewModel {
  constructor() {
    this.listeners = [];

    this.settings = {
      illuminant: 'D65',
      adaptation: 'primaries',
      gamut: 'clip',
      separation: 'gcr',
      amount: 1,
      ucrStart: 0.5,
    };

    this.matrices = buildMatrices(this.settings.illuminant, this.settings.adaptation);

    // RGB хранится как промежуточное представление: через него идут все переходы
    this.rgb = [230, 120, 60];
    this.cmyk = [0, 0, 0, 0];
    this.lab = [0, 0, 0];
    this.hsv = [0, 0, 0];
    this.warning = null;
    this.lastEdited = 'hsv';

    this.fromRgb(this.rgb);
  }

  subscribe(fn) {
    this.listeners.push(fn);
    fn(this.snapshot());
  }

  notify() {
    const s = this.snapshot();
    this.listeners.forEach((fn) => fn(s));
  }

  snapshot() {
    return {
      rgb: this.rgb,
      cmyk: this.cmyk,
      lab: this.lab,
      hsv: this.hsv,
      hex: C.rgbToHex(this.rgb),
      xyz: C.rgbToXyz(this.rgb, this.matrices),
      settings: { ...this.settings },
      matrices: this.matrices,
      warning: this.warning,
      lastEdited: this.lastEdited,
    };
  }

  cmykOpts() {
    return {
      separation: this.settings.separation,
      amount: this.settings.amount,
      ucrStart: this.settings.ucrStart,
    };
  }

  // Пересчёт остальных моделей из RGB. skip - модель, которую редактируют
  // прямо сейчас, её пересчитывать обратно не нужно.
  fromRgb(rgb, skip = null, warning = null) {
    this.rgb = rgb.map((v) => clamp(v, 0, 255));
    if (skip !== 'cmyk') this.cmyk = C.rgbToCmyk(this.rgb, this.cmykOpts());
    if (skip !== 'lab') this.lab = C.rgbToLab(this.rgb, this.matrices);
    if (skip !== 'hsv') this.hsv = C.rgbToHsv(this.rgb);
    this.warning = warning;
    this.notify();
  }

  applyCmyk(cmyk) {
    this.cmyk = cmyk.map((v) => clamp(v, 0, 100));
    this.lastEdited = 'cmyk';
    this.fromRgb(C.cmykToRgb(this.cmyk), 'cmyk');
  }

  applyLab(lab) {
    this.lab = [clamp(lab[0], 0, 100), clamp(lab[1], -128, 127), clamp(lab[2], -128, 127)];
    this.lastEdited = 'lab';
    const r = C.labToRgb(this.lab, this.matrices, this.settings.gamut);
    this.fromRgb(r.rgb, 'lab', r.out ? this.gamutMessage() : null);
  }

  applyHsv(hsv) {
    let h = hsv[0] % 360;
    if (h < 0) h += 360;
    this.hsv = [h, clamp(hsv[1], 0, 100), clamp(hsv[2], 0, 100)];
    this.lastEdited = 'hsv';
    this.fromRgb(C.hsvToRgb(this.hsv), 'hsv');
  }

  setHex(hex) {
    if (!/^#?[0-9a-fA-F]{6}$/.test(hex)) return;
    this.lastEdited = 'rgb';
    this.fromRgb(C.hexToRgb(hex));
  }

  gamutMessage() {
    return this.settings.gamut === 'scale'
      ? 'Цвет выходит за пределы sRGB. Диапазон пропорционально сжат до отображаемого.'
      : 'Цвет выходит за пределы sRGB. Значения каналов обрезаны по границе диапазона.';
  }

  // При смене источника матрицы строятся заново, RGB остаётся прежним
  setIlluminant(key) {
    this.settings.illuminant = key;
    this.matrices = buildMatrices(key, this.settings.adaptation);
    this.fromRgb(this.rgb);
  }

  setAdaptation(method) {
    this.settings.adaptation = method;
    this.matrices = buildMatrices(this.settings.illuminant, method);
    this.fromRgb(this.rgb);
  }

  // Пересчитываем от Lab, иначе разницу между стратегиями не будет видно
  setGamut(strategy) {
    this.settings.gamut = strategy;
    this.applyLab(this.lab);
  }

  setSeparation(kind) {
    this.settings.separation = kind;
    this.fromRgb(this.rgb);
  }

  setAmount(v) {
    this.settings.amount = clamp(v, 0, 1);
    this.fromRgb(this.rgb);
  }

  setUcrStart(v) {
    this.settings.ucrStart = clamp(v, 0, 0.95);
    this.fromRgb(this.rgb);
  }

  // Опорные цвета для фона ползунка: меняется одна компонента, остальные текущие
  sliderGradient(model, index, steps = 12) {
    const out = [];
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      let rgb;
      if (model === 'cmyk') {
        const v = this.cmyk.slice();
        v[index] = t * 100;
        rgb = C.cmykToRgb(v);
      } else if (model === 'lab') {
        const v = this.lab.slice();
        v[index] = index === 0 ? t * 100 : -128 + t * 255;
        rgb = C.labToRgb(v, this.matrices, this.settings.gamut).rgb;
      } else {
        const v = this.hsv.slice();
        v[index] = index === 0 ? t * 360 : t * 100;
        rgb = C.hsvToRgb(v);
      }
      out.push(C.rgbToHex(rgb));
    }
    return out;
  }
}
