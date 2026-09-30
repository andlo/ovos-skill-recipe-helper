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

Fully offline recipes sourced from Wikibooks Cookbook (and each
language's own Wikibooks cookbook-equivalent) - see
data/build_data.py and README.md for the exact sourcing and
per-language survey.

v1 scope, decided 2026-08-21 (see README.md "Still open" and closed
issues #1/#2/#4): exact-title lookup only, not ingredient search
(#1) - "how do I make bobotie", not "what uses chicken". Whole
recipe read out in one response, not step-by-step (#2) - `steps`
stays a list of strings throughout so that's cheap to add later.
Danish {{WikiKogebogen/Mangor}} prose-only historical recipes are
permanently out of scope (#4) - see build_data.py's parse_da_recipe()
docstring.

NATIVE-FIRST, ENGLISH-FALLBACK-WITH-TRANSLATION - a real
generalization of ovos-skill-wiki-offline's Path A/Path B pattern,
not a copy of it. wiki-offline treats "supported" as all-or-nothing
per language (a language either has a full bundled dataset or gets
100% ad-hoc translation). Recipe-helper's native da-dk/de-de datasets
are real but much smaller than en-us after the actual build run
(2026-08-21): en-us 3,129 recipes, de-de 341, da-dk 156 - a Danish or
German query that misses the small native corpus would previously
just fail, even though the SAME dish very likely exists in the
3,129-recipe English corpus. So here, EVERY language - including
da-dk/de-de themselves - falls through to "translate the phrase to
English, look up in the big English corpus, translate the matched
recipe back" whenever the native lookup (if any) comes up empty.
This subsumes wiki-offline's pattern rather than replacing it: a
language with zero native data (fr-fr, es-es, nl-nl, pt-pt, it-it)
just always takes this path, same as before.

Translation only ever happens at ANSWER time, on the one matched
recipe - never bulk-pretranslated into a data file. Same reasoning
as wiki-offline: translates only what's actually asked about, adds
no bundled data, works for ANY language the user has a translator
plugin configured for - not just the languages with native recipes.

Depends on ovos-skill-convert for any unit conversion inside a
recipe ("how many grams is 2 dl of flour") rather than duplicating
that logic - see README.md "Relationship to ovos-skill-convert".
"""
import json
import re
from pathlib import Path

from ovos_workshop.skills.fallback import FallbackSkill
from ovos_workshop.decorators import common_query, fallback_handler, intent_handler
from ovos_utils.parse import match_one

SKILL_ROOT = Path(__file__).resolve().parent
DATA_DIR = SKILL_ROOT / "data"

FUZZY_MATCH_THRESHOLD = 0.85

# Native/bundled-data languages - see README.md "Multi-language"
# table and data/build_data.py's actual per-language yield.
RECIPE_LANGS = ("en-us", "da-dk", "de-de")
TRANSLATION_PIVOT_LANG = "en-us"

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _load_recipes(lang):
    path = DATA_DIR / f"recipes_{lang}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# lang -> {wikibooks-title -> parsed recipe dict}
RECIPES_BY_LANG = {lang: _load_recipes(lang) for lang in RECIPE_LANGS}
# lang -> {lowercased recipe title -> canonical wikibooks-title key}
# NOTE: matches against recipe["title"] (the cleaned display title,
# e.g. "Bobotie"), not the dict key (the raw wikibooks page title,
# e.g. "Cookbook:Bobotie") - the dict key is only used to look the
# recipe back up in RECIPES_BY_LANG.
TITLE_INDEX_BY_LANG = {
    lang: {recipe["title"].lower(): key for key, recipe in recipes.items()}
    for lang, recipes in RECIPES_BY_LANG.items()
}
ALL_TITLES_LOWER_BY_LANG = {
    lang: list(index.keys()) for lang, index in TITLE_INDEX_BY_LANG.items()
}


# Deliberately simple prefix stripping, not full NLU - same
# "safety net, not a second intent parser" reasoning as
# wiki-offline. Only needed for RECIPE_LANGS: any OTHER language
# translates the WHOLE phrase to en-us first (see
# lookup_recipe_via_translation below) and reuses THESE en-us
# prefixes on the translated phrase - no per-language prefix list
# needed for languages that never get a native lookup at all.
QUESTION_PREFIXES = {
    "en-us": [
        "how do i make ", "how do you make ", "how to make ",
        "how do i cook ", "how do i bake ", "how do you cook ", "how do you bake ",
        "what do i need for ", "what do i need to make ",
        "what ingredients do i need for ",
        "recipe for ", "give me a recipe for ", "give me the recipe for ",
    ],
    "da-dk": [
        "hvordan laver jeg ", "hvordan laves ", "hvordan tilbereder jeg ",
        "hvordan bager jeg ", "hvordan koger jeg ",
        "hvad skal jeg bruge til ", "hvad skal der bruges til ",
        "hvilke ingredienser skal jeg bruge til ",
        "opskrift på ", "giv mig en opskrift på ", "giv mig opskriften på ",
    ],
    "de-de": [
        "wie mache ich ", "wie macht man ", "wie bereite ich zu ",
        "wie koche ich ", "wie backe ich ",
        "was brauche ich für ", "welche zutaten brauche ich für ",
        "rezept für ", "gib mir ein rezept für ",
    ],
}


# articles in front of a dish: "how do i make a cake", "en kage", "einen Kuchen"
ARTICLES = r"^(?:a|an|the|some|en|et|nogle|ein|eine|einen|einem)\s+"


def _strip_question_prefix(phrase, lang):
    stripped = phrase.strip().rstrip("?").strip()
    lower = stripped.lower()
    for prefix in QUESTION_PREFIXES.get(lang, []):
        if lower.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def resolve_recipe_key(dish_name, lang):
    """Exact match first (case-insensitive), then fuzzy as a safety
    net for STT variation - same resolve_title() pattern as
    wiki-offline. Returns the dict key into RECIPES_BY_LANG[lang]
    (the raw wikibooks title), or None."""
    if not dish_name or lang not in RECIPES_BY_LANG:
        return None
    title_index = TITLE_INDEX_BY_LANG[lang]
    key = re.sub(ARTICLES, "", dish_name.strip().lower()).strip()
    if key in title_index:
        return title_index[key]
    all_titles = ALL_TITLES_LOWER_BY_LANG.get(lang, [])
    if not all_titles:
        return None
    match, score = match_one(key, all_titles)
    if score >= FUZZY_MATCH_THRESHOLD:
        return title_index[match]
    # "pancakes" -> "Blueberry Pancakes", "carbonara" -> "Carbonara Pasta":
    # the dish as a whole word (singular or plural) in a title, shortest
    # title first. Only for a real word, so "tea" or "a" pick nothing.
    # Danish/German compounds end in the dish ("kikærtepandekage",
    # "eierpfannkuchen") and have other plurals ("pandekager").
    if len(key) < 4:
        return None
    compound = lang in ("da-dk", "de-de")
    endings = ("s", "es", "r", "er", "n", "en") if compound else ("s", "es")
    stems = [key] + [key[:-len(e)] for e in endings if key.endswith(e) and len(key) - len(e) >= 4]
    for stem in stems:
        head = "" if compound else r"(?<!\w)"
        pattern = re.compile(rf"{head}{re.escape(stem)}(?:{'|'.join(endings)})?(?!\w)")
        found = [t for t in all_titles if pattern.search(t)]
        if found:
            return title_index[min(found, key=len)]
    return None


def is_exact_recipe(phrase, lang):
    """True when the dish in `phrase` is a recipe title as it stands
    ("how do i make pancakes" and a recipe called "Pancakes"), not just a
    fuzzy guess - enough to answer Common Query with full confidence."""
    dish_name = _strip_question_prefix(phrase, lang)
    dish = re.sub(ARTICLES, "", (dish_name or "").strip().lower()).strip()
    return bool(dish) and dish in TITLE_INDEX_BY_LANG.get(lang, {})


# the prefix the recipe intent's {dish} is looked up with
RECIPE_PREFIX = {"en-us": "recipe for ", "da-dk": "opskrift på ", "de-de": "rezept für "}


def lookup_recipe(phrase, lang):
    """Native-only lookup: strip a question prefix, resolve the
    remaining dish name against THIS language's own recipe index.
    Returns a recipe dict or None - never raises, never translates.
    (Translation fallback is a separate, explicit step - see
    lookup_recipe_via_translation - so this function's behavior is
    predictable regardless of whether a translator is configured.)"""
    dish_name = _strip_question_prefix(phrase, lang)
    if dish_name is None:
        return None
    key = resolve_recipe_key(dish_name, lang)
    if key is None:
        return None
    return RECIPES_BY_LANG[lang][key]


# v1 decision (#2): whole recipe in one response, not step-by-step.
# Kept as a single small template dict rather than a full i18n
# framework - only 3 languages ever hit this (translated answers are
# already in the target language BY THE TIME they reach here, so
# this only needs entries for en-us/da-dk/de-de, never for a
# translation-fallback language directly).
ANSWER_TEMPLATES = {
    "en-us": {"need": "For {title} you'll need: {ingredients}.", "steps": "Here's what to do: {steps}"},
    "da-dk": {"need": "Til {title} skal du bruge: {ingredients}.", "steps": "Sådan gør du: {steps}"},
    "de-de": {"need": "Für {title} brauchst du: {ingredients}.", "steps": "So geht's: {steps}"},
}


def format_recipe_answer(recipe, lang, translator=None):
    """Joins the structured recipe dict into one spoken response -
    ingredients, then steps, in order. `steps` stays a LIST going
    into this function (see module docstring / issue #2) - joining
    only happens here, right before speaking, so a future
    step-by-step mode can call the same lookup/translation pipeline
    and just skip this join.

    For a language with NO framing template (anything outside
    en-us/da-dk/de-de - i.e. a pure translation-fallback language
    like fr-fr) and a translator available, translates the English
    template's two framing sentences too - otherwise the recipe
    CONTENT would be in the target language (already translated by
    lookup_recipe_via_translation) but wrapped in English "For X
    you'll need"/"Here's what to do" framing, which would sound
    broken/inconsistent, not just imperfect. Falls back to the
    English framing only if no translator is available at this point
    (shouldn't normally happen - reaching here without a translator
    would mean the recipe itself couldn't have been translated
    either)."""
    template = ANSWER_TEMPLATES.get(lang)
    if template is None:
        template = ANSWER_TEMPLATES["en-us"]
        if translator is not None:
            try:
                template = {
                    "need": translator.translate(template["need"], lang, "en-us"),
                    "steps": translator.translate(template["steps"], lang, "en-us"),
                }
            except Exception:
                template = ANSWER_TEMPLATES["en-us"]
    ingredients = ", ".join(recipe["ingredients"])
    steps = " ".join(f"{i}. {s}" for i, s in enumerate(recipe["steps"], 1))
    need_part = template["need"].format(title=recipe["title"], ingredients=ingredients)
    steps_part = template["steps"].format(steps=steps)
    return f"{need_part} {steps_part}"


# --- Translation infra ---
# Deliberately duplicated from ovos-skill-wiki-offline rather than
# imported - this skill has no hard dependency on that one (see
# requirements.txt), same "not a dependency" stance as
# ovos-skill-convert. Same known pitfalls apply here as there (see
# wiki-offline's DEVELOPMENT.md for the full writeup): a first NLLB
# load can BLOCK for ~40s, so the blocking path (_get_translator())
# must never run inside can_answer() - only the cheap, non-blocking
# _translator_configured() check may run there.

_translator_cache = {}


def _translator_configured():
    """Cheap, non-blocking config check - safe to call from
    can_answer()."""
    try:
        from ovos_config import Configuration
        return bool(Configuration().get("language", {}).get("translation_module"))
    except Exception:
        return False


def _get_translator():
    """Lazily instantiates and caches whatever translation plugin the
    user has configured, generically. Can BLOCK for tens of seconds
    on first call - never call from can_answer(), only from
    handle_common_query()/handle_fallback()."""
    if "translator" not in _translator_cache:
        try:
            from ovos_plugin_manager.language import OVOSLangTranslationFactory
            _translator_cache["translator"] = OVOSLangTranslationFactory.create()
        except Exception:
            _translator_cache["translator"] = None
    return _translator_cache["translator"]


def _translate_text(translator, text, target, source):
    """Sentence-split before translating, then rejoin - NLLB (and
    likely similar MT plugins) silently truncates a multi-sentence
    string to just its first sentence rather than erroring (found
    during wiki-offline's development, same risk applies to any
    multi-sentence ingredient/step line here)."""
    sentences = SENTENCE_SPLIT_RE.split(text.strip())
    translated = [translator.translate(s, target, source) for s in sentences]
    return " ".join(translated)


def _translate_recipe(recipe, target_lang, translator):
    """Translates title + every ingredient + every step - each list
    item is its own _translate_text() call rather than joining the
    whole list into one blob first, since a naive join would re-
    trigger the exact multi-sentence-truncation risk _translate_text
    already guards against, just one level up. Returns a new dict in
    the same shape as a native recipe (see RECIPE_SHAPE in
    build_data.py) - format_recipe_answer() doesn't need to know or
    care whether a recipe it's formatting was native or translated."""
    return {
        "title": _translate_text(translator, recipe["title"], target_lang, TRANSLATION_PIVOT_LANG),
        "ingredients": [_translate_text(translator, i, target_lang, TRANSLATION_PIVOT_LANG)
                         for i in recipe["ingredients"]],
        "steps": [_translate_text(translator, s, target_lang, TRANSLATION_PIVOT_LANG)
                  for s in recipe["steps"]],
    }


def lookup_recipe_via_translation(phrase, lang, translator=None):
    """Fallback path, tried whenever native lookup_recipe() comes up
    empty for a RECIPE_LANGS language, and ALWAYS for any other
    language (see module docstring - this is the generalization of
    wiki-offline's Path A/Path B). Translates the phrase to en-us,
    looks it up against the 3,129-recipe English corpus (by far the
    largest), translates the matched recipe back. Returns a recipe
    dict or None - same silent-miss contract as lookup_recipe()."""
    if lang == TRANSLATION_PIVOT_LANG:
        return None  # nothing to translate to/from
    translator = translator or _get_translator()
    if translator is None:
        return None
    try:
        english_phrase = translator.translate(phrase, TRANSLATION_PIVOT_LANG, lang)
    except Exception:
        return None
    english_recipe = lookup_recipe(english_phrase, TRANSLATION_PIVOT_LANG)
    if english_recipe is None:
        return None
    try:
        return _translate_recipe(english_recipe, lang, translator)
    except Exception:
        return None


def get_recipe_answer(phrase, lang):
    """Full pipeline for one incoming phrase: native lookup first
    (fast, no translation latency, only possible for RECIPE_LANGS),
    then the English-pivot translation fallback (works for ANY
    language with a translator configured, including RECIPE_LANGS
    themselves when the native corpus misses). Returns the finished
    spoken string, or None."""
    lang = lang.lower()
    recipe = lookup_recipe(phrase, lang) if lang in RECIPE_LANGS else None
    used_translation = False
    if recipe is None:
        recipe = lookup_recipe_via_translation(phrase, lang)
        used_translation = True
    if recipe is None:
        return None
    translator = _get_translator() if used_translation else None
    return format_recipe_answer(recipe, lang, translator=translator)


class RecipeHelper(FallbackSkill):
    """Extends FallbackSkill (not plain OVOSSkill) - the
    @fallback_handler decorator only auto-registers on this base
    class, same reasoning as wiki-offline. Combines both entry
    points: Common Query competes fairly against other knowledge
    skills when the platform routes there; the fallback handler
    catches whatever the rest of the pipeline didn't answer."""

    def can_answer(self, message):
        """Pre-check for the fallback 'ping': True only when the sentence
        asks how to make a dish this skill has a recipe for (issue #5).

        It used to say yes whenever a translator was configured, for any
        sentence at all, so the fallback stage handed this skill "set
        intercom name to living room" and "can you see my Sony TV" - and
        they got no answer. The native lookup is an index lookup (plus a
        fuzzy match), fast enough for the ping. Translated lookups can
        block for ~40 s loading a model and stay with Common Query."""
        utterances = message.data.get("utterances") or []
        if not utterances:
            return False
        lang = message.data.get("lang", self.lang).lower()
        return lang in RECIPE_LANGS and lookup_recipe(utterances[0], lang) is not None

    @common_query()
    def handle_common_query(self, phrase, lang):
        lang = lang.lower()
        answer = get_recipe_answer(phrase, lang)
        if answer is None:
            return None
        # a recipe with exactly that title beats a general knowledge
        # answer ("what do I need for carbonara" went to wolfie at 0.8)
        return answer, (1.0 if is_exact_recipe(phrase, lang) else 0.8)

    @intent_handler("recipe.intent")
    def handle_recipe(self, message):
        """"Recipe for X", "how do I bake X": unambiguous, so this skill's own
        intent (issue #5: common query and the fallback come too late, and
        other skills answered first)."""
        lang = (message.data.get("lang") or self.lang).lower()
        dish = (message.data.get("dish") or "").strip()
        if not dish:
            return
        prefix = RECIPE_PREFIX.get(lang, RECIPE_PREFIX["en-us"])
        answer = get_recipe_answer(prefix + dish, lang)
        if answer is None:
            self.speak_dialog("no_recipe", {"dish": dish})
            return
        self.speak(answer)

    @fallback_handler(priority=85)
    def handle_fallback(self, message):
        """Priority 85 - same tier as wiki-offline: after
        specific-domain skills, before the generic catch-all."""
        utterances = message.data.get("utterances") or []
        if not utterances:
            return False
        lang = message.data.get("lang", self.lang).lower()
        answer = get_recipe_answer(utterances[0], lang)
        if answer is None:
            return False
        self.speak(answer)
        return True
