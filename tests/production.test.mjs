import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {changeAt, comparisonLabel, comparisonPeriods, displayCatalog, emptyChartLabel, formatChange,
  inRange, parseRoute, seriesLabel, summaryStatistics, unpackDataset} from '../site/assets/data.js';
import {setDataMode, t} from '../site/assets/zh-CN.js';

export const results = [];
function test(name, verify) { verify(); results.push({name, passed: true}); }
const catalog = JSON.parse(readFileSync(new URL('../dist/data/catalog.json', import.meta.url)));
const payload = JSON.parse(readFileSync(new URL('../dist/data/observations.json', import.meta.url)));
assert.equal(catalog.dataset.mode, 'production', 'Run assemble.py and build.py --mode production first');
const display = displayCatalog(catalog);
const daily = display.indicators.find(item => item.seriesId === 'sofr-effr-spread');
const weekly = display.indicators.find(item => item.seriesId === 'fed-assets');
const point = (date, value) => ({date, value});

test('expanded production preserves quarterly and manual policies and deferred gaps', () => {
  const lending = display.indicators.find(item => item.seriesId === 'lending-standards');
  assert.equal(lending.observationDateRule, 'quarter-start');
  assert.equal(comparisonLabel(lending, 1), '较上季度变化');
  assert.equal(changeAt([point('2026-07-01', -5), point('2026-10-01', 0)], 1, lending), 5);
  const issuance = display.indicators.find(item => item.seriesId === 'bond-issuance');
  assert.equal(issuance.observationDateRule, 'month-end');
  assert.match(issuance.source.name, /G1132499/);
  assert.equal(changeAt([point('2024-02-29', 100), point('2024-03-31', 120)], 1, issuance), 20);
  const ratio = catalog.indicators.find(item => item.seriesId === 'reserve-assets-ratio');
  assert.match(ratio.explanation, /季调/);
  assert.match(ratio.source.name, /项目计算/);
  for (const key of ['bid-ask-spread', 'price-impact']) {
    assert.equal(catalog.indicators.find(item => item.seriesId === key).inputAvailable, false);
    assert.deepEqual(payload.series[key], []);
  }
  assert.ok(!Object.hasOwn(payload.series, 'treasury-yield-chg'));
});

test('credit spreads display both ICE OAS series with daily source dates', () => {
  for (const key of ['credit-spreads-ig', 'credit-spreads-hy']) {
    const spread = display.indicators.find(item => item.seriesId === key);
    assert.equal(spread.nativeFrequency, 'daily');
    assert.equal(spread.observationDateRule, 'source-daily-close');
    assert.equal(comparisonLabel(spread, 4), '近4周变化');
    assert.ok(payload.series[key].length > 0);
    assert.match(spread.notices.map(notice => notice.text).join(' '), /ICE Data Indices/);
  }
});

test('VIX displays as an index level with Cboe attribution', () => {
  const vix = display.indicators.find(item => item.seriesId === 'vix');
  assert.equal(vix.nativeFrequency, 'daily');
  assert.equal(vix.observationDateRule, 'source-daily-close');
  assert.equal(vix.unit.label, '点');
  assert.equal(comparisonLabel(vix, 13), '近13周变化');
  assert.ok(payload.series.vix.length > 0);
  assert.match(vix.notices.map(notice => notice.text).join(' '), /Cboe/);
});

