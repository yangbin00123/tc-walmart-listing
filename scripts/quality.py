#!/usr/bin/env python3
"""Local evidence, keyword pools and exact-phrase audit. No network calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

MARKETS = {'US': 'Walmart US', 'CA': 'Walmart Canada', 'MX': 'Walmart Mexico'}
POOL_FILES = {'eligible': '03_kw_filtered.json', 'deferred': '03_kw_deferred.json', 'excluded': '03_kw_removed.json'}
REVIEW_FILES = ['01_product_profile.json', '02_kw_raw.json', '03_keyword_decisions.json', '05_keyword_plan.json', '07_listing.json']

def read(run, name):
    return json.loads((run / name).read_text(encoding='utf-8'))

def write(run, name, data):
    path = run / name
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)

def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())

def match(text, phrase):
    # Preserve offsets into the original text, including NFKC expansions.
    chars, offsets = [], []
    for i, char in enumerate(text):
        for unit in unicodedata.normalize('NFKC', char).casefold():
            chars.append(' ' if unit.isspace() or unit in '-‐‑‒–—' else unit)
            offsets.append(i)
    needle = re.sub(r'[\s\-‐‑‒–—]+', ' ', norm(phrase)).strip()
    if not needle:
        return ''
    pattern = r'(?<!\w)' + r'\s+'.join(re.escape(t) for t in needle.split()) + r'(?!\w)'
    found = re.search(pattern, ''.join(chars))
    return text[offsets[found.start()]:offsets[found.end()-1]+1] if found else ''

def pointer(value, path):
    if path == '':
        return value
    if not path.startswith('/'):
        raise ValueError('JSON pointer must start with /')
    for part in path[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value

def require(condition, message):
    if not condition:
        raise ValueError(message)

def decode_response(response):
    # This exact success sentinel was observed on the live Sorftime endpoint.
    # Never generalize arbitrary errors or malformed text to an empty result.
    if response == 'No data available.':
        return {'data': []}
    return json.loads(response) if isinstance(response, str) else response


def envelope_text(envelope):
    require(isinstance(envelope, dict) and envelope.get('isError') is not True,
            'MCP tool error is not an empty keyword page')
    blocks = envelope.get('content', [])
    texts = [b['text'] for b in blocks if b.get('type') == 'text']
    require(len(texts) == 1 and isinstance(texts[0], str), 'unsupported MCP response envelope')
    return texts[0]


def traffic_refs(response):
    require(isinstance(response, dict) and isinstance(response.get('data'), list),
            'Sorftime traffic response must contain a data array')
    require(not response.get('error') and not response.get('isError'), 'business error is not an empty keyword page')
    refs = []
    for i, record in enumerate(response['data']):
        require(isinstance(record, dict) and isinstance(record.get('keyword'), dict)
                and isinstance(record['keyword'].get('keyword'), str)
                and norm(record['keyword']['keyword']), 'unexpected Sorftime keyword record')
        refs.append({'record_pointer': f'/data/{i}', 'keyword_pointer': '/keyword/keyword'})
    return refs


def import_page(envelope, number):
    require(type(number) is int and 1 <= number <= 5, 'page must be 1-5')
    text = envelope_text(envelope)
    response = decode_response(text)
    return {'page': number, 'mcp_response': envelope, 'response': text,
            'records': traffic_refs(response), 'has_next': None}


def profile_check(profile):
    require(profile.get('target_country') in MARKETS, 'Only US, CA and MX are supported')
    ids = profile.get('product_ids')
    require(isinstance(ids, list) and all(isinstance(i, str) and i for i in ids)
            and 1 <= len(ids) <= 20 and len(ids) == len(set(ids)), 'profile: require 1-20 unique Product IDs')
    mode = profile.get('mode', 'production')
    require(mode in ('production', 'public_product_demo'), 'invalid profile mode')
    demo = mode == 'public_product_demo'
    if demo:
        require(profile.get('target_product_id') and profile.get('test_authorization')
                and profile.get('brand_authorized') is False, 'demo requires target ID, explicit test authorization and no brand authorization claim')
    sources = profile.get('sources', [])
    require(isinstance(sources, list) and sources, 'profile.sources required')
    source_map = {s['source_id']: s for s in sources}
    require(len(source_map) == len(sources), 'duplicate source_id')
    for source in sources:
        kinds = ('public_product',) if demo else ('user_text', 'user_image', 'user_document')
        require(source.get('kind') in kinds and source.get('locator') and source.get('excerpt'),
                'source requires appropriate provenance, locator and excerpt/observation')
        if demo:
            require(source.get('product_id') == profile['target_product_id'], 'demo facts must belong to the exact target product')
    facts = profile.get('facts', [])
    require(isinstance(facts, list) and facts, 'profile.facts required')
    fact_map = {f['fact_id']: f for f in facts}
    require(len(fact_map) == len(facts), 'duplicate fact_id')
    for fact in facts:
        require(fact.get('status') == ('source_reported' if demo else 'confirmed') and fact.get('text') and fact.get('source_ids')
                and set(fact['source_ids']) <= set(source_map), 'fact must cite appropriate source evidence and status')
    if demo and profile.get('brand'):
        require(profile.get('brand_fact_ids') and set(profile['brand_fact_ids']) <= set(fact_map), 'demo brand requires target product facts')
    require(profile.get('identity_fact_ids') and set(profile['identity_fact_ids']) <= set(fact_map), 'identity_fact_ids must cite product identity')
    require(isinstance(profile.get('image_plan_required'), bool), 'image_plan_required must be explicit')
    variants = profile.get('variations', [])
    require(isinstance(variants, list), 'variations must be a list')
    require(len({v['variant_id'] for v in variants}) == len(variants), 'duplicate variant_id')
    for variant in variants:
        require(variant.get('attributes') and variant.get('fact_ids')
                and set(variant['fact_ids']) <= set(fact_map), 'variant requires attributes and facts')
    return fact_map

def source_market_check(country):
    capabilities = json.loads((Path(__file__).resolve().parents[1] / 'references' / 'SOURCE_CAPABILITIES.json').read_text(encoding='utf-8'))
    require(country in capabilities['writing_countries'], 'Only US, CA and MX are supported')
    require(country in capabilities['research_countries'],
            'unsupported_source_market: Sorftime Walmart local keyword research is currently verified for US only; target=' + country)


def research_check(run, rebuild=False):
    profile, raw = read(run, '01_product_profile.json'), read(run, '02_kw_raw.json')
    profile_check(profile)
    source_market_check(profile['target_country'])
    ids = profile['product_ids']
    require(raw.get('source') == 'sorftime_mcp' and raw.get('tool') == 'walmart_product_traffic_terms', 'invalid research source')
    require(raw.get('product_ids') == ids and raw.get('completed_product_ids') == ids
            and raw.get('complete') is True, 'research incomplete or input IDs differ')
    require(raw.get('marketplace') == MARKETS[profile['target_country']], 'research target market mismatch')
    verification = raw.get('market_verification', {})
    require(verification.get('status') in ('verified', 'unverified') and verification.get('evidence'), 'record market evidence or explicit uncertainty')
    if verification['status'] == 'verified':
        require(verification.get('country') == profile['target_country'], 'verified country mismatch')
    by_id = raw['raw']['by_product_id']
    require(set(by_id) == set(ids), 'pagination IDs mismatch')
    aggregated, capped = {}, []
    for product_id in ids:
        state = by_id[product_id]
        pages = state['pages']
        require(state.get('error') is None and 1 <= len(pages) <= 5, 'page error or invalid page count: ' + product_id)
        seen, signatures = set(), []
        for number, page in enumerate(pages, 1):
            require(page['page'] == number and 'response' in page, 'missing or non-contiguous page')
            if 'mcp_response' in page:
                require(envelope_text(page['mcp_response']) == page['response'], 'page differs from saved MCP response')
            response = decode_response(page['response'])
            records = page['records']
            require(isinstance(records, list), 'page.records must be a list')
            if isinstance(response, dict) and 'data' in response:
                require(records == traffic_refs(response), 'Sorftime page extraction omitted, duplicated or reordered records')
            keys = []
            for ref in records:
                record = pointer(response, ref['record_pointer'])
                word = pointer(record, ref['keyword_pointer'])
                require(isinstance(word, str) and norm(word), 'invalid keyword extraction')
                key = norm(word)
                keys.append(key)
                if key not in aggregated:
                    aggregated[key] = dict(keyword=word, normalized_keyword=key, source_product_ids=[], product_hit_count=0,
                                           first_seen_order=len(aggregated)+1, sorftime_records=[])
                item = aggregated[key]
                if product_id not in item['source_product_ids']:
                    item['source_product_ids'].append(product_id)
                    item['product_hit_count'] += 1
                item['sorftime_records'].append({'product_id': product_id, 'page': number,
                                                'record_pointer': ref['record_pointer'], 'record': record})
            signature = digest(keys)
            no_new = not (set(keys) - seen)
            repeated = signature in signatures
            has_next = page.get('has_next')
            require(has_next is None or isinstance(has_next, bool), 'has_next must be boolean or null')
            if has_next is False:
                require(page.get('next_page_evidence'), 'no-next-page requires evidence from response')
            terminal = has_next is False or not keys or no_new or repeated or number == 5
            require(not terminal or number == len(pages), 'pages continued after stop condition')
            if number == len(pages):
                reasons = set()
                if has_next is False: reasons.add('no_next_page')
                if not keys: reasons.add('empty_page')
                if repeated: reasons.add('repeated_page')
                if no_new: reasons.add('no_new_keywords')
                if number == 5: reasons.add('max_pages')
                require(state.get('stop_reason') in reasons, 'unsupported pagination stop reason')
                is_capped = number == 5 and has_next is not False and bool(keys) and not no_new and not repeated
                require(state.get('pagination_capped') is is_capped, 'incorrect pagination_capped')
                if is_capped: capped.append(product_id)
            seen.update(keys)
            signatures.append(signature)
    expected = list(aggregated.values())
    require(expected, 'zero keywords: replace competitor IDs before writing')
    if rebuild:
        raw['raw']['keyword_data'] = expected
        raw['keywords'] = [r['keyword'] for r in expected]
        raw['pagination'] = {'max_pages_per_product_id': 5, 'capped_product_ids': capped}
    require(raw['raw'].get('keyword_data') == expected and raw.get('keywords') == [r['keyword'] for r in expected], 'aggregate does not match original page records')
    require(raw.get('pagination') == {'max_pages_per_product_id': 5, 'capped_product_ids': capped}, 'pagination summary mismatch')
    if rebuild:
        write(run, '02_kw_raw.json', raw)
    return profile, raw

def decision_check(run, exports=False):
    profile, raw = research_check(run)
    ledger = read(run, '03_keyword_decisions.json')
    require(ledger.get('profile_sha256') == digest(profile) and ledger.get('raw_sha256') == digest(raw), 'facts/research changed: review decisions and refresh ledger fingerprints')
    require(ledger.get('group_schema_version') == 1, 'intent-group ledger required before writing')
    decisions = ledger['decisions']
    require([d['keyword'] for d in decisions] == raw['keywords'], 'every raw keyword must have exactly one decision in source order')
    facts = {f['fact_id'] for f in profile['facts']}
    for d in decisions:
        require(d.get('decision') in POOL_FILES and d.get('reason_code') and d.get('reason') and d.get('query_intent'), 'incomplete keyword decision')
        require(isinstance(d.get('fact_ids'), list) and set(d['fact_ids']) <= facts, 'invalid keyword fact_ids')
        if d['decision'] == 'eligible':
            require(d['fact_ids'] and d.get('relevance') in ('high', 'relevant') and d.get('intent'), 'eligible keyword requires facts and tags')
        if d['decision'] == 'deferred':
            require(d.get('promotion_condition'), 'deferred keyword requires promotion_condition')
    if ledger.get('group_schema_version') == 1:
        from keyword_groups import check
        check(profile, decisions)
    pools = {state: [] for state in POOL_FILES}
    for source, d in zip(raw['raw']['keyword_data'], decisions):
        pools[d['decision']].append({**source, **d})
    if exports:
        for state, filename in POOL_FILES.items():
            require(read(run, filename) == pools[state], 'stale or modified pool: ' + filename)
        require(read(run, '04_kw_tagged.json') == pools['eligible'], 'tagged keywords must equal eligible pool')
    return profile, raw, decisions, pools

def fields(listing):
    result = {'product_title': listing['product_title'], 'product_description': listing['product_description']}
    if listing.get('variation_title_template'):
        result['variation_title_template'] = listing['variation_title_template']
    result.update({f'key_features.{i}': value for i, value in enumerate(listing['key_features'])})
    result.update({f'variant_titles.{i}.title': value['title'] for i, value in enumerate(listing.get('variant_titles', []))})
    for i, item in enumerate(listing.get('image_plan', [])):
        for key in ('direction', 'overlay_text'):
            result[f'image_plan.{i}.{key}'] = item.get(key, '')
    require(all(isinstance(v, str) for v in result.values()), 'all content fields must be strings')
    return result

def coverage(run):
    profile, raw, decisions, pools = decision_check(run, exports=True)
    listing, plan = read(run, '07_listing.json'), read(run, '05_keyword_plan.json')
    content = fields(listing)
    allowed = {d['keyword'] for d in pools['eligible']}
    assigned = []
    rows = []
    mapping = {'title': ['product_title'], 'description': ['product_description'],
               'key_features': [f for f in content if f.startswith('key_features.')]}
    require(set(plan) == {'title', 'description', 'key_features', 'not_planned'}, 'invalid keyword plan fields')
    for group, names in mapping.items():
        for item in plan[group]:
            word = item['keyword']
            require(word in allowed, 'only eligible keywords may be planned: ' + word)
            assigned.append(word)
            matches = [{'field': name, 'matched_text': match(content[name], word)} for name in names if match(content[name], word)]
            require(matches or item.get('unused_reason'), 'missing unused_reason: ' + word)
            rows.append({'keyword': word, 'field': group, 'used': bool(matches), 'matches': matches,
                         'reason': '' if matches else item['unused_reason']})
    unplanned = plan['not_planned']
    require(all(i.get('reason') for i in unplanned), 'not_planned requires reasons')
    not_words = [i['keyword'] for i in unplanned]
    require(len(assigned) == len(set(assigned)) and len(not_words) == len(set(not_words))
            and not set(assigned) & set(not_words) and set(assigned + not_words) == allowed,
            'each eligible word must be planned once or explicitly not_planned')
    blocked = []
    for d in decisions:
        if d['decision'] != 'eligible':
            for name, value in content.items():
                if match(value, d['keyword']):
                    blocked.append({'keyword': d['keyword'], 'field': name, 'decision': d['decision']})
    # Planning intent and actual appearance are separate: broad terms can appear
    # naturally even when explicitly not targeted. Scan all eligible words.
    frontend = {name: value for name, value in content.items()
                if name in ('product_title', 'product_description') or name.startswith(('key_features.', 'variant_titles.'))}
    actual_eligible = []
    for d in pools['eligible']:
        matches = [{'field': name, 'matched_text': match(value, d['keyword'])}
                   for name, value in frontend.items() if match(value, d['keyword'])]
        actual_eligible.append({'keyword': d['keyword'], 'planned': d['keyword'] in assigned,
                                'used': bool(matches), 'matches': matches})
    return {'planned': rows, 'not_planned': unplanned, 'blocked_hits': blocked,
            'actual_eligible': actual_eligible,
            'summary': {'eligible': len(allowed), 'planned': len(rows),
                        'planned_used_in_assigned_field': sum(row['used'] for row in rows),
                        'actually_used': sum(row['used'] for row in actual_eligible)},
            'mode': profile.get('mode', 'production'), 'target_product_id': profile.get('target_product_id'),
            'market_verification': raw['market_verification'], 'capped_product_ids': raw['pagination']['capped_product_ids']}

def final_check(run):
    profile, raw, decisions, pools = decision_check(run, exports=True)
    listing = read(run, '07_listing.json')
    require(listing['marketplace'] == MARKETS[profile['target_country']], 'listing country differs from input')
    content = fields(listing)
    actual = coverage(run)
    require(read(run, '08_keyword_coverage.json') == actual, 'coverage report differs from actual phrase matches: run audit')
    require(not actual['blocked_hits'], 'deferred/excluded keyword leaked into content')
    for term in profile.get('forbidden_terms', []):
        require(not any(match(v, term) for v in content.values()), 'forbidden term in content: ' + term)
    facts = {f['fact_id'] for f in profile['facts']}
    claims = listing.get('claims', [])
    require(claims, 'claims with fact references required')
    for claim in claims:
        require(claim.get('field') in content and claim.get('text') and claim['text'] in content[claim['field']], 'claim text must exist in its field')
        require(claim.get('fact_ids') and set(claim['fact_ids']) <= facts, 'claim has invalid fact reference')
    claimed = {c['field'] for c in claims}
    require({f for f, value in content.items() if value.strip()} <= claimed, 'every nonempty content field requires fact-linked claims')
    variants = profile.get('variations', [])
    titles = listing.get('variant_titles', [])
    require([v['variant_id'] for v in titles] == [v['variant_id'] for v in variants], 'variant titles must match supplied variants in order')
    require(all(isinstance(v.get('title'), str) and v['title'].strip() and len(v['title']) <= 150 for v in titles), 'each rendered variant title must be nonempty and at most 150 characters')
    if variants: require(listing.get('variation_title_template'), 'variant template required')
    else: require(not listing.get('variation_title_template'), 'no invented variant template')
    if profile['image_plan_required']: require(listing.get('image_plan'), 'image plan required')
    brand = profile.get('brand')
    require(listing.get('brand') == brand, 'brand mismatch')
    demo = profile.get('mode') == 'public_product_demo'
    if demo:
        require(listing.get('mode') == 'public_product_demo' and listing.get('target_product_id') == profile['target_product_id'], 'demo output must identify exact target and test mode')
    else:
        require(listing.get('mode', 'production') == 'production', 'output mode differs from profile')
    if brand:
        require((demo or profile.get('brand_authorized') is True), 'brand requires authorization or a demo-reference source')
    review = read(run, '08_semantic_review.json')
    require(review.get('fingerprints') == {name: digest(read(run, name)) for name in REVIEW_FILES}, 'semantic review stale: regenerate template and re-review changed content')
    for name in ('facts_and_claims', 'keyword_intent', 'walmart_copy', 'variants_and_images'):
        item = review.get('checks', {}).get(name, {})
        require(item.get('status') == 'passed' and item.get('notes'), 'semantic review pending/failed: ' + name)
    # User-facing Markdown must actually include the reviewed content.
    md = (run / '07_listing.md').read_text(encoding='utf-8')
    require(md == render_text(listing, actual), 'Markdown differs from reviewed content; render again')

def render_text(listing, report):
    lines = []
    if report.get('mode') == 'public_product_demo':
        lines += ['> 公开商品流程测试：仅重写所选商品的公开资料；不代表用户拥有该商品或品牌授权，不作为用户新品直接上架。',
                  '测试商品 ID：' + report['target_product_id']]
    lines += ['# Product Title', listing['product_title'], '# Product Description', listing['product_description'], '# Key Features']
    lines += ['- ' + value for value in listing['key_features']]
    if listing.get('variation_title_template'):
        lines += ['# Variation Title Template', listing['variation_title_template']]
        lines += ['- ' + v['variant_id'] + ': ' + v['title'] for v in listing.get('variant_titles', [])]
    if listing.get('image_plan'):
        lines += ['# 图片策划']
        for i, item in enumerate(listing['image_plan'], 1):
            lines += [f'## 图 {i}', item['direction'], item.get('overlay_text', '')]
    lines += ['# 研究说明', '市场来源核验：' + report['market_verification']['status'], report['market_verification']['evidence']]
    if report['capped_product_ids']:
        lines += ['达到分页上限（不代表全量采集）：' + ', '.join(report['capped_product_ids'])]
    return '\n\n'.join(lines) + '\n'


def render(run):
    (run / '07_listing.md').write_text(render_text(read(run, '07_listing.json'), read(run, '08_keyword_coverage.json')), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply-groups', 'check-keywords', 'check-source', 'aggregate', 'rebind', 'check-research', 'prepare', 'export', 'audit', 'review-template', 'render'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    run = args.directory.resolve()
    try:
        if args.command == 'check-source': source_market_check(read(run, '01_product_profile.json')['target_country'])
        elif args.command == 'aggregate': research_check(run, rebuild=True)
        elif args.command == 'rebind':
            profile, raw = research_check(run)
            ledger = read(run, '03_keyword_decisions.json')
            old = {d['keyword']: d for d in ledger['decisions']}
            decisions = []
            for word in raw['keywords']:
                item = old.get(word, {'keyword': word, 'fact_ids': []})
                item['decision'] = 'pending'
                decisions.append(item)
            write(run, '03_keyword_decisions.json', {'profile_sha256': digest(profile), 'raw_sha256': digest(raw), 'decisions': decisions})
        elif args.command == 'check-research': research_check(run)
        elif args.command == 'prepare':
            profile, raw = research_check(run)
            require(not (run / '03_keyword_decisions.json').exists(), 'ledger exists: edit it; do not discard decisions')
            from keyword_groups import view
            (run / '03_keyword_view.tsv').write_text(view(raw), encoding='utf-8')
            write(run, '03_keyword_decisions.json', {'profile_sha256': digest(profile), 'raw_sha256': digest(raw), 'decisions': [
                {'keyword': word, 'decision': 'pending', 'reason_code': '', 'reason': '', 'query_intent': '', 'fact_ids': []} for word in raw['keywords']]})
        elif args.command == 'apply-groups':
            from keyword_groups import apply
            ledger = apply(read(run, '03_keyword_decisions.json'), read(run, '03_keyword_groups.json'))
            write(run, '03_keyword_decisions.json', ledger)
            decision_check(run)
        elif args.command == 'check-keywords':
            require(read(run, '03_keyword_decisions.json').get('group_schema_version') == 1, 'intent-group ledger required before writing')
            decision_check(run, exports=True)
        elif args.command == 'export':
            _, _, _, pools = decision_check(run)
            for state, filename in POOL_FILES.items(): write(run, filename, pools[state])
            write(run, '04_kw_tagged.json', pools['eligible'])
        elif args.command == 'audit': write(run, '08_keyword_coverage.json', coverage(run))
        elif args.command == 'render': render(run)
        else:
            fingerprints = {name: digest(read(run, name)) for name in REVIEW_FILES}
            path = run / '08_semantic_review.json'
            if not path.exists() or read(run, path).get('fingerprints') != fingerprints:
                write(run, path.name, {'fingerprints': fingerprints, 'checks': {key: {'status': 'pending', 'notes': ''} for key in
                    ('facts_and_claims', 'keyword_intent', 'walmart_copy', 'variants_and_images')}})
        print('OK: ' + args.command)
        return 0
    except (ValueError, TypeError, KeyError, OSError, AttributeError, IndexError) as error:
        print('ERROR: ' + str(error))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
