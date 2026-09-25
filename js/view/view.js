// Интерфейс: собирает элементы управления, передаёт ввод во ViewModel
// и выводит текущее состояние. Расчётов здесь нет.

import { ColorViewModel } from '../viewmodel/colorViewModel.js';
import { ILLUMINANTS } from '../model/whitepoints.js';
import { drawCieChart } from './cieChart.js';
import { drawCmykPlane, drawLabPlane, drawHsvPlane, drawHueStrip, pickPoint } from './planes.js';

const vm = new ColorViewModel();
const $ = (id) => document.getElementById(id);

const SCHEMA = {
  cmyk: [ {n:'C', min:0,    max:100, step:0.1},
          {n:'M', min:0,    max:100, step:0.1},
          {n:'Y', min:0,    max:100, step:0.1},
          {n:'K', min:0,    max:100, step:0.1} ],
  lab:  [ {n:'L', min:0,    max:100, step:0.1},
          {n:'a', min:-128, max:127, step:0.1},
          {n:'b', min:-128, max:127, step:0.1} ],
  hsv:  [ {n:'H', min:0,    max:360, step:0.1},
          {n:'S', min:0,    max:100, step:0.1},
          {n:'V', min:0,    max:100, step:0.1} ],
};

const APPLY = {
  cmyk: (v) => vm.applyCmyk(v),
  lab:  (v) => vm.applyLab(v),
  hsv:  (v) => vm.applyHsv(v),
};

const controls = {};

function buildControls(model, host) {
  controls[model] = [];
  SCHEMA[model].forEach((c, i) => {
    const row = document.createElement('div');
    row.className = 'control';

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = c.n;

    const range = document.createElement('input');
    range.type = 'range';
    range.min = c.min; range.max = c.max; range.step = c.step;

    const num = document.createElement('input');
    num.type = 'number';
    num.min = c.min; num.max = c.max; num.step = c.step;

    const send = (raw) => {
      const v = parseFloat(raw);
      if (Number.isNaN(v)) return;
      const arr = vm[model].slice();
      arr[i] = v;
      APPLY[model](arr);
    };

    range.addEventListener('input', (e) => send(e.target.value));
    num.addEventListener('input', (e) => send(e.target.value));

    row.append(name, range, num);
    host.append(row);
    controls[model].push({ range, number: num });
  });
}

buildControls('cmyk', $('cmykControls'));
buildControls('lab', $('labControls'));
buildControls('hsv', $('hsvControls'));

$('illuminant').addEventListener('change', (e) => vm.setIlluminant(e.target.value));
$('adaptation').addEventListener('change', (e) => vm.setAdaptation(e.target.value));
$('gamut').addEventListener('change', (e) => vm.setGamut(e.target.value));
$('separation').addEventListener('change', (e) => vm.setSeparation(e.target.value));
$('amount').addEventListener('input', (e) => vm.setAmount(e.target.value / 100));
$('ucrStart').addEventListener('input', (e) => vm.setUcrStart(e.target.value / 100));
$('picker').addEventListener('input', (e) => vm.setHex(e.target.value));
$('hex').addEventListener('input', (e) => vm.setHex(e.target.value.trim()));

function bindPlane(id, handler) {
  const canvas = $(id);
  let down = false;
  const act = (e) => handler(pickPoint(canvas, e));
  canvas.addEventListener('pointerdown', (e) => { down = true; canvas.setPointerCapture(e.pointerId); act(e); });
  canvas.addEventListener('pointermove', (e) => { if (down) act(e); });
  canvas.addEventListener('pointerup', () => { down = false; });
}

bindPlane('cmykPlane', ({ u, v }) => vm.applyCmyk([u * 100, (1 - v) * 100, vm.cmyk[2], vm.cmyk[3]]));
bindPlane('labPlane', ({ u, v }) => vm.applyLab([vm.lab[0], -128 + u * 255, -128 + v * 255]));
bindPlane('hsvPlane', ({ u, v }) => vm.applyHsv([vm.hsv[0], u * 100, v * 100]));
bindPlane('huePlane', ({ u }) => vm.applyHsv([u * 360, vm.hsv[1], vm.hsv[2]]));

function fillControls(model, values) {
  controls[model].forEach((c, i) => {
    const v = values[i];
    // поле, в котором сейчас печатают, не трогаем, иначе сбивается ввод
    if (document.activeElement !== c.range) c.range.value = v;
    if (document.activeElement !== c.number) c.number.value = v.toFixed(1);
    c.range.style.background = 'linear-gradient(to right,' + vm.sliderGradient(model, i).join(',') + ')';
  });
}

function fillMatrix(table, m) {
  table.innerHTML = m
    .map((row) => '<tr>' + row.map((v) => '<td>' + v.toFixed(6) + '</td>').join('') + '</tr>')
    .join('');
}

let pending = false;

function render(state) {
  fillControls('cmyk', state.cmyk);
  fillControls('lab', state.lab);
  fillControls('hsv', state.hsv);

  $('preview').style.background = state.hex;
  if (document.activeElement !== $('hex')) $('hex').value = state.hex;
  $('picker').value = state.hex;
  $('rgbOut').textContent = state.rgb.map((v) => Math.round(v)).join('   ');
  $('xyzOut').textContent = state.xyz.map((v) => v.toFixed(2)).join('   ');

  const s = state.xyz[0] + state.xyz[1] + state.xyz[2];
  $('xyOut').textContent = s > 0
    ? (state.xyz[0] / s).toFixed(4) + '   ' + (state.xyz[1] / s).toFixed(4)
    : '—';

  const warn = $('warning');
  warn.hidden = !state.warning;
  warn.textContent = state.warning || '';

  $('illuminant').value = state.settings.illuminant;
  $('adaptation').value = state.settings.adaptation;
  $('gamut').value = state.settings.gamut;
  $('separation').value = state.settings.separation;
  $('amountVal').textContent = Math.round(state.settings.amount * 100) + '%';
  $('ucrStartVal').textContent = Math.round(state.settings.ucrStart * 100) + '%';
  $('ucrStartField').style.opacity = state.settings.separation === 'ucr' ? 1 : 0.4;

  $('illName').textContent = ILLUMINANTS[state.settings.illuminant].name.split(' —')[0];
  fillMatrix($('mFwd'), state.matrices.rgbToXyz);
  fillMatrix($('mInv'), state.matrices.xyzToRgb);
  $('wpOut').textContent = 'Xw, Yw, Zw = ' + state.matrices.whiteXYZ100.map((v) => v.toFixed(3)).join(', ');

  // палитры и график перерисовываем не чаще кадра, иначе ползунки тормозят
  if (!pending) {
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      drawCmykPlane($('cmykPlane'), state);
      drawLabPlane($('labPlane'), state, state.matrices, state.settings.gamut);
      drawHueStrip($('huePlane'), state);
      drawHsvPlane($('hsvPlane'), state);
      drawCieChart($('cieChart'), state);
    });
  }
}

vm.subscribe(render);
