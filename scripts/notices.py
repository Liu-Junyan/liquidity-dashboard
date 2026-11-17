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
