# Recipe Helper — a design document, not a working skill yet

**Status: idea and sourcing-investigation stage.**

## The idea

"Hvordan laver jeg pandekager", "hvad skal jeg bruge til carbonara",
"hvor mange gram er 2 dl mel" - offline recipes plus the ingredient/
measurement conversion `ovos-skill-convert` already solves.

## Sourcing: same wiki family, same method as wiki-offline

**Wikibooks Cookbook** (`en.wikibooks.org/wiki/Cookbook:Table_of_Contents`)
is a real, actively-maintained, CC-BY-SA-4.0-licensed recipe
collection - same license family as Wikipedia itself, same MediaWiki
platform, and (per a third-party dump found during research,
[gossminn/wikibooks-cookbook on Hugging Face](https://huggingface.co/datasets/gossminn/wikibooks-cookbook))
confirmed to contain real, structured recipe pages with titles,
ingredients, and instructions.

This means `ovos-skill-wiki-offline/data/build_data.py`'s existing
approach - fetch wikitext via the MediaWiki API, extract structured
content, verify against a second source before trusting completeness
- is very likely directly adaptable here, fetching straight from
`wikibooks.org` rather than depending on a third-party dump.
**Not yet verified**: whether recipe wikitext parses as cleanly as
Wikipedia's `[[Article]]`-link-based vital-articles lists did, or
whether recipe pages have enough internal structural variance
(ingredient list formatting, instruction step formatting) to need a
meaningfully different parser. Needs hands-on investigation of real
Cookbook pages before assuming a straight port of the existing
pipeline works.

## Relationship to ovos-skill-convert

Not a competing measurement-conversion implementation - this skill
would depend on `ovos-skill-convert` for any unit conversion inside a
recipe ("how many grams is 2 dl of flour"), reusing its 19 existing
categories rather than duplicating that logic.

## Multi-language: an open question, not yet resolved

Wikibooks has editions in other languages (de.wikibooks.org,
fr.wikibooks.org, etc.), but unlike Wikipedia's vital-articles lists
(which are explicitly curated to be comparable across languages),
each language edition's Cookbook is its own independently-grown
collection with no guarantee of a comparable-scale or comparable-
content collection existing per language. This needs the same kind
of per-language verification wiki-offline already did (checking
actual page counts and content, not assuming symmetry) before
committing to which languages a v1 could support - very possibly
en-us only at first, expanding once other editions are checked.

## Open questions (resolve before implementing)

- How large is the usable Cookbook subset once non-recipe pages
  (technique articles, equipment guides, ingredient reference pages)
  are filtered out - needs checking, not assumed from the raw page
  count.
- Recipe search/matching: exact-title lookup only (like wiki-offline)
  vs. some notion of "recipes containing ingredient X" - the latter
  is a meaningfully bigger feature, probably out of scope for v1.
- Step-by-step spoken walkthrough (read one step, wait, "next step")
  vs. read-the-whole-thing-at-once - a real UX decision, not just an
  implementation detail.

## Category
**Daily**

## Tags
#recipes #cooking #food #idea #design-doc
