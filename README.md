# Recipe Helper — sourcing investigation complete, scaffolding in progress

**Status: sourcing and multi-language investigation resolved
(2026-08-21); scaffold underway, data pipeline and skill logic not
yet implemented.**

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
- is directly adaptable here, fetching straight from
`wikibooks.org` rather than depending on a third-party dump.

**Verified 2026-08-21** (live MediaWiki API calls, `en.wikibooks.org`):
recipe wikitext parses *more* cleanly than vital-articles prose did.
Every sample recipe checked wraps its data in a `{{recipesummary}}`
infobox template (category, servings, time, difficulty, image) followed
by `== Ingredients ==` (bulleted, wikilinked ingredient names) and
`== Procedure ==` (numbered steps). A quality-flag template,
`{{Incomplete recipe|reason=...}}`, appears on some pages and can be
used to skip/deprioritize low-quality entries, same spirit as
stub-filtering in wiki-offline.

Filtering is also easier than assumed: `Category:Cookbook` (the
parent) holds only 37 non-recipe pages (Equipment, Ingredients,
Ethics, Manual of Style, etc.) - the actual recipes live separately
under `Category:Recipes` (3,824+ pages across 15 subcategories). No
guesswork needed to tell them apart.

## Relationship to ovos-skill-convert

Not a competing measurement-conversion implementation - this skill
would depend on `ovos-skill-convert` for any unit conversion inside a
recipe ("how many grams is 2 dl of flour"), reusing its 19 existing
categories rather than duplicating that logic.

## Multi-language: verified 2026-08-21, resolved

Wikibooks has editions in other languages, and as expected each
Cookbook is its own independently-grown collection, not symmetric
with English. Checked all 8 target languages live against each
language's MediaWiki API (subpage counts are raw - unfiltered
totals under the cookbook root, include some non-recipe pages, so
treat as upper bounds not final corpus sizes):

| Lang | Root page | Raw subpage count | Structured infobox? | Steps |
|---|---|---|---|---|
| en-us | `Cookbook:` (`Category:Recipes`) | 3,824+ | Yes, `{{recipesummary}}` | numbered |
| de-de | `Kochbuch/ Alle Rezepte` | 500+ (capped, likely more) | not directly checked, same category pattern as en | - |
| nl-nl | `Kookboek/` | 1,113 | Yes, `{{Infobox recept}}` | - |
| fr-fr | `Livre de cuisine/` | 1,523 | Inconsistent - breadcrumb template only, no data infobox on some pages | bulleted, not always numbered |
| pt-pt | `Livro de receitas/` | 2,128 | Inconsistent - some recipes lack any infobox | numbered |
| es-es | `Artes culinarias/Recetas/` | 1,588 | Yes, but ingredients+steps are template *parameters* (`{{Artes culinarias/Datos de receta|...}}`), not separate sections | numbered |
| it-it | `Libro di cucina/` | 842 | No infobox found in samples, plain prose+bullets | bulleted, not numbered |
| da-dk | `WikiKogebogen/<name>` (subpages, no Category tree) | 458 | Yes, `{{Infoboks opskrift}}` | numbered |

Danish is structurally the odd one out for *discovery*: no
`Category:` tree at all, just subpages under `WikiKogebogen/` listed
via a manually-maintained index page - discovery needs
`action=query&list=allpages&apprefix=WikiKogebogen/` instead of
category traversal. But the *per-recipe* structure (infobox +
Ingredienser + Fremgangsmåde) is practically identical to English -
same parser, different discovery step.

**Translation strategy: adopt wiki-offline's Path A / Path B pattern
directly**, no new design needed. Native/bundled data (Path A) is
worth the build+maintenance cost only for languages likely to be
asked about often - candidates: en-us, likely de-de, and da-dk
(despite smaller raw count, it's the primary language this skill will
actually be spoken in). Everything else defaults to Path B: on-demand
translation of question and answer via whatever OVOS translate
plugin is configured (`ovos-translate-plugin-nllb` recommended, local
model, no third-party runtime dependency) - zero bundled data, zero
extra code, ~2-5s added latency. No language is blocked; unsupported
just means "translated" rather than "unavailable."

## Open questions

**Resolved 2026-08-21:**
- ~~Usable Cookbook subset size~~ - `Category:Recipes` (en) cleanly
  separates recipes from the 37 non-recipe pages; other languages'
  exact filterable/non-recipe split still needs the same per-language
  pass build_data.py will do at build time, but the *mechanism*
  (category or `{{AutoCat}}`/quality-template signals) exists in every
  language checked.
- ~~Multi-language scope~~ - see table above; wiki-offline's Path A/B
  pattern reused directly.
- ~~Wikitext parseability~~ - confirmed cleaner than expected
  (infobox template + `==Ingredients==`/`==Procedure==` sections),
  though es-es needs a different parser branch (ingredients/steps as
  template params, not sections) and fr-fr/it-it/pt-pt need
  tolerance for missing infoboxes and non-numbered step lists.

**Still open (deferred to v1 implementation, not blocking scaffold):**
- Recipe search/matching: exact-title lookup only (like wiki-offline)
  vs. some notion of "recipes containing ingredient X" - the latter
  is a meaningfully bigger feature, probably out of scope for v1.
- Step-by-step spoken walkthrough (read one step, wait, "next step")
  vs. read-the-whole-thing-at-once - a real UX decision, not just an
  implementation detail.
- `[mcp]` extras: per the pattern used on geography/geometry/holidays/
  calculator/convert/wiki-offline, worth designing in once
  `ovos-tool-adapters` fork lands - not before.

## Category
**Daily**

## Tags
#recipes #cooking #food #idea #design-doc