test('daily comparison uses calendar weeks, seven-day limit, explicit nulls and zero', () => {
  const latest = point('2026-11-16', 5); // Four weeks earlier: Monday October 19.
  assert.equal(changeAt([point('2026-10-16', 0), latest], 4, daily), 5);
  assert.equal(changeAt([point('2026-10-12', 3), latest], 4, daily), 2);
  assert.equal(changeAt([point('2026-10-11', 3), latest], 4, daily), null);
  assert.equal(changeAt([point('2026-10-16', 3), point('2026-10-19', null), latest], 4, daily), null);
  assert.equal(changeAt([point('2026-10-16', 3), point('2026-10-18', null), latest], 4, daily), 2);
  assert.equal(changeAt([point('2026-10-20', 3), latest], 4, daily), null);
  assert.equal(changeAt([point('2026-10-19', 4.9), latest], 4, daily).toFixed(1), '0.1');
  assert.equal(formatChange(10, daily), '+10.00 bp');
});
test('weekly matching stays exact and bp values never scale twice', () => {
  assert.equal(changeAt([point('2026-10-13', 1), point('2026-11-11', 5)], 4, weekly), null);
  assert.equal(changeAt([point('2026-10-14', 1), point('2026-11-11', 5)], 4, weekly), 4);
  const bp = {...daily, unit: {kind: 'spread', label: 'bp', precision: 2}};
  assert.equal(changeAt([point('2026-10-19', 10), point('2026-11-16', 15)], 4, bp), 5);
  assert.equal(formatChange(5, bp), '+5.00 bp');
});
const monthly = display.indicators.find(item => item.seriesId === 'bond-issuance');
const quarterly = {...monthly, nativeFrequency: 'quarterly', observationDateRule: 'quarter-start',
  comparisonPolicy: {periods: [1, 4], periodUnit: 'quarter', match: 'source-period-date', valueScale: 1}};
test('monthly and quarterly policies preserve reviewed source dates', () => {
  assert.deepEqual(comparisonPeriods(monthly), [1, 12]);
  assert.equal(comparisonLabel(monthly, 12), '较上年同月变化');
  const leapMonth = [point('2023-02-28', 5), point('2024-01-31', 0), point('2024-02-29', 20), point('2024-03-31', null)];
  assert.equal(changeAt(leapMonth, 1, monthly), 20);
  assert.equal(changeAt(leapMonth, 12, monthly), 15);
  assert.equal(changeAt([point('2024-02-29', null), point('2024-03-31', 5)], 1, monthly), null);
  assert.equal(changeAt([point('2024-02-29', 2), point('2024-03-31', 5)], 1, monthly), 3);
  assert.equal(changeAt([point('2024-01-31', 2), point('2024-03-31', 5)], 1, monthly), null);
  assert.equal(changeAt([point('2024-01-01', 2), point('2024-04-01', 5)], 1, quarterly), 3);
  assert.equal(changeAt([point('2023-04-01', 2), point('2024-04-01', 5)], 4, quarterly), 3);
  assert.equal(changeAt([point('2024-06-30', 2), point('2024-09-30', 5)], 1,
    {...quarterly, observationDateRule: 'quarter-end'}), 3);
  assert.equal(changeAt([point('2024-01-28', 2), point('2024-02-28', 5)], 1,
    {...monthly, observationDateRule: 'day-of-month'}), 3);
  assert.equal(comparisonLabel(quarterly, 4), '较上年同季变化');
  assert.equal(changeAt([point('2024-01-31', 2), point('2024-02-29', 5)], 1,
    {...monthly, observationDateRule: null}), null);
  const irregular = {...daily, comparisonPolicy: {periods: [], match: 'none', valueScale: 1}};
  assert.deepEqual(comparisonPeriods(irregular), []);
  assert.equal(changeAt([point('2026-10-19', 2), point('2026-11-16', 5)], 4, irregular), null);
});
test('empty, all-null and single-point histories retain actual sample counts', () => {
  const points = [point('2026-08-16', 2), point('2026-10-19', null), point('2026-11-16', 0)];
  const stats = summaryStatistics(points, []);
  assert.deepEqual(stats.average3m, {value: 1, count: 2});
  assert.deepEqual(stats.percentile, {value: null, count: 0});
  assert.equal(summaryStatistics([point('2026-11-16', 0)]).percentile.value, 100);
  assert.equal(summaryStatistics([point('2026-11-16', null)]).average1y.count, 0);
  assert.deepEqual(inRange([point('2024-01-01', 0)], 'ytd', catalog.dataset.observationEnd), []);
  assert.match(emptyChartLabel({...daily, inputAvailable: false}), /待接入/);
  assert.match(emptyChartLabel(daily), /所选区间/);
});
test('production loader rejects mismatched IDs, modes, dates and comparison policies', () => {
  assert.equal(unpackDataset(catalog, payload), payload.series);
  for (const patch of [{schemaVersion: 1}, {snapshotId: 'other'}, {series: {}}]) {
    assert.throws(() => unpackDataset(catalog, {...payload, ...patch}));
  }
  for (const date of ['2026-02-30', '2026-1-01']) {
    const bad = structuredClone(payload); bad.series[daily.id][0].date = date;
    assert.throws(() => unpackDataset(catalog, bad));
  }
  for (const value of [NaN, Infinity, false, '1']) {
    const bad = structuredClone(payload); bad.series[daily.id][0].value = value;
    assert.throws(() => unpackDataset(catalog, bad));
  }
  const bad = structuredClone(catalog);
  bad.indicators.find(item => item.id === daily.id).comparisonPolicy.valueScale = 100;
  assert.throws(() => unpackDataset(bad, payload));
  const retiredDataset = {...catalog.dataset, mode: 'manual-preview', sourceReview: 'pending'};
  assert.throws(() => unpackDataset({...catalog, dataset: retiredDataset}, payload), /Unsupported dataset/);
  assert.throws(() => unpackDataset({...catalog, dataset: {...catalog.dataset, observationEnd: '2030-01-01'}}, payload));
  assert.equal(parseRoute('#indicator=sofr-effr-spread&range=all', catalog.categories, catalog.indicators).category, daily.categoryId);
});
test('production labels identify source and publisher without synthetic wording', () => {
  setDataMode('production');
  assert.doesNotMatch(t('methodologyBody'), /合成|演示/);
  assert.match(t('footerNote'), /Junyan Liu/);
  assert.match(seriesLabel(daily), /NY Fed.*FRED/);
  assert.doesNotMatch(seriesLabel(daily), /SIFMA/);
  setDataMode('demo');
  assert.match(t('methodologyBody'), /合成/);
});

