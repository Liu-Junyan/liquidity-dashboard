import { locale, t } from './zh-CN.js';

export const DAY = 86400000;
export const timestamp = date => Date.parse(`${date}T00:00:00Z`);
export function latestObservation(observations) {
  return observations.findLast(point => point.value !== null) ?? null;
}
export function changeAt(observations, period, indicator) {
  const latest = latestObservation(observations);
  if (!latest) return null;
  const policy = indicator.comparisonPolicy;
  if (policy && (!policy.periods?.includes(period) || policy.match === 'none')) return null;
  let target = timestamp(latest.date) - period * 7 * DAY;
  if (['month', 'quarter'].includes(policy?.periodUnit)) {
    const current = new Date(timestamp(latest.date));
    const months = period * (policy.periodUnit === 'quarter' ? 3 : 1);
    const rule = indicator.observationDateRule ?? policy.match;
    if (!['month-end', 'month-start', 'quarter-end', 'quarter-start', 'day-of-month'].includes(rule)) return null;
    const targetEnd = new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() - months + 1, 0));
    // Preserve source conventions: month/quarter start, end, or day-of-month.
    // Never substitute another period or clamp an impossible fixed source day.
    const day = rule.endsWith('-end') ? targetEnd.getUTCDate() : rule.endsWith('-start') ? 1 : current.getUTCDate();
    if (day > targetEnd.getUTCDate()) return null;
    target = Date.UTC(targetEnd.getUTCFullYear(), targetEnd.getUTCMonth(), day);
  }
  const exact = observations.find(point => timestamp(point.date) === target);
  const prior = policy?.match === 'on-or-before'
    ? exact ?? observations.findLast(point => point.value !== null && timestamp(point.date) <= target)
    : exact;
  if (prior && policy?.match === 'on-or-before' && target - timestamp(prior.date) > policy.maxAgeDays * DAY) return null;
  if (!prior || prior.value === null) return null;
  const difference = (latest.value - prior.value) * (indicator.comparisonPolicy?.valueScale ?? (indicator.unit.kind === 'rate' ? 100 : 1));
  return Math.abs(difference) < 1e-8 ? 0 : difference;
}
export function inRange(observations, range, anchor) {
  if (range === 'all') return observations;
  if (!anchor) return [];
  const start = new Date(timestamp(anchor));
  if (range === 'ytd') start.setUTCMonth(0, 1);
  else start.setUTCFullYear(start.getUTCFullYear() - (range === '1y' ? 1 : 5));
  return observations.filter(point => timestamp(point.date) >= start.getTime());
}
export function summaryStatistics(observations, history = observations) {
  const latest = latestObservation(observations);
  const empty = () => ({value: null, count: 0});
  if (!latest) return {average3m: empty(), average1y: empty(), percentile: empty()};
  const end = timestamp(latest.date);
  function average(months) {
    const start = new Date(end);
    const day = start.getUTCDate();
    start.setUTCDate(1);
    start.setUTCMonth(start.getUTCMonth() - months);
    const lastDay = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0)).getUTCDate();
    start.setUTCDate(Math.min(day, lastDay));
    const points = observations.filter(point => point.value !== null && timestamp(point.date) >= start.getTime() && timestamp(point.date) <= end);
    return {value: points.length ? points.reduce((sum, point) => sum + point.value, 0) / points.length : null, count: points.length};
  }
  const validHistory = history.filter(point => point.value !== null && timestamp(point.date) <= end);
  return {
    average3m: average(3),
    average1y: average(12),
    percentile: {
      value: validHistory.length ? validHistory.filter(point => point.value <= latest.value).length / validHistory.length * 100 : null,
      count: validHistory.length,
    },
  };
}
export function formatNumber(value, precision = 2) {
  return value === null || value === undefined ? '—' : new Intl.NumberFormat(locale, {minimumFractionDigits: precision, maximumFractionDigits: precision}).format(value);
}
export function formatDate(date, options = {}) {
  if (!date) return '—';
  return new Intl.DateTimeFormat(locale, {year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC', ...options}).format(new Date(date.length === 10 ? timestamp(date) : date));
}
export function formatChange(value, indicator) {
  if (value === null) return '—';
  const suffix = indicator.unit.kind === 'rate' ? 'bp' : indicator.unit.kind === 'ratio' ? t('percentagePoints') : indicator.unit.label;
  const digits = indicator.unit.kind === 'rate' ? 1 : indicator.unit.precision;
  return `${value > 0 ? '+' : ''}${formatNumber(value, digits)} ${suffix}`;
}
export function parseRoute(hash, categories, indicators) {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const indicator = indicators.find(item => item.id === params.get('indicator'));
  const category = indicator?.categoryId ?? (categories.some(item => item.id === params.get('category')) ? params.get('category') : (indicators.find(item => item.availability === 'numeric')?.categoryId ?? categories[0].id));
  const range = ['ytd', '1y', '5y', 'all'].includes(params.get('range')) ? params.get('range') : '5y';
  return { category, range, indicator: indicator?.id ?? null };
}
export const frequencyLabel = frequency => ({daily: '每日', weekly: '每周', monthly: '每月', quarterly: '每季度', annual: '每年', irregular: '不定期'})[frequency] ?? '待确认';
export const comparisonPeriods = indicator => indicator.isDemo ? [4, 13] : (indicator.comparisonPolicy?.periods ?? []);
export const comparisonLabel = (indicator, period) => indicator.comparisonPolicy?.periodUnit === 'month' ? (period === 1 ? '较上月变化' : '较上年同月变化') : indicator.comparisonPolicy?.periodUnit === 'quarter' ? (period === 1 ? '较上季度变化' : '较上年同季变化') : `近${period}周变化`;
export const seriesLabel = indicator => indicator.isDemo ? t('syntheticSeries') : (indicator.inputAvailable ? indicator.source?.name ?? '来源观测' : '待接入');
export const emptyChartLabel = indicator => indicator.unit.kind === 'unquantified' ? t('unquantifiedChart') :
  (indicator.inputAvailable === false ? '待接入 · 暂无真实数据' : '所选区间暂无有效观测');


function validProductionComparison(item) {
  const policy = item.comparisonPolicy;
  const defaults = {
    daily: {periods: [4, 13], periodUnit: 'week', match: 'on-or-before', maxAgeDays: 7, explicitMissing: 'null', valueScale: 1},
    weekly: {periods: [4, 13], periodUnit: 'week', match: 'exact-date', valueScale: 1},
    monthly: {periods: [1, 12], periodUnit: 'month', match: 'source-period-date', valueScale: 1},
    quarterly: {periods: [1, 4], periodUnit: 'quarter', match: 'source-period-date', valueScale: 1},
    annual: {periods: [], match: 'none', valueScale: 1}, irregular: {periods: [], match: 'none', valueScale: 1},
  };
  const expected = defaults[item.nativeFrequency ?? 'irregular'];
  return expected && policy && Object.keys(policy).length === Object.keys(expected).length &&
    Object.entries(expected).every(([key, value]) => JSON.stringify(policy[key]) === JSON.stringify(value));
}
const safeReference = value => {
  if (typeof value !== 'string' || !value.trim()) return false;
  if (!value.includes('://')) return true;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash;
  } catch { return false; }
};

export function unpackDataset(catalog, document) {
  if (catalog.schemaVersion === 1 && catalog.dataset.isDemo === true) {
    if (!document || document.schemaVersion !== undefined) throw new Error('Mismatched demo dataset');
    return document;
  }
  if (catalog.schemaVersion !== 2 || document.schemaVersion !== 2 ||
      !['manual-preview', 'production'].includes(catalog.dataset.mode) || catalog.dataset.isDemo !== false ||
      !catalog.snapshotId || catalog.snapshotId !== document.snapshotId) {
    throw new Error('Unsupported dataset or mismatched snapshot');
  }
  const production = catalog.dataset.mode === 'production';
  if (production ? catalog.dataset.sourceReview === 'pending' || !catalog.dataset.publisher || !catalog.dataset.generatedAt
    : catalog.dataset.sourceReview !== 'pending') throw new Error('Invalid dataset review/mode');
  const allowed = new Set(['bond-issuance', 'treasury-bond-issuance', 'corporate-bond-issuance']);
  const ids = catalog.indicators.map(item => item.id);
  if (!document.series || new Set(ids).size !== ids.length ||
      Object.keys(document.series).length !== ids.length) throw new Error('Preview membership mismatch');
  for (const item of catalog.indicators) {
    const points = document.series[item.id];
    if (item.isDemo !== false || !Array.isArray(points) || (!production && !allowed.has(item.seriesId) && points.length)) {
      throw new Error('Invalid preview series');
    }
    let previous = '';
    for (const point of points) {
      if (typeof point.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(point.date) ||
          !Number.isFinite(timestamp(point.date)) || new Date(timestamp(point.date)).toISOString().slice(0, 10) !== point.date ||
          point.date <= previous || (point.value !== null && (typeof point.value !== 'number' || !Number.isFinite(point.value)))) {
        throw new Error('Invalid preview observation');
      }
      previous = point.date;
    }
    if (production) {
      const numeric = points.some(point => point.value !== null);
      if (!['numeric', 'empty', 'nonnumeric'].includes(item.availability) ||
          (item.availability === 'numeric') !== numeric ||
          (item.availability === 'nonnumeric' && points.length) ||
          typeof item.inputAvailable !== 'boolean' || (!item.inputAvailable && points.length) ||
          !item.displayUnit || typeof item.displayUnit.label !== 'string' ||
          !Number.isInteger(item.displayUnit.precision) || item.displayUnit.precision < 0 || item.displayUnit.precision > 6 ||
          !Array.isArray(item.sources) || !Array.isArray(item.notices) || !item.source ||
          !validProductionComparison(item) ||
          !item.sources.every(safeReference) ||
          (item.source.url !== null && (!item.source.url?.startsWith('https://') || !safeReference(item.source.url))) ||
          !item.notices.every(notice => typeof notice.text === 'string' && notice.url?.startsWith('https://') && safeReference(notice.url))) throw new Error('Invalid production series');
    }
  }
  if (production) {
    const dates = Object.values(document.series).flatMap(points => points.map(point => point.date)).sort();
    if (catalog.dataset.observationStart !== (dates[0] ?? null) ||
        catalog.dataset.observationEnd !== (dates.at(-1) ?? null)) throw new Error('Invalid dataset bounds');
  }
  return document.series;
}

export function displayCatalog(catalog) {
  if (catalog.dataset.mode !== 'production') return catalog;
  return {...catalog, indicators: catalog.indicators.map(item => ({...item,
    normalizedUnit: item.unit, unit: item.displayUnit, frequency: item.nativeFrequency}))};
}
