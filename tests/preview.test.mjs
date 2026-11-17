import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {changeAt, inRange, summaryStatistics, parseRoute, unpackDataset, comparisonLabel,
  comparisonPeriods, frequencyLabel, emptyChartLabel} from '../site/assets/data.js';
import {setDataMode, t} from '../site/assets/zh-CN.js';

// Run build.py --mode preview first. These checks also run in the Node REPL.
export const results = [];
function test(name, verify) { verify(); results.push({name, passed: true}); }
const catalog = JSON.parse(readFileSync(new URL('../dist-preview/data/catalog.json', import.meta.url)));
const documentData = JSON.parse(readFileSync(new URL('../dist-preview/data/observations.json', import.meta.url)));
const monthly = catalog.indicators.find(item => item.seriesId === 'bond-issuance');
const points = [
  {date: '2023-02-28', value: 5}, {date: '2024-01-31', value: 0},
  {date: '2024-02-29', value: 20}, {date: '2024-03-31', value: null},
];
test('monthly comparisons preserve leap month ends and true zeroes', () => {
  assert.equal(changeAt(points, 1, monthly), 20);
  assert.equal(changeAt(points, 12, monthly), 15);
  assert.equal(changeAt([{date: '2024-02-29', value: 3}, {date: '2024-03-31', value: 4}], 1, monthly), 1);
  assert.equal(comparisonLabel(monthly, 12), '较上年同月变化');
  assert.deepEqual(comparisonPeriods(monthly), [1, 12]);
  assert.equal(frequencyLabel('monthly'), '每月');
});
test('missing months never fall back to earlier or explicitly missing values', () => {
  assert.equal(changeAt([{date: '2024-01-31', value: 3}, {date: '2024-03-31', value: 4}], 1, monthly), null);
  assert.equal(changeAt([{date: '2024-02-29', value: null}, {date: '2024-03-31', value: 4}], 1, monthly), null);
  assert.equal(changeAt([], 1, monthly), null);
});
test('native observation statistics count actual samples and empty ranges', () => {
  const statistics = summaryStatistics(points, []);
  assert.deepEqual(statistics.average3m, {value: 10, count: 2});
  assert.deepEqual(statistics.percentile, {value: null, count: 0});
  assert.deepEqual(inRange([], '1y', null), []);
  assert.deepEqual(inRange(points, 'ytd', '2025-01-01'), []);
  assert.equal(summaryStatistics([{date: '2024-02-29', value: 0}]).percentile.value, 100);
});
test('preview opens credit category and preserves deep links', () => {
  assert.equal(parseRoute('', catalog.categories, catalog.indicators).category, monthly.categoryId);
  assert.equal(parseRoute('#indicator=fed-assets&range=all', catalog.categories, catalog.indicators).indicator, 'fed-assets');
});
test('loader checks mode snapshot identity and series ownership', () => {
  assert.equal(unpackDataset(catalog, documentData), documentData.series);
  assert.throws(() => unpackDataset({schemaVersion: 1, dataset: {isDemo: true}}, documentData));
  for (const patch of [{schemaVersion: 1}, {snapshotId: 'other'}, {series: {}}]) {
    assert.throws(() => unpackDataset(catalog, {...documentData, ...patch}));
  }
  for (const value of [NaN, Infinity, '1', false]) {
    const broken = structuredClone(documentData);
    broken.series[monthly.id][0].value = value;
    assert.throws(() => unpackDataset(catalog, broken));
  }
  const broken = structuredClone(documentData);
  broken.series['fed-assets'] = [{date: '2024-02-29', value: 1}];
  assert.throws(() => unpackDataset(catalog, broken));
  assert.throws(() => unpackDataset({...catalog, dataset: {...catalog.dataset, mode: 'production'}}, documentData));
});
test('pending review labels and distinct empty states are explicit', () => {
  setDataMode('manual-preview');
  assert.match(t('demoBadge'), /定义待复核/);
  assert.doesNotMatch(t('methodologyBody'), /合成/);
  assert.match(emptyChartLabel(monthly), /所选区间/);
  assert.match(emptyChartLabel(catalog.indicators.find(item => item.id === 'fed-assets')), /待接入/);
  assert.match(emptyChartLabel({...monthly, unit: {kind: 'unquantified'}}), /数值定义/);
  setDataMode('demo');
  assert.match(t('demoBadge'), /演示/);
});

