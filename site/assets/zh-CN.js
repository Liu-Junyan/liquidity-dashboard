export const locale = 'zh-CN';
export const messages = {
  skip: '跳至指标图表', home: '美元流动性观察首页', brand: '流动性研究', brandEnglish: 'LIQUIDITY OBSERVATORY', mainNavigation: '主导航', rangeAria: '图表时间范围', close: '关闭详情', eyebrow: 'USD LIQUIDITY / WEEKLY MONITOR', readingEyebrow: 'READING THE DATA',
  title: '美元流动性观察', mastheadNote: '独立研究 · 周度视角', dashboard: '数据看板', methodology: '数据与阅读说明', edition: '研究原型  /  01',
  demoBadge: '演示数据 · 非实时', intro: '以周度视角，观察美元流动性的变化。选择类别，探索指标与历史趋势。',
  weekly: '周度观测', observationDate: '观测日期', dataWindow: '样本区间', aboutData: '了解数据说明 ↗', overview: '流动性概览', overviewHint: '选择类别查看详细指标 · 缩略图为近一年',
  rangeLabel: '时间范围', ytd: 'YTD', '1y': '近1年', '5y': '近5年', all: '全部', syntheticSeries: '合成数据',
  latest: '最新值', change4: '近4周变化', change13: '近13周变化', unit: '单位', weeklyFrequency: '每周',
  expand: '展开指标', statistics: '查看统计摘要', hideStatistics: '收起统计摘要', average3m: '近3个月均值', average1y: '近1年均值', percentile: '当前值历史分位', validCount: '有效观测', statisticsAsOf: '统计截至', statisticsNote: '均值按最新有效观测日期向前3个月、1年计算，不受图表范围限制；仅计入可用观测。历史分位为当前图表区间内小于或等于最新值的有效观测占比（含最新值）。缺失值不参与计算。',
  chartNote: '注：单位以各图标注为准；比例变动以百分点表示，其余变化沿用原生单位。正负仅代表方向，不代表利好或利空。缺失观测保留为空白。',
  methodologyBody: '本页使用固定生成的五年周度合成数据，用于评审界面与研究流程。所有数值、趋势与数据日期均为演示，不反映真实市场状况。',
  placeholderNote: '指标清单、名称、分组与来源说明由维护者登记表生成；暂不可用的指标不展示。当前数值仍为合成演示，尚未接入登记来源或执行派生公式。',
  emptyCategory: '此类别暂无展示指标',
  indicatorCount: '项指标', percentagePoints: '百分点', definitionPending: '观察规则待定义 · 暂不生成数值或统计。', unquantifiedChart: '当前指标尚无数值定义。待明确观察规则后再量化，当前没有数值序列。',
  collectedAt: '演示数据生成时间', collectionNote: '与指标观测日期分别记录', footerNote: '合成数据研究原型 · 不构成投资建议', backTop: '返回顶部 ↑',
  explanation: '指标说明', source: '当前数据来源', intendedSource: '后续拟接入来源', frequency: '更新频率', sourceFixture: '本地合成数据（非官方观测）',
  demoShort: '演示', category: '类别', loading: '正在加载本地数据…', loadError: '数据加载失败。请通过 HTTP 本地服务器打开页面，或稍后重试。', chartUnavailable: '图表组件未能加载，仍可查看最新值与统计摘要。',
  rangeDates: '显示区间',
};
const previewMessages = {
  mastheadNote: '独立研究 · 月度发行数据', eyebrow: 'USD LIQUIDITY / SIFMA PREVIEW',
  edition: '本地数据预览', demoBadge: 'SIFMA 数据预览 · 定义待复核',
  intro: '查看已保存的 SIFMA / Wind 月度发行数据。来源引用、覆盖范围及月度／年累计口径待复核。',
  weekly: '月度观测', syntheticSeries: 'SIFMA / Wind 数据', demoShort: '本地预览',
  methodologyBody: '本页展示已保存的 Wind 工作簿所导出的三项 SIFMA 发行数据，保留原始月末日期及十亿美元单位。数据未在此刷新；来源引用、覆盖范围、发行口径及月度／年累计定义尚待复核，不能视为已审核的生产数据。',
  placeholderNote: '仅债券、国债及公司债发行量有真实输入；其他指标保留为空并显示待接入。三项发行量的覆盖范围可能重叠，不作加总。较上月和较上年同月变化按对应月末观测计算；缺失月份不替代、不插值。',
  footerNote: 'SIFMA 本地预览 · 来源定义待复核',
};
let mode = 'demo';
const productionMessages = {
  mastheadNote: '独立研究 · 来源观测', eyebrow: 'USD LIQUIDITY / RESEARCH MONITOR',
  edition: '美元流动性研究', demoBadge: '来源数据 · 非实时',
  intro: '观察美元流动性的变化。保留各来源的原生频率与观测日期，选择类别探索指标与历史趋势。',
  weekly: '原生频率观测', syntheticSeries: '来源观测', demoShort: '来源数据',
  methodologyBody: '本页展示经复核来源的历史观测：美联储总资产、纽约联储隔夜正回购总量，以及项目计算的 SOFR−EFFR 利差。数据经 FRED 获取，保留来源日期及缺失值，不填充、不插值。历史数据可能修订；当前历史不代表当时可获得的信息。',
  placeholderNote: '未接入的指标显示待接入；尚无数值定义的观察项保留文字说明。日度变化匹配目标日或此前不超过7天的观测，显式缺失不回退；周度变化要求精确日期。利差为百分点，未进行基点换算。统计按原生有效观测计算，不补齐日期。',
  footerNote: 'Junyan Liu · 独立研究 · 不构成投资建议',
};
export function setDataMode(value) { mode = value; }
export const t = key => (mode === 'manual-preview' ? previewMessages[key] : mode === 'production' ? productionMessages[key] : undefined) ?? messages[key] ?? key;
