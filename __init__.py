"""
skill OVOS Recipe Helper
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

SCAFFOLD ONLY - data pipeline (data/build_data.py) and the actual
recipe-matching logic below are NOT implemented yet. See README.md
"Open questions" for what's still undecided (recipe search/matching
approach, step-by-step vs whole-recipe delivery) before writing
handle_common_query()/handle_fallback() for real - those decisions
should be made together, not assumed here.

Offline recipes sourced from Wikibooks Cookbook (and each language's
own Wikibooks cookbook-equivalent - see README.md for the per-language
survey). Depends on ovos-skill-convert for any unit conversion inside
a recipe ("how many grams is 2 dl of flour") rather than duplicating
that logic - see README.md "Relationship to ovos-skill-convert".

English, Danish, and German are the planned native/bundled-data
languages (see README.md "Multi-language" table for why). Any other
language falls back to the same ad-hoc runtime translation pattern
already proven in ovos-skill-wiki-offline - see that skill's
DEVELOPMENT.md "Ad-hoc translation for unsupported languages" for the
full reasoning and the caching/blocking pitfalls already found there
(a first translator load can block ~40s - must not happen inside
can_answer()).
"""

import json
from pathlib import Path

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import common_query

SKILL_ROOT = Path(__file__).resolve().parent
DATA_DIR = SKILL_ROOT / "data"

# Native/bundled-data languages - see README.md "Multi-language"
# table. Any language NOT listed here gets ad-hoc translation only,
# same default-path reasoning as wiki-offline.
SUPPORTED_LANGS = ("en-us", "da-dk", "de-de")
TRANSLATION_PIVOT_LANG = "en-us"


def _load_recipes(lang):
    """Loads data/recipes_<lang>.json if it exists. Returns {} for
    every language right now - data/build_data.py hasn't been
    written yet, so no data files exist. Structure of the returned
    dict (title -> parsed recipe) is a placeholder, not yet decided
    against the actual per-language wikitext variance documented in
    README.md (es-es packs ingredients/steps into template params;
    fr-fr/it-it/pt-pt have inconsistent or missing infoboxes)."""
    path = DATA_DIR / f"recipes_{lang}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# lang -> {title -> parsed recipe} - empty until build_data.py exists
RECIPES_BY_LANG = {lang: _load_recipes(lang) for lang in SUPPORTED_LANGS}


class RecipeHelper(OVOSSkill):
    """Not yet implemented - this is a scaffold, not a working skill.

    Planned pattern (matching geometry/geography/calculator/convert/
    wiki-offline): @common_query decorator on plain OVOSSkill, not
    the deprecated CommonQuerySkill base class - see those skills'
    history for why. handle_common_query() below is a stub; wiring
    up real recipe lookup depends on the still-open questions in
    README.md (exact-title vs ingredient-search matching, step-by-
    step vs whole-recipe spoken delivery) being decided first.
    """

    def initialize(self):
        # TODO: register intents/vocab once matching approach (see
        # README.md open questions) is decided.
        pass

    @common_query()
    def handle_common_query(self, phrase, lang=None):
        """Stub - always returns None (no answer) until real recipe
        lookup is implemented. Deliberately raises nothing and
        crashes nothing: an unimplemented Common Query handler must
        stay silent, not error, so it doesn't break the pipeline for
        other skills while this one is still under construction."""
        return None
