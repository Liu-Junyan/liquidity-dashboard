import {t} from './zh-CN.js';
import {latestObservation, changeAt, inRange, formatNumber, formatDate, formatChange, parseRoute, frequencyLabel, summaryStatistics} from './data.js';
import {drawChart, disposeCharts} from './charts.js';

const $ = selector => document.querySelector(selector);
const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
document.querySelectorAll('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
document.querySelectorAll('[data-i18n-aria-label]').forEach(element => { element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel)); });
const status = $('#status');
const dialog = $('#indicator-dialog');
let catalog, observations, categories, state, dialogTrigger;
const rangesByCategory = new Map();
const statisticsOpen = new Set();
let renderedCategory, renderedRange, renderedIndicator;

function navigate(patch) {
  const next = {...state, ...patch};
  const params = new URLSearchParams({category: next.category, range: next.range});
  if (next.indicator) params.set('indicator', next.indicator);
  location.hash = params.toString();
}
function pointsFor(indicator) { return inRange(observations[indicator.id], state.range, catalog.dataset.observationEnd); }
function secondarySummary(indicator, primaryDate) {
  const latest = latestObservation(observations[indicator.id]);
  const date = latest?.date !== primaryDate ? `<span class="secondary-date">${t('observationDate')} ${formatDate(latest?.date)}</span>` : '';
  return `${escape(indicator.name)}<strong>${formatNumber(latest?.value, indicator.unit.precision)} <small>${escape(indicator.unit.label)}</small>${date}</strong>`;
}
function metrics(indicator) {
  if (indicator.unit.kind === 'unquantified') return `<p class="definition-pending">${t('definitionPending')}</p>`;
  const points = observations[indicator.id];
  const latest = latestObservation(points);
  return `<div class="indicator-metrics"><div class="latest-value"><span class="metric-label">${t('latest')}</span><strong>${formatNumber(latest?.value, indicator.unit.precision)}<small>${escape(indicator.unit.label)}</small></strong></div><div><span class="metric-label">${t('change4')}</span><span class="metric-change">${formatChange(changeAt(points, 4, indicator), indicator)}</span></div><div><span class="metric-label">${t('change13')}</span><span class="metric-change">${formatChange(changeAt(points, 13, indicator), indicator)}</span></div></div><p class="observation-date">${t('observationDate')}：${formatDate(latest?.date)}</p>`;
}
function statisticsMarkup(indicator) {
  if (indicator.unit.kind === 'unquantified') return `<p class="statistics-note statistics-panel">${t('definitionPending')}</p>`;
  const statistics = summaryStatistics(observations[indicator.id], pointsFor(indicator));
  const latest = latestObservation(observations[indicator.id]);
  return `<section class="statistics-panel" aria-label="${escape(indicator.name)} · ${t('statistics')}"><p class="statistics-date">${t('statisticsAsOf')}：${formatDate(latest?.date)} · ${t('syntheticSeries')}</p><dl class="statistics-grid">${['average3m', 'average1y', 'percentile'].map(key => {
    const statistic = statistics[key];
    const isPercentile = key === 'percentile';
    return `<div><dt>${t(key)}${isPercentile ? `<span class="statistics-range">${t(state.range)}</span>` : ''}</dt><dd>${formatNumber(statistic.value, isPercentile ? 1 : indicator.unit.precision)}<small>${isPercentile ? '%' : escape(indicator.unit.label)}</small></dd><dd class="statistics-count">${t('validCount')}：${statistic.count}</dd></div>`;
  }).join('')}</dl><p class="statistics-note">${t('statisticsNote')}</p></section>`;
}
function sourceMarkup(indicator) {
  return indicator.source.url ? `<a href="${escape(indicator.source.url)}" target="_blank" rel="noopener noreferrer">${escape(indicator.source.name)} ↗</a>` : escape(indicator.source.name);
}
function renderOverview() {
  $('#categories').innerHTML = categories.map((category, index) => {
    const items = catalog.indicators.filter(item => item.categoryId === category.id);
    if (!items.length) return `<button class="category-card" data-category="${category.id}" aria-pressed="false" aria-controls="charts"><span class="category-top"><span class="category-number">0${index + 1}</span><span class="category-name">${escape(category.name)}</span></span><span class="summary-label">${t('emptyCategory')}</span><span class="summary-date">0 ${t('indicatorCount')}</span></button>`;
    const primary = items[0], latest = latestObservation(observations[primary.id]);
    return `<button class="category-card" data-category="${category.id}" aria-pressed="false" aria-controls="charts"><span class="category-top"><span class="category-number">0${index + 1}</span><span class="category-name">${escape(category.name)}</span><span class="category-arrow" aria-hidden="true">↗</span></span><span class="summary-label">${escape(primary.name)}</span><span class="summary-value">${formatNumber(latest?.value, primary.unit.precision)}<small>${escape(primary.unit.label)}</small></span><span class="sparkline" id="spark-${category.id}" aria-hidden="true"></span><span class="secondary-summary">${items.slice(1, 2).map(item => secondarySummary(item, latest?.date)).join('<br>')}</span><span class="summary-date">${t('observationDate')} ${formatDate(latest?.date)} · ${items.length} ${t('indicatorCount')} · ${t('demoShort')}</span></button>`;
  }).join('');
  categories.forEach(category => {
    const indicator = catalog.indicators.find(item => item.categoryId === category.id);
    if (!indicator) return;
    drawChart($(`#spark-${category.id}`), inRange(observations[indicator.id], '1y', catalog.dataset.observationEnd), indicator, {sparkline: true});
  });
}
function renderCharts() {
  const category = categories.find(item => item.id === state.category);
  $('#category-title').textContent = category.name;
  $('#category-eyebrow').textContent = `0${categories.indexOf(category) + 1} / ${t('category')}`;
  $('#category-description').textContent = category.description;
  document.querySelectorAll('[data-category]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.category === state.category)));
  $('#ranges').innerHTML = ['ytd', '1y', '5y', 'all'].map(range => `<button data-range="${range}" aria-pressed="${state.range === range}">${t(range)}</button>`).join('');
  const parent = $('#charts');
  disposeCharts(parent);
  const indicators = catalog.indicators.filter(item => item.categoryId === state.category);
  if (!indicators.length) {
    parent.innerHTML = `<p class="empty-category">${t('emptyCategory')}</p>`;
    return;
  }
  parent.innerHTML = indicators.map(indicator => `<article class="indicator-card" aria-labelledby="heading-${indicator.id}"><div class="card-heading"><h3 id="heading-${indicator.id}">${escape(indicator.name)}</h3><span class="card-demo">${t('demoShort')}</span></div><p class="indicator-role">${escape(indicator.role ?? '')}</p>${metrics(indicator)}<div class="chart-unit">${t('unit')}：${escape(indicator.unit.label)}</div><div class="detail-chart" id="chart-${indicator.id}" role="img" aria-label="${escape(indicator.name)} · ${t(state.range)} · ${t('syntheticSeries')}"></div><div class="card-actions"><button class="text-button" data-statistics="${indicator.id}" aria-expanded="${statisticsOpen.has(indicator.id)}" aria-controls="statistics-${indicator.id}"><span aria-hidden="true">▦</span> ${t(statisticsOpen.has(indicator.id) ? 'hideStatistics' : 'statistics')}</button><button class="text-button" data-expand="${indicator.id}">${t('expand')} <span aria-hidden="true">↗</span></button></div><div id="statistics-${indicator.id}" ${statisticsOpen.has(indicator.id) ? '' : 'hidden'}>${statisticsMarkup(indicator)}</div></article>`).join('');
  indicators.forEach(indicator => drawChart($(`#chart-${indicator.id}`), pointsFor(indicator), indicator));
}
function renderDialog() {
  const indicator = catalog.indicators.find(item => item.id === state.indicator);
  disposeCharts($('#dialog-content'));
  if (!indicator) {
    if (dialog.open) dialog.close();
    document.body.classList.remove('modal-open');
    if (renderedIndicator && dialogTrigger?.isConnected) dialogTrigger.focus();
    return;
  }
  $('#dialog-content').innerHTML = `<h2 id="dialog-title">${escape(indicator.name)}</h2><p class="dialog-range">${t(state.range)} · ${t('rangeDates')}：${formatDate(pointsFor(indicator)[0].date)} — ${formatDate(pointsFor(indicator).at(-1).date)}</p>${metrics(indicator)}<div class="chart-unit">${t('unit')}：${escape(indicator.unit.label)}</div><div id="expanded-chart" class="expanded-chart" role="img" aria-label="${escape(indicator.name)} · ${t('syntheticSeries')}"></div><div class="indicator-info"><div><h3>${t('explanation')}</h3><p>${escape(indicator.explanation)}</p></div><dl><dt>${t('source')}</dt><dd>${t('sourceFixture')}</dd><dt>${t('frequency')}</dt><dd>${frequencyLabel(indicator.frequency)}</dd><dt>${t('intendedSource')}</dt><dd>${sourceMarkup(indicator)}</dd><dt>${t('collectedAt')}</dt><dd>${formatDate(catalog.dataset.collectedAt, {hour: '2-digit', minute: '2-digit'})} UTC</dd></dl></div>`;
  if (!dialog.open) dialog.showModal();
  document.body.classList.add('modal-open');
  drawChart($('#expanded-chart'), pointsFor(indicator), indicator);
}
function renderRoute() {
  if (state && ['#methodology', '#research'].includes(location.hash)) return;
  const focusedRange = document.activeElement?.dataset.range;
  const next = parseRoute(location.hash, categories, catalog.indicators);
  state = next;
  rangesByCategory.set(state.category, state.range);
  if (state.category !== renderedCategory || state.range !== renderedRange) renderCharts();
  if (focusedRange) $(`[data-range="${state.range}"]`)?.focus();
  if (state.indicator !== renderedIndicator || state.range !== renderedRange) renderDialog();
  renderedCategory = state.category; renderedRange = state.range; renderedIndicator = state.indicator;
}

$('#categories').addEventListener('click', event => {
  const button = event.target.closest('[data-category]');
  if (button) navigate({category: button.dataset.category, range: rangesByCategory.get(button.dataset.category) ?? '5y', indicator: null});
});
$('#ranges').addEventListener('click', event => {
  const button = event.target.closest('[data-range]');
  if (button) { navigate({range: button.dataset.range}); }
});
$('#charts').addEventListener('click', event => {
  const expand = event.target.closest('[data-expand]');
  if (expand) { dialogTrigger = expand; navigate({indicator: expand.dataset.expand}); return; }
  const statisticsButton = event.target.closest('[data-statistics]');
  if (!statisticsButton) return;
  const id = statisticsButton.dataset.statistics;
  if (statisticsOpen.has(id)) statisticsOpen.delete(id); else statisticsOpen.add(id);
  $(`#statistics-${id}`).hidden = !statisticsOpen.has(id);
  statisticsButton.setAttribute('aria-expanded', String(statisticsOpen.has(id)));
  statisticsButton.innerHTML = `<span aria-hidden="true">▦</span> ${t(statisticsOpen.has(id) ? 'hideStatistics' : 'statistics')}`;
});
function closeDialog() { navigate({indicator: null}); }
$('#close-dialog').addEventListener('click', closeDialog);
dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(); });
dialog.addEventListener('click', event => { if (event.target === dialog) closeDialog(); });

async function initialize() {
  status.textContent = t('loading');
  try {
    const responses = await Promise.all(['catalog', 'observations'].map(name => fetch(new URL(`../data/${name}.json`, import.meta.url)).then(response => {if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json();})));
    [catalog, observations] = responses;
    categories = catalog.categories.toSorted((a, b) => a.order - b.order);
    $('#dataset-date').textContent = `${t('observationDate')}：${formatDate(catalog.dataset.observationEnd)}`;
    $('#dataset-window').textContent = `${t('dataWindow')}：${formatDate(catalog.dataset.observationStart)} — ${formatDate(catalog.dataset.observationEnd)}`;
    $('#collection-time').textContent = `${t('collectedAt')}：${formatDate(catalog.dataset.collectedAt, {hour: '2-digit', minute: '2-digit'})} UTC · ${t('collectionNote')}`;
    renderOverview();
    renderRoute();
    window.addEventListener('hashchange', renderRoute);
    status.textContent = '';
  } catch (error) { status.textContent = t('loadError'); console.error(error); }
}
initialize();
