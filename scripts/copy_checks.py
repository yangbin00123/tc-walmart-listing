#!/usr/bin/env python3
"""Walmart copy-format checks only; never certifies keyword-source coverage."""
from __future__ import annotations
import json
import re
import sys
import unicodedata
from pathlib import Path

def count_words(text: str) -> int:
    return len(re.findall(r"\b[^\W_]+(?:['’-][^\W_]+)?\b", text, flags=re.UNICODE))



def locale_signals(listing):
    title = listing.get('product_title', '')
    text = listing.get('product_description', '')
    if not isinstance(text, str):
        text = ''
    if isinstance(title, str) and text.startswith(title):
        text = text[len(title):]
    words = re.findall(r"[^\W\d_]+", unicodedata.normalize('NFC', text).casefold())
    english = set('the these this with and your for from which their its they when into that each you is are'.split())
    spanish = set('el la los las del de para con una un que en su sus por este esta estos estas puedes alimentos'.split())
    signals = {'English': sum(w in english for w in words), 'Spanish': sum(w in spanish for w in words)}
    expected = 'Spanish' if listing.get('marketplace') == 'Walmart Mexico' else 'English'
    other = 'English' if expected == 'Spanish' else 'Spanish'
    errors = []
    notes = []
    if signals[expected] < 5 or signals[other] > signals[expected]:
        notes.append('copy language requires review: expected ' + expected + '; body language signals do not support its label')
    # These are review prompts, not a general dialect classifier or ban on brand names.
    if listing.get('marketplace') == 'Walmart Canada':
        copy_text = ' '.join([str(listing.get('product_title','')), str(listing.get('product_description','')),
                              *[str(x) for x in listing.get('key_features',[])]])
        brand = listing.get('brand')
        if isinstance(brand,str) and brand: copy_text=copy_text.replace(brand,'')
        american = [w for w in ('color','colors','odor','odors','liter','liters') if re.search(r'\b'+w+r'\b',copy_text,re.I)]
        if american: notes.append('Review Canadian spelling outside brand/model names: ' + ', '.join(american))
    return {'expected_language_family': expected, 'signals': signals, 'errors': errors, 'review_notes': notes,
            'limitation': 'Signals detect gross language-label mismatch; naturalness, dialect, brands and short image text require semantic review.'}


def _validate_copy(listing):
    errors = []
    title = listing.get("product_title")
    description = listing.get("product_description")
    features = listing.get("key_features")
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        errors.append("product_title must be nonempty and at most 150 Unicode characters")
    if not isinstance(description, str):
        errors.append("product_description must be a string")
    else:
        body = description
        paragraphs = re.split(r"\n\s*\n", body.strip())
        if not any(count_words(paragraph) >= 150 for paragraph in paragraphs):
            errors.append("product_description needs a substantive paragraph of at least 150 words")
    if not isinstance(features, list) or not 3 <= len(features) <= 10:
        errors.append("key_features must contain 3-10 items")
    elif any(not isinstance(item, str) or not item.strip() or len(item) > 80 for item in features):
        errors.append("each key feature must be non-empty and at most 80 Unicode characters")

    marketplace_languages = {
        "Walmart US": "English (US)",
        "Walmart Canada": "English (Canada)",
        "Walmart Mexico": "Spanish (Mexico)",
    }
    if listing.get("marketplace") not in marketplace_languages:
        errors.append("marketplace must be Walmart US, Walmart Canada, or Walmart Mexico")
    elif listing.get("listing_language") != marketplace_languages[listing.get("marketplace")]:
        errors.append("listing_language does not match marketplace")

    serialized = json.dumps(listing, ensure_ascii=False).lower()
    forbidden_fields = ["search_terms", "item_highlight", "rufus", "a_plus_plan"]
    for field in forbidden_fields:
        if field in listing:
            errors.append(f"Amazon-only field is not allowed: {field}")
    if "sellersprite" in serialized or "卖家精灵" in serialized:
        errors.append("listing must not contain SellerSprite references")

    metrics = listing.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("listing metrics object is required")
    else:
        expected_feature_lengths = [len(item) for item in features] if isinstance(features, list) else []
        if metrics.get("title_characters") != (len(title) if isinstance(title, str) else None):
            errors.append("metrics.title_characters is inaccurate")
        if metrics.get("description_words") != (count_words(description) if isinstance(description, str) else None):
            errors.append("metrics.description_words is inaccurate")
        if metrics.get("key_feature_characters") != expected_feature_lengths:
            errors.append("metrics.key_feature_characters is inaccurate")


    # Language signals are advisory; actual language is checked in semantic review.
    return errors


def validate_copy(listing):
    try:
        return _validate_copy(listing)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
        return ['invalid copy structure: ' + str(error)]


def main():
    if len(sys.argv) != 2:
        print('Usage: copy_checks.py <copy JSON>')
        return 2
    try:
        listing=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        errors=validate_copy(listing)
        print(json.dumps({'scope':'copy_format_and_language_signals_only',
            'status':'failed' if errors else 'passed', 'keyword_research_verified':False,
            'errors':errors,'locale':locale_signals(listing)},ensure_ascii=False,indent=2))
        return int(bool(errors))
    except (ValueError,OSError,TypeError,AttributeError) as error:
        print('ERROR: '+str(error));return 1

if __name__=='__main__':raise SystemExit(main())
