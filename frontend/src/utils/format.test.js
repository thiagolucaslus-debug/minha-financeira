import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildCardSurfaceStyle,
  formatBRL,
  formatCompetenciaFull,
  formatDateBR,
  getContrastTextForHex,
  getUrgencyMeta,
  parseHexColor,
  shiftCompetencia,
} from './format.js';

test('formatBRL formats positive, negative and zero values cleanly', () => {
  assert.match(formatBRL(100), /R\$\s*100,00/);
  assert.match(formatBRL(1234.56), /R\$\s*1\.234,56/);
  assert.match(formatBRL(0), /R\$\s*0,00/);
  assert.match(formatBRL(-20), /-R\$\s*20,00/);
});

test('shiftCompetencia handles year rollovers cleanly', () => {
  assert.equal(shiftCompetencia('2026-12', 1), '2027-01');
  assert.equal(shiftCompetencia('2026-01', -1), '2025-12');
  assert.equal(shiftCompetencia('2026-05', 3), '2026-08');
  assert.equal(formatCompetenciaFull('2026-05'), 'Maio 2026');
  assert.equal(formatDateBR('2026-05-18'), '18/05/2026');
});

test('card color engine respects chosen indicator hex and picks WCAG contrast text', () => {
  assert.equal(parseHexColor('#a855f7'), '#A855F7');
  assert.equal(parseHexColor('invalid', '#C9A45C'), '#C9A45C');
  assert.equal(getContrastTextForHex('#111827'), '#FFFFFF');
  assert.equal(getContrastTextForHex('#FDE047'), '#0B0E14');

  const style = buildCardSurfaceStyle('#7C3AED');
  assert.ok(style.background.includes('#7C3AED'));
  assert.equal(style.color, '#FFFFFF');
});

test('getUrgencyMeta returns accurate countdown labels for all radar states', () => {
  assert.equal(getUrgencyMeta('atrasado', -3).countdown, '3 dias em atraso');
  assert.equal(getUrgencyMeta('vence_hoje', 0).countdown, 'Vence hoje');
  assert.equal(getUrgencyMeta('proximos_7_dias', 1).countdown, 'Vence amanhã');
  assert.equal(getUrgencyMeta('proximos_15_dias', 12).countdown, 'Em 12 dias');
  assert.equal(getUrgencyMeta('pago', 5).countdown, 'Quitado');
});
