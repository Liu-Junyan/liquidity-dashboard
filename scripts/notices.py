"""Publisher and attribution for the reviewed pilot (terms checked 2026-11-17)."""
PUBLISHER = 'Junyan Liu'
TERMS = 'https://www.newyorkfed.org/privacy/termsofuse'
REFERENCE_NOTICE = (
    'The SOFR and EFFR data and related information are subject to the Terms of Use posted at newyorkfed.org. '
    'The New York Fed is not responsible for publication of the SOFR and EFFR data and related information '
    f'by {PUBLISHER}, does not endorse any particular republication, and has no liability for your use.')
NON_AFFILIATION = (
    f'{PUBLISHER} is not affiliated with the New York Fed. The New York Fed does not sanction, endorse, '
    f'or recommend any products or services offered by {PUBLISHER}.')
SOFR_NOTICE = (
    'The Secured Overnight Financing Rate (SOFR) Data are calculated using data provided under a license '
    'granted to the New York Fed by DTCC Solutions LLC (“Solutions”), an affiliate of The Depository '
    'Trust & Clearing Corporation. Solutions, its affiliates, and third parties from which they obtained '
    'data have no liability for the content of this material.')


def notices_for(identifier, year):
    board_sources = {
        'reserve-balances': ('WRBWFRBL', 'H.4.1, Reserve Balances with Federal Reserve Banks: Wednesday Level'),
        'bank-total-assets': ('TLAACBW027SBOG', 'H.8, Total Assets, All Commercial Banks; seasonally adjusted'),
        'treasury-account': ('WDTGAL', 'H.4.1, U.S. Treasury, General Account: Wednesday Level'),
        'discount-window': ('WLCFLPCL', 'H.4.1, Loans: Primary Credit: Wednesday Level'),
        'swap-line': ('SWPT', 'H.4.1, Central Bank Liquidity Swaps: Wednesday Level'),
        'fima-repo': ('H41RESPPALGTRFNWW', 'H.4.1, Repurchase Agreements - Foreign Official: Wednesday Level'),
        'bank-loans': ('TOTLL', 'H.8, Loans and Leases in Bank Credit, All Commercial Banks; seasonally adjusted'),
        'lending-standards': ('DRTSCILM', 'SLOOS, Net Percentage of Domestic Banks Tightening Standards '
                             'for Commercial and Industrial Loans to Large and Middle-Market Firms'),
        'treasury-yield-chg': ('DGS10', 'H.15, Market Yield on U.S. Treasury Securities at 10-Year Constant '
                               'Maturity, Quoted on an Investment Basis; FRED chg × 100 to bp'),
    }
    if identifier in board_sources:
        code, title = board_sources[identifier]
        return [{'text': f'Source: Board of Governors of the Federal Reserve System (US), {title} '
                 f'({code}); distributed by FRED.', 'url': f'https://fred.stlouisfed.org/series/{code}'}]
    ice_sources = {
        'credit-spreads-ig': ('BAMLC0A0CM', 'ICE BofA US Corporate Index Option-Adjusted Spread'),
        'credit-spreads-hy': ('BAMLH0A0HYM2', 'ICE BofA US High Yield Index Option-Adjusted Spread'),
    }
    if identifier in ice_sources:
        code, title = ice_sources[identifier]
        return [{'text': f'Source: ICE Data Indices, LLC, {title} ({code}); distributed by FRED. '
                 'Maintainer confirmed ICE BofA index redistribution permission on 2026-11-18. '
                 'FRED supplies a rolling three-year history for this series.',
                 'url': f'https://fred.stlouisfed.org/series/{code}'}]
    wind_indices = {
        'move': ('ICE BofA MOVE Index', 'C7536898', 'move-index'),
        'dollar-index': ('ICE U.S. Dollar Index', 'M0000271', 'currency-indices'),
    }
    if identifier in wind_indices:
        title, code, product = wind_indices[identifier]
        return [{'text': f'{title} · ICE Data Indices · Wind EDB {code}',
                 'url': f'https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-{product}'}]
    if identifier == 'vix':
        return [{'text': 'Source: Cboe Volatility Index (VIX), VIXCLS; distributed by FRED. '
                 'Copyright, Chicago Board Options Exchange, Inc. Maintainer confirmed Cboe VIX '
                 'redistribution permission on 2026-11-18. Cite Cboe and FRED.',
                 'url': 'https://fred.stlouisfed.org/series/VIXCLS'}]
    if identifier == 'reserve-assets-ratio':
        return (notices_for('reserve-balances', year) + notices_for('bank-total-assets', year) +
                [{'text': f'Project calculation by {PUBLISHER}: 100 × normalized WRBWFRBL / TLAACBW027SBOG. '
                   '覆盖范围和季调口径不同，非同一银行总体的资产占比。',
                  'url': 'https://www.federalreserve.gov/releases/h8/about.htm'}])
    if identifier in {'bond-issuance', 'treasury-bond-issuance', 'corporate-bond-issuance'}:
        return [{'text': 'Source: SIFMA, US Fixed Income Securities Statistics, supplied through Wind; '
                 'monthly gross issuance in USD billions. Redistribution permission confirmed by maintainer '
                 'on 2026-11-17. 国债和公司债包含在总量中，不可重复加总。',
                 'url': 'https://www.sifma.org/research/statistics/us-fixed-income-securities-statistics'}]
    if identifier == 'reverse-repo':
        return [{'text': f'© {year} Federal Reserve Bank of New York. Source: Overnight Reverse Repurchase '
                 'Agreements: Treasury Securities Sold by the Federal Reserve in the Temporary Open Market '
                 'Operations (RRPONTSYD); distributed by FRED. 十亿美元原值。',
                 'url': 'https://fred.stlouisfed.org/series/RRPONTSYD'},
                {'text': 'New York Fed content is subject to its Terms of Use.', 'url': TERMS}]
    if identifier in {'sofr99', 'sofr-tail-spread'}:
        return [{'text': f'© {year} Federal Reserve Bank of New York. Source: SOFR and Secured Overnight '
                 'Financing Rate: 99th Percentile (SOFR99); distributed by FRED. '
                 f'SOFR99−SOFR is a project calculation by {PUBLISHER}, in percentage points.',
                 'url': 'https://fred.stlouisfed.org/series/SOFR99'},
                {'text': REFERENCE_NOTICE, 'url': TERMS},
                {'text': NON_AFFILIATION, 'url': TERMS},
                {'text': SOFR_NOTICE, 'url': 'https://www.newyorkfed.org/markets/reference-rates/sofr'}]
    if identifier == 'fed-assets':
        return [{'text': 'Source: Board of Governors of the Federal Reserve System (US), H.4.1, '
                 'Assets: Total Assets: Total Assets (Less Eliminations from Consolidation): Wednesday Level '
                 '(WALCL); distributed by FRED. 百万美元除以1000为十亿美元。',
                 'url': 'https://fred.stlouisfed.org/series/WALCL'}]
    if identifier not in {'fed-repo', 'sofr-effr-spread', 'sofr', 'effr'}:
        return []
    notices = [{'text': f'© {year} Federal Reserve Bank of New York. Content from the New York Fed '
                'subject to the Terms of Use at newyorkfed.org.', 'url': TERMS}]
    if identifier == 'fed-repo':
        notices.append({'text': 'Source: Federal Reserve Bank of New York, Overnight Repurchase Agreements: '
                        'Total Securities Purchased by the Federal Reserve in the Temporary Open Market Operations '
                        '(RPONTTLD); distributed by FRED. 十亿美元原值。',
                        'url': 'https://fred.stlouisfed.org/series/RPONTTLD'})
    else:
        notices += [{'text': REFERENCE_NOTICE, 'url': TERMS},
                    {'text': NON_AFFILIATION, 'url': TERMS},
                    {'text': SOFR_NOTICE, 'url': 'https://www.newyorkfed.org/markets/reference-rates/sofr'},
                    {'text': f'Secured Overnight Financing Rate (SOFR) and Effective Federal Funds Rate (EFFR); '
                     f'distributed by FRED. SOFR−EFFR 为 {PUBLISHER} 项目计算，不是纽约联储发布的利差。',
                     'url': 'https://fred.stlouisfed.org/series/SOFR'}]
    return notices
