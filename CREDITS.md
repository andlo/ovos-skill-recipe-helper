# Data credits and licensing

## Source

**Wikibooks Cookbook** and each language's own cookbook-equivalent -
all live under the Wikibooks family (`{lang}.wikibooks.org`), same
MediaWiki platform and CC BY-SA 4.0 license family as Wikipedia
itself. See README.md "Sourcing" and "Multi-language" for the full
per-language survey (root pages, page counts, structural notes),
gathered via live `action=parse`/`action=query` MediaWiki API calls
on 2026-08-21.

Root pages surveyed:

| Lang | Root page |
|---|---|
| en-us | `en.wikibooks.org/wiki/Cookbook:Table_of_Contents` |
| de-de | `de.wikibooks.org/wiki/Kochbuch` |
| da-dk | `da.wikibooks.org/wiki/Wikimedia_Kogebogen` |
| nl-nl | `nl.wikibooks.org/wiki/Kookboek` |
| fr-fr | `fr.wikibooks.org/wiki/Livre_de_cuisine` |
| es-es | `es.wikibooks.org/wiki/Artes_culinarias` |
| pt-pt | `pt.wikibooks.org/wiki/Livro_de_receitas` |
| it-it | `it.wikibooks.org/wiki/Libro_di_cucina` |

## License

Wikibooks page text is **CC BY-SA 4.0**. Once `data/build_data.py`
exists and bundles extracted recipe data (title, ingredients, steps),
this file needs the same attribution treatment as
`ovos-skill-wiki-offline`'s CREDITS.md: content sourced from
Wikibooks, © Wikibooks contributors, CC BY-SA 4.0 - not yet done
here since no data is bundled yet.

This does NOT extend to the skill's own code, which remains
GPL-3.0-or-later per `LICENSE`.

## Snapshot, not a live mirror (planned, once build_data.py exists)

Same pattern as wiki-offline: each `data/recipes_<lang>.json` will be
a one-time snapshot from when `data/build_data.py <lang>` was run,
not automatically kept in sync with Wikibooks' ongoing edits.
