import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {latestObservation, changeAt, inRange, parseRoute, formatChange} from '../site/assets/data.js';

// Also importable in a persistent Node REPL without spawning a test subprocess.
export const results = [];
function test(name, verify) { verify(); results.push({name, passed: true}); }

const catalog = JSON.parse(readFileSync(new URL('../site/data/catalog.json', import.meta.url)));
const fixtures = JSON.parse(readFileSync(new URL('../site/data/observations.json', import.meta.url)));

test('native changes use the exact calendar week, including zero', () => {
  const indicator = catalog.indicators[0];
  const data = [{date:'2026-09-30',value:0}, {date:'2026-10-28',value:15}];
  assert.equal(changeAt(data, 4, indicator), 15);
  assert.equal(changeAt([{date:'2026-09-30',value:15}, data[1]], 4, indicator), 0);
  assert.equal(changeAt(data, 13, indicator), null);
});

test('rate changes convert percentage points to basis points', () => {
  const rate = catalog.indicators.find(item => item.id === 'sofr');
  const points = [{date:'2026-09-30',value:4}, {date:'2026-10-28',value:4.25}];
  assert.equal(changeAt(points, 4, rate), 25);
  assert.equal(formatChange(25, rate), '+25.0 bp');
  assert.equal(formatChange(null, rate), '—');
});

test('missing comparison and latest data are never treated as zero', () => {
  const reverse = catalog.indicators.find(item => item.id === 'reverse-repo');
  assert.equal(changeAt(fixtures[reverse.id], 4, reverse), null);
  const latest = latestObservation(fixtures['dealer-positions']);
  assert.equal(latest.date, '2026-10-21');
  assert.equal(latestObservation([{date:'2026-10-28',value:null}]), null);
});

test('all fixture metrics match independent dated comparisons', () => {
  for (const indicator of catalog.indicators) {
    const points = fixtures[indicator.id];
    const latest = [...points].reverse().find(point => point.value !== null);
    for (const weeks of [4, 13]) {
      const target = new Date(latest.date + 'T00:00:00Z');
      target.setUTCDate(target.getUTCDate() - weeks * 7);
      const prior = points.find(point => point.date === target.toISOString().slice(0, 10));
      const expected = !prior || prior.value === null ? null : (latest.value - prior.value) * (indicator.unit.kind === 'rate' ? 100 : 1);
      assert.equal(changeAt(points, weeks, indicator), expected);
    }
  }
});

test('calendar ranges use dataset end, preserve nulls and differ from all', () => {
  const points = fixtures['reserve-balances'];
  const year = inRange(points, '1y', catalog.dataset.observationEnd);
  assert.equal(year.length, 53);
  assert.equal(inRange(points, '5y', catalog.dataset.observationEnd).length, 261);
  assert.equal(inRange(points, 'all', catalog.dataset.observationEnd).length, 262);
  assert.ok(inRange(points, 'all').some(point => point.value === null));
  assert.equal(points.length, 262);
  const ytd = inRange(points, 'ytd', catalog.dataset.observationEnd);
  assert.equal(ytd.length, 43);
  assert.equal(ytd[0].date, '2026-01-07');
  assert.equal(ytd.at(-1).date, catalog.dataset.observationEnd);
  assert.deepEqual(inRange([
    {date:'2023-12-31',value:1},
    {date:'2024-01-01',value:null},
    {date:'2024-02-29',value:0},
  ], 'ytd', '2024-02-29'), [
    {date:'2024-01-01',value:null},
    {date:'2024-02-29',value:0},
  ]);
});

test('deep links and malformed hashes resolve to safe valid state', () => {
  const parse = hash => parseRoute(hash, catalog.categories, catalog.indicators);
  assert.deepEqual(parse(''), {category:'category-1',range:'5y',indicator:null});
  assert.deepEqual(parse('#category=invalid&range=bad&indicator=bad'), parse(''));
  assert.deepEqual(parse('#indicator=sofr&range=1y'), {category:'category-2',range:'1y',indicator:'sofr'});
  assert.deepEqual(parse('#indicator=sofr&range=ytd'), {category:'category-2',range:'ytd',indicator:'sofr'});
  assert.equal(parse('#methodology').category, 'category-1');
});

console.log(`${results.length} JavaScript regression checks passed`);