// Exercise actual app render functions with lightweight DOM/chart test doubles.
// This is not a browser/layout test: it verifies generated markup and chart data.
const globals = ['document', 'window', 'location', 'fetch', 'ResizeObserver'];
const saved = new Map(globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
try {
  const nodes = new Map(), handlers = {}, charts = new Map();
  function node(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {
      innerHTML: '', textContent: '', hidden: false, open: false,
      dataset: {}, classList: {add() {}, remove() {}}, setAttribute() {},
      contains: () => true, focus() {},
      addEventListener(type, handler) { handlers[`${selector}:${type}`] = handler; },
      showModal() { this.open = true; }, close() { this.open = false; },
    });
    return nodes.get(selector);
  }
  const labels = [...readFileSync(new URL('../site/index.html', import.meta.url), 'utf8').matchAll(/data-i18n="([^"]+)"/g)]
    .map(match => ({dataset: {i18n: match[1]}, textContent: ''}));
  globalThis.document = {querySelector: node, querySelectorAll: selector => selector === '[data-i18n]' ? labels : [],
    body: node('body'), activeElement: node('active')};
  globalThis.location = {hash: ''};
  globalThis.window = {addEventListener: (type, handler) => { handlers[type] = handler; },
    matchMedia: () => ({matches: true}), echarts: {init: element => ({
      setOption: option => charts.set(element, option), dispose() {}, resize() {},
    })}};
  globalThis.ResizeObserver = class {observe() {} unobserve() {}};
  const payload = structuredClone(documentData);
  globalThis.fetch = async url => ({ok: true, json: async () => String(url).endsWith('catalog.json') ? catalog : payload});
  await import('../site/assets/app.js');
  await new Promise(resolve => setTimeout(resolve, 0));
  test('app renders real monthly cards first without synthetic labels', () => {
    assert.equal(node('#status').textContent, '');
    const markup = node('#charts').innerHTML;
    assert.match(markup, /较上月变化/);
    assert.match(markup, /较上年同月变化/);
    assert.doesNotMatch(markup, /合成|近4周|近13周|自动更新|人工维护/);
    assert.ok(markup.indexOf('heading-bond-issuance') < markup.indexOf('heading-credit-spreads-ig'));
    assert.ok(labels.some(label => label.textContent.includes('定义待复核')));
    assert.ok(labels.every(label => !/合成|演示/.test(label.textContent)));
    assert.equal(node('#collection-time').hidden, true);
    const chart = charts.get(node('#chart-bond-issuance'));
    assert.deepEqual(chart.series[0].data.map(point => point[1]), payload.series['bond-issuance'].slice(-61).map(point => point.value));
  });
  test('empty dialog and short histories render without exceptions', () => {
    location.hash = '#indicator=fed-assets&range=all';
    handlers.hashchange();
    assert.equal(node('#indicator-dialog').open, true);
    assert.match(node('#dialog-content').innerHTML, /待接入/);
    assert.match(node('#expanded-chart').textContent, /待接入/);
    payload.series['bond-issuance'] = [{date: '2024-02-29', value: 0}];
    location.hash = '#indicator=bond-issuance&range=all';
    handlers.hashchange();
    assert.match(node('#dialog-content').innerHTML, /SIFMA/);
    assert.doesNotMatch(node('#dialog-content').innerHTML, /合成|生成时间/);
    const chart = charts.get(node('#expanded-chart'));
    assert.equal(chart.series[0].showSymbol, true);
    assert.ok(chart.xAxis.min < chart.xAxis.max);
    location.hash = '#indicator=bond-issuance&range=ytd';
    handlers.hashchange();
    assert.match(node('#expanded-chart').textContent, /所选区间/);
    location.hash = '#category=category-3&range=all';
    handlers.hashchange();
    assert.equal(node('#indicator-dialog').open, false);
  });
} finally {
  for (const [key, descriptor] of saved) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
  setDataMode('demo');
}
console.log(`${results.length} preview checks passed`);
