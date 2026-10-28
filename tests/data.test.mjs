import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {latestObservation, changeAt, inRange, parseRoute, formatChange, summaryStatistics} from '../site/assets/data.js';

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

test('summary statistics use fixed trailing windows, skip gaps and retain zeros', () => {
  const points = [
    {date:'2025-02-28',value:1000},
    {date:'2025-03-31',value:10},
    {date:'2025-12-30',value:100},
    {date:'2025-12-31',value:0},
    {date:'2026-01-31',value:null},
    {date:'2026-02-28',value:10},
    {date:'2026-03-31',value:20},
    {date:'2026-04-07',value:null},
  ];
  const stats = summaryStatistics(points, points.slice(-2));
  assert.deepEqual(stats.average3m, {value:10,count:3});
  assert.deepEqual(stats.average1y, {value:28,count:5});
  assert.deepEqual(stats.percentile, {value:100,count:1});
  assert.equal(summaryStatistics(points).percentile.count, 6);
  assert.ok(Math.abs(summaryStatistics(points).percentile.value - 4 / 6 * 100) < 1e-10);
});

test('summary windows clamp month ends and leap days to calendar dates', () => {
  const points = [
    {date:'2023-02-27',value:1000},
    {date:'2023-02-28',value:10},
    {date:'2023-11-29',value:100},
    {date:'2024-02-29',value:20},
  ];
  assert.deepEqual(summaryStatistics(points).average1y, {value:130 / 3,count:3});
  const monthEnd = [
    {date:'2025-02-27',value:1000},
    {date:'2025-02-28',value:10},
    {date:'2025-05-31',value:20},
  ];
  assert.deepEqual(summaryStatistics(monthEnd).average3m, {value:15,count:2});
});

test('percentile includes tied current values, is range-aware and handles no valid history', () => {
  const points = [
    {date:'2026-01-01',value:0},
    {date:'2026-01-08',value:10},
    {date:'2026-01-15',value:20},
    {date:'2026-01-22',value:null},
    {date:'2026-01-29',value:10},
  ];
  assert.deepEqual(summaryStatistics(points).percentile, {value:75,count:4});
  assert.deepEqual(summaryStatistics(points, points.slice(1)).percentile, {value:2 / 3 * 100,count:3});
  assert.deepEqual(summaryStatistics(points, []).percentile, {value:null,count:0});
  assert.deepEqual(summaryStatistics([{date:'2026-01-01',value:null}]), {
    average3m:{value:null,count:0}, average1y:{value:null,count:0}, percentile:{value:null,count:0},
  });
});

console.log(`${results.length} JavaScript regression checks passed`);
