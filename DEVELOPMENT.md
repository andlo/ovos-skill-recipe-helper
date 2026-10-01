# Recipe Helper — v1 working end-to-end

**Status: v1 fully working end-to-end (2026-08-21) - data pipeline
run for all 3 native languages, skill lookup logic implemented and
tested against the real bundled data (native lookup + English-pivot
translation fallback both confirmed live, including with a real
NLLB model). Not yet done: `setup.py`/CI validation of the packaged
skill, and no real device/OVOS-instance testing yet - only direct
Python-level testing so far.**

## Data pipeline status (2026-08-21)

`data/build_data.py` discovers and parses recipes for the three
native languages. Verified against real pages, not just written and
assumed correct - three parsing bugs were found and fixed this way
(see commit history), and one gap was found and deliberately left
open rather than papered over:

- **en-us, de-de, da-dk** all parse correctly on spot-checked pages.
- **da-dk hit rate**: 12/20 on a live sample after fixing the
  list-style assumption (numbered-only missed real recipes using `*`
  or `:` instead of `#`) - remaining misses are a mix of genuine
  non-recipe pages (technique articles, category-index pages) and...
- **decided, permanently out of scope**: ~20% of da-dk recipes use a
  third infobox family (`{{WikiKogebogen/Mangor}}`), prose-only
  historical recipes with no ingredients/steps structure to extract.
  Decided 2026-08-21 ([#4](https://github.com/andlo/ovos-skill-recipe-helper/issues/4),
  closed) to exclude these from this skill entirely rather than
  force-fit or special-case them - da-dk-only, prose content, not
  the ingredients+steps interaction this skill is built around. If
  ever built, the right shape is a separate skill (offline
  historical/heritage-recipe reader), not an extension of this one.
- No full data run has been executed yet (`python3 data/build_data.py
  <lang>` against the complete candidate list) - only small live
  samples during development. Full runs, and de-de/en-us hit-rate
  numbers at scale, are still open.

**Full runs completed (2026-08-21) - actual yield:**

| Lang | Candidates | Recipes saved | Coverage |
|---|---|---|---|
| en-us | 3,850 | **3,129** | 81.3% |
| de-de | 640 | **341** | 53.3% |
| da-dk | 458 | **156** | 34.1% |

da-dk/de-de's smaller yield (partly the Mangor exclusion above,
partly the genuine size difference between Wikibooks' English
Cookbook and its Danish/German counterparts - see "Multi-language"
table) is why the skill's lookup logic doesn't stop at native data -
see "Lookup architecture" below.

## Lookup architecture: native-first, English-pivot fallback

Given the yield numbers above, a Danish or German query that misses
the small native corpus very likely still exists in the 3,129-recipe
English one. So `__init__.py`'s `get_recipe_answer()` generalizes
wiki-offline's Path A/Path B pattern from "per-language, all or
nothing" to "per-query, native falls through to translated": every
language - INCLUDING da-dk/de-de themselves - retries via
"translate the phrase to English, look up in the big English corpus,
translate the matched recipe back" whenever its own native lookup
misses. Confirmed working end-to-end 2026-08-21 (real NLLB
translation, a da-dk query for "Kachumbari" - which only exists
natively in English - correctly found, translated, and spoken back
in Danish, framing sentences included).

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
- es-es parser needs to live as its own function in a per-language
  dispatch table (`PARSERS = {"en-us": parse_en, "es-es": parse_es,
  ...}`) rather than branching inside one generic parser - the
  template-param structure is different enough to want isolation, not
  an if/else tangle.
- fr-fr/it-it/pt-pt: parser should degrade gracefully (skip/flag
  pages that don't parse cleanly, same spirit as `{{Incomplete
  recipe}}` filtering) rather than guess at missing structure -
  and log a per-language parse-coverage percentage during build,
  same idea as `ovos_localize`'s coverage scoring, so there's a real
  number instead of an assumption.

**Decided 2026-08-21, tracked as enhancement issues (not v1):**
- Recipe search/matching: v1 ships exact-title lookup only (like
  wiki-offline). Ingredient-based search ("recipes containing
  chicken") is a meaningfully bigger feature - reverse index,
  multi-result handling, cross-language ingredient-name matching -
  tracked as [#1](https://github.com/andlo/ovos-skill-recipe-helper/issues/1).
- Step-by-step spoken walkthrough: v1 reads the whole recipe in one
  response. Conversational step-by-step ("next step") needs real
  session state this portfolio doesn't have yet - tracked as
  [#2](https://github.com/andlo/ovos-skill-recipe-helper/issues/2).
  **v1 constraint to keep this cheap later:** store `steps` as a
  list of strings all the way through the data pipeline, not
  flattened into one blob at parse time.
- `[mcp]` extra: same pattern as geography/geometry/holidays/
  calculator/convert/wiki-offline, blocked on the `ovos-tool-adapters`
  fork landing first - tracked as
  [#3](https://github.com/andlo/ovos-skill-recipe-helper/issues/3).

## Category
**Daily**

## Tags
#recipes #cooking #food #idea #design-doc