// Render the actual app with DOM/chart doubles. Real browser/layout QA is separate.
const globals = ['document', 'window', 'location', 'fetch', 'ResizeObserver'];
const saved = new Map(globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
try {
  const nodes = new Map(), handlers = {}, charts = new Map(), requests = [];
  function node(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {
      innerHTML: '', textContent: '', hidden: false, open: false, dataset: {},
      classList: {add() {}, remove() {}}, setAttribute() {}, contains: () => true, focus() {},
      addEventListener(type, handler) { handlers[`${selector}:${type}`] = handler; },
      showModal() { this.open = true; }, close() { this.open = false; },
    });
    return nodes.get(selector);
  }
  const labels = [...readFileSync(new URL('../site/index.html', import.meta.url), 'utf8').matchAll(/data-i18n="([^"]+)"/g)]
    .map(match => ({dataset: {i18n: match[1]}, textContent: ''}));
  globalThis.document = {querySelector: node, querySelectorAll: selector => selector === '[data-i18n]' ? labels : [],
    body: node('body'), activeElement: node('active')};
  globalThis.location = {hash: '#indicator=sofr-effr-spread&range=all'};
  globalThis.window = {addEventListener: (type, handler) => { handlers[type] = handler; },
    matchMedia: () => ({matches: true}), echarts: {init: element => ({
      setOption: option => charts.set(element, option), dispose() {}, resize() {},
    })}};
  globalThis.ResizeObserver = class {observe() {} unobserve() {}};
  globalThis.fetch = async address => {
    requests.push(String(address));
    return {ok: true, json: async () => String(address).endsWith('catalog.json') ? catalog : payload};
  };
  await import('../site/assets/app.js?production-test');
  await new Promise(resolve => setTimeout(resolve, 0));
  test('production app renders deep-linked chart, sources, notices and native values', () => {
    assert.equal(node('#status').textContent, '');
    assert.equal(node('#indicator-dialog').open, true);
    assert.match(node('#dialog-content').innerHTML, /Junyan Liu.*not affiliated/);
    assert.match(node('#dialog-content').innerHTML, /DTCC Solutions/);
    assert.match(node('#charts').innerHTML, /数据来源：NY Fed \/ FRED · 项目计算<\/p>/);
    assert.doesNotMatch(node('#charts').innerHTML, /source-notices|DTCC Solutions/);
    assert.match(node('#charts').innerHTML, /近4周变化/);
    assert.ok(labels.every(label => !/合成|演示|SIFMA 数据预览|定义待复核/.test(label.textContent)));
    assert.match(labels.find(label => label.dataset.i18n === 'methodologyBody').textContent, /SIFMA/);
    assert.doesNotMatch(node('#dialog-content').innerHTML, /最近检查|人工录入时间|自动更新|人工维护|生成时间/);
    assert.equal(node('#collection-time').hidden, true);
    const chart = charts.get(node('#expanded-chart'));
    assert.deepEqual(chart.series[0].data.map(point => point[1]), payload.series[daily.id].map(point => point.value));
    assert.equal(chart.series[0].connectNulls, false);
    assert.doesNotMatch(chart.tooltip.formatter([{value: chart.series[0].data.at(-2)}]), /FRED|NY Fed|项目计算/);
    assert.ok(requests.every(address => address.endsWith('/site/data/catalog.json') || address.endsWith('/site/data/observations.json')));
    const source = readFileSync(new URL('../dist/assets/app.js', import.meta.url), 'utf8');
    assert.match(source, /new URL\(`\.\.\/data\/\$\{name\}\.json`, import.meta.url\)/);
  });
  test('expanded range applies only until the dialog closes', () => {
    const pageChart = charts.get(node(`#chart-${daily.id}`));
    const originalHash = location.hash;
    const button = {dataset: {range: 'ytd'}, getAttribute: () => 'false'};
    handlers['#dialog-content:click']({target: {closest: () => button}});
    assert.match(node('#dialog-content').innerHTML, /data-range="ytd" aria-pressed="true"/);
    assert.match(node('#ranges').innerHTML, /data-range="all" aria-pressed="true"/);
    assert.equal(charts.get(node(`#chart-${daily.id}`)), pageChart);
    assert.equal(location.hash, originalHash);
    assert.ok(charts.get(node('#expanded-chart')).series[0].data.length < pageChart.series[0].data.length);
    handlers['#close-dialog:click']();
    handlers.hashchange();
    location.hash = originalHash;
    handlers.hashchange();
    assert.match(node('#dialog-content').innerHTML, /data-range="all" aria-pressed="true"/);
  });
  test('production dialogs handle single points, empty ranges and keyboard cancellation', () => {
    payload.series[daily.id] = [point('2024-02-29', 0)];
    location.hash = '#indicator=sofr-effr-spread&range=5y'; handlers.hashchange();
    const chart = charts.get(node('#expanded-chart'));
    assert.equal(chart.series[0].showSymbol, true);
    assert.ok(chart.xAxis.min < chart.xAxis.max);
    location.hash = '#indicator=sofr-effr-spread&range=ytd'; handlers.hashchange();
    assert.match(node('#expanded-chart').textContent, /所选区间/);
    location.hash = '#indicator=dollar-index&range=all'; handlers.hashchange();
    assert.match(node('#dialog-content').innerHTML, /待接入/);
    assert.match(node('#expanded-chart').textContent, /待接入/);
    let prevented = false;
    handlers['#indicator-dialog:cancel']({preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
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
console.log(`${results.length} production checks passed`);
