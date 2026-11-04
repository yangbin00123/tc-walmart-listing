"""Intent grouping helpers; semantic decisions remain the model's responsibility."""
import json

FIELDS = ('decision', 'reason_code', 'reason', 'query_intent', 'fact_ids', 'relevance', 'intent', 'role', 'evidence', 'promotion_condition', 'specific_fact_ids', 'group_difference')

def check(profile, decisions):
    facts = {f['fact_id']: f for f in profile['facts']}
    groups = {}
    for d in decisions:
        for key in ('intent_group', 'evidence', 'query_intent'):
            if not isinstance(d.get(key), str) or not d[key].strip():
                raise ValueError('keyword grouping missing ' + key + ': ' + d['keyword'])
        if d.get('role') not in ('identity', 'synonym', 'attribute', 'intent', 'broad'):
            raise ValueError('invalid keyword role: ' + d['keyword'])
        if d['decision'] == 'eligible':
            if any(facts[f].get('status') != 'confirmed' for f in d['fact_ids']):
                raise ValueError('uncertain fact cannot support eligible keyword: ' + d['keyword'])
            if d['relevance'] == 'high':
                refs = d.get('specific_fact_ids', [])
                if d['role'] not in ('attribute', 'intent') or not refs or not set(refs) <= set(d['fact_ids']):
                    raise ValueError('high requires narrowing attribute/intent facts: ' + d['keyword'])
        groups.setdefault(d['intent_group'], []).append(d)
    for key, rows in groups.items():
        if len({(r['decision'], r.get('relevance') if r['decision']=='eligible' else None) for r in rows}) > 1:
            if any(not str(r.get('group_difference', '')).strip() for r in rows):
                raise ValueError('intent group decisions differ without explanation: ' + key)

def apply(ledger, spec):
    import copy
    result = copy.deepcopy(ledger)
    assigned = {}
    known = {d['keyword'] for d in result['decisions']}
    for group_id, group in spec['groups'].items():
        if not group_id.strip() or not group.get('keywords'):
            raise ValueError('empty intent group')
        for word in group['keywords']:
            if word not in known or word in assigned:
                raise ValueError('unknown or repeated group keyword: ' + word)
            assigned[word] = (group_id, group)
    if set(assigned) != known:
        raise ValueError('groups must cover every original keyword exactly once')
    overrides = spec.get('overrides', {})
    if not set(overrides) <= known:
        raise ValueError('unknown override keyword')
    for d in result['decisions']:
        group_id, group = assigned[d['keyword']]
        initial = d.get('initial_decision', d.get('decision'))
        word = d['keyword']
        d.clear()
        d.update({k: copy.deepcopy(group[k]) for k in FIELDS if k in group})
        d.update(keyword=word, intent_group=group_id, initial_decision=initial)
        if word in overrides:
            override = overrides[word]
            if not override.get('group_difference'):
                raise ValueError('override needs group_difference: ' + word)
            d.update({k: copy.deepcopy(override[k]) for k in FIELDS if k in override})
    result['group_schema_version'] = 1
    return result

def view(raw):
    # Source order avoids inventing comparable volume where none is supplied.
    rows = ['keyword\tsource_product_ids\tproduct_hit_count']
    for r in raw['raw']['keyword_data']:
        cells = [r['keyword'], ','.join(r['source_product_ids']), str(len(r['source_product_ids']))]
        rows.append('\t'.join(c.replace('\t', ' ').replace('\n', ' ') for c in cells))
    return '\n'.join(rows) + '\n'
