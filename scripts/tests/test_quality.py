"""Offline synthetic fixtures: validate invariants, never claim live MCP validation."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quality as q
from validate_output import validate, count_words
from copy_checks import validate_copy, locale_signals

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.profile = dict(target_country='US', product_ids=['123'], product_name='Storage Bag', brand=None,
            brand_authorized=False, image_plan_required=True, forbidden_terms=[], unknowns=['waterproof'], variations=[],
            sources=[dict(source_id='s1', kind='user_text', locator='synthetic test input', excerpt='Storage bag, cotton, blue')],
            facts=[dict(fact_id='f1', text='Cotton storage bag in blue', status='confirmed', source_ids=['s1'])], identity_fact_ids=['f1'])
        self.raw = dict(source='sorftime_mcp', server='sorftime-server', tool='walmart_product_traffic_terms',
            marketplace='Walmart US', product_ids=['123'], completed_product_ids=['123'], complete=True,
            market_verification=dict(status='unverified', evidence='No country supplied by synthetic source'),
            raw={'by_product_id': {'123': dict(pages=[dict(page=1, response={'items': [
                {'term': 'storage bag', 'volume': 30}, {'term': 'waterproof bag', 'volume': 100}, {'term': 'leather bag', 'volume': 5}]},
                records=[dict(record_pointer='/items/'+str(i), keyword_pointer='/term') for i in range(3)],
                has_next=False, next_page_evidence='Synthetic end-of-results')], stop_reason='no_next_page', pagination_capped=False, error=None)}, 'keyword_details': {}})
        self.save('01_product_profile.json', self.profile)
        self.save('02_kw_raw.json', self.raw)
        q.research_check(self.run, rebuild=True)
        self.raw = q.read(self.run, '02_kw_raw.json')
        self.ledger = dict(profile_sha256=q.digest(self.profile), raw_sha256=q.digest(self.raw), decisions=[
            dict(keyword='storage bag', decision='eligible', reason_code='identity', reason='Confirmed identity', query_intent='storage', fact_ids=['f1'], relevance='relevant', intent='category'),
            dict(keyword='waterproof bag', decision='deferred', reason_code='unknown', reason='No evidence', query_intent='waterproof', fact_ids=[], promotion_condition='Confirm performance'),
            dict(keyword='leather bag', decision='excluded', reason_code='conflict', reason='Cotton only', query_intent='leather', fact_ids=['f1'])])
        self.save('03_keyword_decisions.json', self.ledger)
        self.export()
        self.save('05_keyword_plan.json', dict(title=[dict(keyword='storage bag')], key_features=[], description=[], not_planned=[]))
        title='Cotton Storage Bag for Organizing Items, Blue Fabric'
        self.listing=dict(marketplace='Walmart US', listing_language='English (US)', brand=None,
            product_title=title, product_description=title+'\n\n'+' '.join(['Synthetic test paragraph has enough words for checking length.']*18),
            key_features=['Cotton Material', 'Blue Fabric', 'Storage Bag'], image_plan=[dict(direction='展示收纳袋', overlay_text='')],
            variation_title_template=None, variant_titles=[], claims=[])
        self.update_listing()
        self.save('06_competitor_context.json', dict(status='skipped', reason='Fixture'))
        self.finish()

    def save(self, name, data): q.write(self.run, name, data)
    def export(self):
        _, _, _, pools = q.decision_check(self.run)
        for state, filename in q.POOL_FILES.items(): self.save(filename, pools[state])
        self.save('04_kw_tagged.json', pools['eligible'])
    def update_listing(self):
        l=self.listing
        l['claims']=[dict(field=field, text=text, fact_ids=['f1']) for field,text in q.fields(l).items() if text]
        l['metrics']=dict(title_characters=len(l['product_title']), description_words=count_words(l['product_description']), key_feature_characters=[len(x) for x in l['key_features']])
        self.save('07_listing.json', l)
    def finish(self):
        self.save('08_keyword_coverage.json', q.coverage(self.run))
        self.save('08_semantic_review.json', dict(fingerprints={name:q.digest(q.read(self.run,name)) for name in q.REVIEW_FILES},
            checks={key:dict(status='passed', notes='Synthetic fixture only') for key in ('facts_and_claims','keyword_intent','walmart_copy','variants_and_images')}))
        q.render(self.run)
    def fails(self, phrase): self.assertIn(phrase, '\n'.join(validate(self.run)))

    def test_valid(self): self.assertEqual(validate(self.run), [])
    def test_three_writing_countries_and_source_boundary(self):
        for country, language in [('CA','English (Canada)'), ('MX','Spanish (Mexico)')]:
            profile=copy.deepcopy(self.profile)
            profile['target_country']=country
            q.profile_check(profile)  # Writing support remains available.
            listing=copy.deepcopy(self.listing)
            listing.update(marketplace=q.MARKETS[country],listing_language=language)
            if country=='MX':
                listing['product_title']='Bolsa de almacenamiento de algodón azul para uso en el hogar'
                listing['key_features']=['Material: algodón', 'Color: azul', 'Para guardar objetos']
                listing['product_description']=listing['product_title']+'\n\n'+('Esta bolsa de algodón sirve para guardar los objetos en el hogar. '*13)
                listing['metrics']={'title_characters':len(listing['product_title']), 'description_words':count_words(listing['product_description']), 'key_feature_characters':[len(x) for x in listing['key_features']]}
            self.assertEqual(validate_copy(listing),[])
            with self.assertRaisesRegex(ValueError,'unsupported_source_market'): q.source_market_check(country)

    def test_other_country(self):
        self.profile['target_country']='UK'; self.save('01_product_profile.json', self.profile); self.fails('Only US, CA and MX')
    def test_stale_facts(self):
        self.profile['facts'][0]['text']='Different'; self.save('01_product_profile.json', self.profile); self.fails('facts/research changed')
    def test_missing_id(self):
        self.raw['completed_product_ids']=[]; self.save('02_kw_raw.json',self.raw); self.fails('not complete')
    def test_page_gap(self):
        self.raw['raw']['by_product_id']['123']['pages'][0]['page']=2; self.save('02_kw_raw.json',self.raw); self.fails('non-contiguous')
    def test_forged_aggregate(self):
        self.raw['raw']['keyword_data'][0]['sorftime_records'][0]['record']['volume']=999
        self.save('02_kw_raw.json',self.raw); self.fails('aggregate does not match')
    def test_false_stop(self):
        self.raw['raw']['by_product_id']['123']['pages'][0]['has_next']=True
        self.save('02_kw_raw.json',self.raw); self.fails('unsupported pagination stop')
    def test_missing_decision(self):
        self.ledger['decisions'].pop(); self.save('03_keyword_decisions.json',self.ledger); self.fails('every raw keyword')
    def test_deferred_requires_condition(self):
        self.ledger['decisions'][1].pop('promotion_condition'); self.save('03_keyword_decisions.json',self.ledger); self.fails('promotion_condition')
    def test_forged_pool(self):
        self.save('03_kw_filtered.json',[]); self.fails('stale or modified pool')
    def test_deferred_cannot_be_planned(self):
        plan=q.read(self.run,'05_keyword_plan.json'); plan['description']=[dict(keyword='waterproof bag')]
        self.save('05_keyword_plan.json',plan); self.fails('only eligible')
    def test_deferred_leak(self):
        self.listing['key_features'][0]='Waterproof Bag'; self.update_listing(); self.finish(); self.fails('leaked')
    def test_fake_coverage(self):
        report=q.read(self.run,'08_keyword_coverage.json'); report['planned'][0]['used']=False
        self.save('08_keyword_coverage.json',report); self.fails('coverage report differs')
    def test_invalid_claim(self):
        self.listing['claims'][0]['fact_ids']=['invented']; self.save('07_listing.json',self.listing); self.fails('invalid fact reference')
    def test_claim_wrong_text(self):
        self.listing['claims'][0]['text']='missing'; self.save('07_listing.json',self.listing); self.fails('claim text')
    def test_unreviewed_change(self):
        self.listing['key_features'][0]='Cotton Fabric'; self.update_listing(); self.fails('semantic review stale')
    def test_pending_review(self):
        review=q.read(self.run,'08_semantic_review.json'); review['checks']['keyword_intent']['status']='pending'
        self.save('08_semantic_review.json',review); self.fails('review pending')
    def test_missing_image(self):
        self.listing['image_plan']=[]; self.update_listing(); self.fails('image plan required')
    def test_multiple_short_paragraphs(self):
        self.listing['product_description']=self.listing['product_title']+'\n\n'+ '\n\n'.join(['word '*60]*3)
        self.update_listing(); self.fails('substantive paragraph')
    def test_invented_variant(self):
        self.listing['variant_titles']=[dict(variant_id='v1',title=self.listing['product_title'])]
        self.update_listing(); self.save('08_keyword_coverage.json',q.coverage(self.run)); self.fails('variant titles must match')
    def test_phrase_boundaries(self):
        self.assertEqual(q.match('Lightweight bathroom furniture', 'light'), '')
        self.assertEqual(q.match('Lightweight bathroom furniture', 'bat'), '')
        self.assertEqual(q.match('A Storage-Bag for use', 'storage bag'), 'Storage-Bag')
        self.assertEqual(q.match('BOLSA AZUL', 'bolsa azul'), 'BOLSA AZUL')
    def test_not_all_keywords_must_be_used(self):
        plan=q.read(self.run,'05_keyword_plan.json'); plan['title'][0]['unused_reason']='Identity expressed naturally'
        self.save('05_keyword_plan.json',plan)
        self.listing['product_title']='Cotton Organizer for Personal Items in Blue Fabric Color'
        self.listing['product_description']=self.listing['product_title']+'\n\n'+'This fabric bag is for storing your personal items. '*20
        self.update_listing(); self.finish(); self.assertEqual(validate(self.run), [])

    def test_markdown_extra_claim(self):
        with (self.run/'07_listing.md').open('a') as output: output.write('\nWaterproof guarantee')
        self.fails('Markdown differs')

    def test_zero_keywords(self):
        page=self.raw['raw']['by_product_id']['123']['pages'][0]
        page['response']={'items':[]}; page['records']=[]
        self.save('02_kw_raw.json',self.raw)
        with self.assertRaisesRegex(ValueError,'zero keywords'): q.research_check(self.run,rebuild=True)

    def test_page_cap_is_disclosed(self):
        state=self.raw['raw']['by_product_id']['123']
        state['pages']=[]
        for number in range(1,6):
            state['pages'].append(dict(page=number,response={'items':[{'term':'bag '+str(number)}]},
                records=[dict(record_pointer='/items/0',keyword_pointer='/term')],has_next=True))
        state.update(stop_reason='max_pages',pagination_capped=True)
        self.save('02_kw_raw.json',self.raw)
        q.research_check(self.run,rebuild=True)
        self.assertEqual(q.read(self.run,'02_kw_raw.json')['pagination']['capped_product_ids'],['123'])

    def test_cli_commands_and_rebind(self):
        import subprocess
        script=Path(q.__file__)
        for command in ('check-research','export','audit','review-template','render'):
            result=subprocess.run([sys.executable,str(script),command,str(self.run)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([sys.executable,str(script.parent/'validate_output.py'),str(self.run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)
        result=subprocess.run([sys.executable,str(script),'rebind',str(self.run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertTrue(all(d['decision']=='pending' for d in q.read(self.run,'03_keyword_decisions.json')['decisions']))
        self.fails('incomplete keyword decision')

    def test_review_template_invalidates_changes(self):
        import subprocess
        self.listing['key_features'][0]='Cotton Fabric'; self.update_listing()
        result=subprocess.run([sys.executable,q.__file__,'review-template',str(self.run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertTrue(all(v['status']=='pending' for v in q.read(self.run,'08_semantic_review.json')['checks'].values()))

    def test_optional_image_and_valid_variants(self):
        self.profile['image_plan_required']=False
        self.profile['variations']=[dict(variant_id='v1',attributes={'color':'Blue'},fact_ids=['f1'])]
        self.save('01_product_profile.json',self.profile)
        self.ledger['profile_sha256']=q.digest(self.profile)
        self.save('03_keyword_decisions.json',self.ledger); self.export()
        self.listing['image_plan']=[]
        self.listing['variation_title_template']='Cotton Storage Bag for Organizing Personal Items ({Color})'
        self.listing['variant_titles']=[dict(variant_id='v1',title='Cotton Storage Bag for Organizing Personal Items (Blue)')]
        self.update_listing(); self.finish(); self.assertEqual(validate(self.run),[])
        self.listing['variant_titles'][0]['title']='Short'
        self.update_listing(); self.save('08_keyword_coverage.json',q.coverage(self.run)); self.fails('50-75 characters')


    def test_real_empty_sentinel_and_error_separation(self):
        page=q.import_page({'content':[{'type':'text','text':'No data available.'}]},5)
        self.assertEqual(page['records'],[])
        self.assertEqual(page['response'],'No data available.')
        for envelope in (
            {'isError':True,'content':[{'type':'text','text':'No data available.'}]},
            {'content':[{'type':'text','text':'Request timed out'}]},
            {'content':[{'type':'text','text':'{"data":[],"error":"unauthorized"}'}]},
            {'content':[{'type':'text','text':'{malformed'}]}):
            with self.assertRaises(ValueError): q.import_page(envelope,1)

    def test_live_nested_records_cannot_be_omitted(self):
        import json
        envelope={'content':[{'type':'text','text':json.dumps({'data':[
            {'keyword':{'keyword':'storage bag','search_volume':30}},
            {'keyword':{'keyword':'waterproof bag','search_volume':100}}]})}]}
        page=q.import_page(envelope,1)
        empty=q.import_page({'content':[{'type':'text','text':'No data available.'}]},2)
        self.raw['raw']['by_product_id']['123'].update(pages=[page,empty],stop_reason='empty_page')
        self.save('02_kw_raw.json',self.raw)
        q.research_check(self.run,rebuild=True)
        raw=q.read(self.run,'02_kw_raw.json')
        self.assertEqual(raw['keywords'],['storage bag','waterproof bag'])
        raw['raw']['by_product_id']['123']['pages'][0]['records'].pop()
        self.save('02_kw_raw.json',raw)
        with self.assertRaisesRegex(ValueError,'omitted'): q.research_check(self.run,rebuild=True)

    def test_original_mcp_response_binding(self):
        page=q.import_page({'content':[{'type':'text','text':'No data available.'}]},1)
        page['response']='{"data":[]}'
        self.raw['raw']['by_product_id']['123'].update(pages=[page],stop_reason='empty_page')
        self.save('02_kw_raw.json',self.raw)
        with self.assertRaisesRegex(ValueError,'differs from saved MCP'): q.research_check(self.run,rebuild=True)

    def test_public_source_is_not_a_user_fact(self):
        self.profile['sources'][0]['kind']='public_product'
        with self.assertRaisesRegex(ValueError,'provenance'): q.profile_check(self.profile)

    def test_demo_requires_same_target_and_truthful_status(self):
        p=self.profile
        p.update(mode='public_product_demo',target_product_id='123',test_authorization='User requested a live test')
        p['sources'][0].update(kind='public_product',product_id='123')
        p['facts'][0]['status']='source_reported'
        q.profile_check(p)
        p['sources'][0]['product_id']='456'
        with self.assertRaisesRegex(ValueError,'exact target'): q.profile_check(p)
        p['sources'][0]['product_id']='123';p['brand_authorized']=True
        with self.assertRaisesRegex(ValueError,'no brand authorization'): q.profile_check(p)

    def test_demo_is_labelled_in_deliverable(self):
        p=self.profile
        p.update(mode='public_product_demo',target_product_id='123',test_authorization='User requested live testing')
        p['sources'][0].update(kind='public_product',product_id='123')
        p['facts'][0]['status']='source_reported'
        self.save('01_product_profile.json',p)
        self.ledger['profile_sha256']=q.digest(p)
        self.save('03_keyword_decisions.json',self.ledger); self.export()
        self.listing.update(mode='public_product_demo',target_product_id='123')
        self.update_listing();self.finish()
        self.assertEqual(validate(self.run),[])
        self.assertIn('公开商品流程测试',(self.run/'07_listing.md').read_text())
        self.listing.pop('mode');self.save('07_listing.json',self.listing)
        self.fails('demo output must identify')

    def test_planned_phrase_used_in_another_field(self):
        plan=q.read(self.run,'05_keyword_plan.json')
        plan['title']=[{'keyword':'storage bag','unused_reason':'test'}]
        # Eligible phrase is assigned to the title, but no title match; it is
        # still present in a feature. Actual appearance must remain true.
        self.listing['product_title']='Cotton Organizer for Personal Items in Blue Fabric Color'
        self.listing['product_description']=self.listing['product_title']+'\n\n'+'This fabric bag is for storing your personal items. '*20
        self.save('05_keyword_plan.json',plan);self.update_listing()
        report=q.coverage(self.run)
        self.assertFalse(report['planned'][0]['used'])
        self.assertTrue(report['actual_eligible'][0]['used'])
        self.assertEqual(report['summary']['planned_used_in_assigned_field'],0)
        self.assertEqual(report['summary']['actually_used'],1)

    def test_importer_cli_preserves_envelope(self):
        import subprocess
        source=self.run/'envelope.json';dest=self.run/'page.json'
        self.save('envelope.json',{'content':[{'type':'text','text':'No data available.'}]})
        script=Path(q.__file__).parent/'import_page.py'
        result=subprocess.run([sys.executable,str(script),str(source),str(dest),'--page','2'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(q.read(self.run,'page.json')['mcp_response'],q.read(self.run,'envelope.json'))

    def test_not_planned_natural_appearance_is_counted(self):
        self.raw['raw']['by_product_id']['123']['pages'][0]['response']['items'][1]['term']='bag'
        self.save('02_kw_raw.json',self.raw);q.research_check(self.run,rebuild=True)
        self.raw=q.read(self.run,'02_kw_raw.json')
        self.ledger['raw_sha256']=q.digest(self.raw)
        self.ledger['decisions'][1]=dict(keyword='bag',decision='eligible',reason_code='identity',reason='Broad identity',query_intent='bag',fact_ids=['f1'],relevance='relevant',intent='category')
        self.save('03_keyword_decisions.json',self.ledger);self.export()
        plan=q.read(self.run,'05_keyword_plan.json')
        plan['not_planned']=[dict(keyword='bag',reason='Broad term, not actively targeted')]
        self.save('05_keyword_plan.json',plan)
        report=q.coverage(self.run)
        row=next(row for row in report['actual_eligible'] if row['keyword']=='bag')
        self.assertFalse(row['planned']);self.assertTrue(row['used'])

    def test_english_cannot_pass_under_mexican_label(self):
        listing=copy.deepcopy(self.listing)
        listing.update(marketplace='Walmart Mexico',listing_language='Spanish (Mexico)')
        self.assertIn('expected Spanish','\n'.join(validate_copy(listing)))

    def test_spanish_cannot_pass_under_canadian_label(self):
        listing=copy.deepcopy(self.listing)
        listing.update(marketplace='Walmart Canada',listing_language='English (Canada)')
        listing['product_description']=listing['product_title']+'\n\n'+('Este recipiente de plástico sirve para guardar los alimentos en la cocina. '*13)
        listing['metrics']['description_words']=count_words(listing['product_description'])
        self.assertIn('expected English','\n'.join(validate_copy(listing)))

    def test_local_page_does_not_prove_provider_coverage(self):
        self.profile['target_country']='CA'
        self.raw.update(marketplace='Walmart Canada',market_verification=dict(status='verified',country='CA',evidence='https://www.walmart.ca/en/ip/123'))
        self.save('01_product_profile.json',self.profile);self.save('02_kw_raw.json',self.raw)
        with self.assertRaisesRegex(ValueError,'unsupported_source_market'):q.research_check(self.run,rebuild=True)

    def test_provider_empty_result_is_not_local_zero_demand(self):
        self.profile['target_country']='MX';self.save('01_product_profile.json',self.profile)
        self.raw['raw']['by_product_id']['123']['pages']=[q.import_page({'content':[{'type':'text','text':'No data available.'}]},1)]
        self.raw['raw']['by_product_id']['123']['stop_reason']='empty_page'
        self.save('02_kw_raw.json',self.raw)
        with self.assertRaisesRegex(ValueError,'unsupported_source_market'):q.research_check(self.run,rebuild=True)

    def test_canadian_spelling_review_preserves_brand(self):
        listing=copy.deepcopy(self.listing)
        listing.update(marketplace='Walmart Canada',listing_language='English (Canada)',brand='Color Works')
        listing['key_features']=['Color Works Fabric', 'Colour: Blue', 'Odour-resistant fabric']
        self.assertEqual(locale_signals(listing)['review_notes'],[])
        listing['key_features'][1]='Color: Blue'
        self.assertTrue(locale_signals(listing)['review_notes'])

    def test_copy_only_does_not_certify_full_pipeline(self):
        self.assertEqual(validate_copy(self.listing),[])
        (self.run/'02_kw_raw.json').unlink()
        self.fails('missing required file')

    def test_check_source_cli_stops_before_research(self):
        import subprocess
        self.profile['target_country']='CA';self.save('01_product_profile.json',self.profile)
        result=subprocess.run([sys.executable,q.__file__,'check-source',str(self.run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('unsupported_source_market',result.stdout)


if __name__=='__main__': unittest.main()
