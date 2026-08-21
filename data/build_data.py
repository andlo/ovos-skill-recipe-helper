"""
One-off, multi-language data pipeline for ovos-skill-recipe-helper.

Fetches recipes from each native language's own Wikibooks Cookbook-
equivalent, parses the per-language recipe infobox template plus
Ingredients/Steps sections into a common structured shape, and writes
data/recipes_<lang>.json.

Only the three native/bundled-data languages are covered here -
en-us, da-dk, de-de (see README.md "Multi-language" for why those
three specifically). Any other language falls back to on-demand
runtime translation at answer time - same Path A/Path B pattern as
ovos-skill-wiki-offline - and has no build step here at all.

Per-language DISCOVERY differs (see README.md "Multi-language"
table, verified live 2026-08-21):
- en-us, de-de: category traversal (Category:Recipes /
  Kategorie:Kochbuch/ Alle Rezepte)
- da-dk: NO category tree for recipes - allpages prefix scan under
  WikiKogebogen/ instead, since recipes are manually-indexed subpages

Per-language PARSING also differs (verified live, real wikitext
samples, not assumed):
- en-us: `{{recipesummary|...}}` infobox, `== Ingredients ==`
  bulleted, `== Procedure ==` NUMBERED (`#`) steps
- da-dk: `{{Infoboks opskrift|...}}` infobox, `== Ingredienser ==`
  bulleted, `== Fremgangsmåde ==` NUMBERED (`#`) steps
- de-de: `{{:Kochbuch/_Vorlage/_RezeptBox|...}}` infobox,
  `== Zutaten ==` bulleted, `== Zubereitung ==` BULLETED (`*`) steps
  - NOT numbered, confirmed against 3 separate sample pages

A page is only kept if its infobox template is actually found during
parsing - this doubles as the filter for "is this really a recipe
page" (vs. a meta/navigation page swept up by discovery) instead of
trying to hand-enumerate non-recipe page names, and a per-language
parse-coverage percentage (pages kept / pages discovered) is logged
at the end of each run so there's a real number, not an assumption.

`steps` is stored as a JSON list of strings throughout, deliberately
never flattened into one blob - see issue #2 (step-by-step
walkthrough is out of scope for v1, but this keeps it cheap to add
later without re-parsing).

Usage: python3 build_data.py <lang-code>
e.g.:  python3 build_data.py da-dk

Not shipped with the skill - run once per language, output committed
as static data/recipes_<lang>.json. Politely rate-limited (0.5s
between page fetches) with retry-on-429 backoff and incremental
checkpointing every 50 recipes, so an interruption doesn't lose
progress. Safe to re-run - resumes from whatever's already saved.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).resolve().parent
REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 5
CHECKPOINT_EVERY = 50


def make_headers():
    return {"User-Agent": "ovos-skill-recipe-helper data pipeline (contact: andlo@outlook.dk)"}


def log(progress_file, msg):
    print(msg, flush=True)
    with open(progress_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def api_get(domain, params, retries=0):
    try:
        r = requests.get(f"https://{domain}/w/api.php", params=params,
                          headers=make_headers(), timeout=30)
    except requests.RequestException:
        if retries < MAX_RETRIES:
            time.sleep(2 ** retries)
            return api_get(domain, params, retries + 1)
        raise
    if r.status_code == 429:
        wait = min(60, 2 ** (retries + 2))
        time.sleep(wait)
        if retries < MAX_RETRIES:
            return api_get(domain, params, retries + 1)
        r.raise_for_status()
    r.raise_for_status()
    return r.json()


def fetch_page_wikitext(domain, page_title):
    data = api_get(domain, {
        "action": "parse", "page": page_title,
        "prop": "wikitext", "format": "json",
    })
    if "error" in data:
        return None
    return data["parse"]["wikitext"]["*"]


def discover_by_category(domain, category_title, progress_file, recurse_subcats=True, max_depth=3):
    """Recursively walks a category tree collecting article (ns=0)
    titles - used for en-us (Category:Recipes has 15 subcategories,
    confirmed during research) and de-de (Kategorie:Kochbuch/ Alle
    Rezepte, flat but large enough to need pagination)."""
    seen_cats = set()
    titles = set()

    def walk(cat, depth):
        if cat in seen_cats or depth > max_depth:
            return
        seen_cats.add(cat)
        cmcontinue = None
        while True:
            params = {
                "action": "query", "list": "categorymembers",
                "cmtitle": cat, "cmlimit": 500, "format": "json",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            data = api_get(domain, params)
            for m in data["query"]["categorymembers"]:
                if m["ns"] == 14 and recurse_subcats:  # subcategory
                    walk(m["title"], depth + 1)
                elif m["ns"] == 0 or m["ns"] == 102:  # article / Cookbook: ns
                    titles.add(m["title"])
            if "continue" in data:
                cmcontinue = data["continue"]["cmcontinue"]
                time.sleep(0.2)
            else:
                break

    walk(category_title, 0)
    log(progress_file, f"  discover_by_category({category_title!r}): "
                        f"{len(titles)} candidate pages across {len(seen_cats)} categories")
    return sorted(titles)


def discover_by_prefix(domain, prefix, progress_file):
    """Lists all subpages under a prefix - used for da-dk, which has
    no Category:Recipes-equivalent tree at all (confirmed during
    research). This will include some non-recipe meta/navigation
    subpages (e.g. WikiKogebogen/Opsætning) - those get filtered out
    downstream by the infobox-template check in parse_da_recipe(),
    not here, since hand-enumerating meta page names is fragile."""
    titles = []
    apcontinue = None
    while True:
        params = {
            "action": "query", "list": "allpages",
            "apprefix": prefix, "apnamespace": 0,
            "aplimit": 500, "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = api_get(domain, params)
        titles.extend(m["title"] for m in data["query"]["allpages"])
        cont = data.get("continue", {}).get("apcontinue")
        if not cont:
            break
        apcontinue = cont
        time.sleep(0.2)
    log(progress_file, f"  discover_by_prefix({prefix!r}): {len(titles)} candidate pages")
    return titles


# --- Per-language parsers ---
# Each returns a dict (see RECIPE_SHAPE below) or None if the page
# doesn't actually contain this language's recipe infobox template -
# that None IS the quality filter, see module docstring.

RECIPE_SHAPE = {
    "title": None, "category": None, "servings": None, "time": None,
    "difficulty": None, "ingredients": [], "steps": [],
}

INFOBOX_RE = re.compile(r"\{\{[^|{}]*[Rr]ecipesummary\s*(.*?)\n\}\}", re.DOTALL)
# NOTE: [ \t] not \s around the '=' and at the end - \s also matches
# \n, which let an EMPTY field's value silently swallow the next
# line's content into this field's capture group (found by testing
# against real da-dk/de-de pages with blank infobox fields, e.g.
# "| billede      = \n| kategori = X" - "billede" was capturing
# "| kategori = X" before this fix, confirmed via direct regex test).
#
# NOTE: field-name pattern is [^\s=|]+ , NOT [A-Za-z]+ - da-dk's own
# "sværhedsgrad" (difficulty) field name contains "æ", which
# [A-Za-z]+ silently fails to match at all (not a partial match, a
# TOTAL miss for that field - found by testing against a real page
# where "sværhedsgrad = 3" never showed up in parsed output at all).
# [^\s=|]+ is deliberately generic rather than enumerating known
# accented letters (æ/ø/å, ß, ñ, ...) - covers whatever future
# languages' field names contain without more per-language patching.
FIELD_RE = re.compile(r"^[ \t]*\|[ \t]*([^\s=|]+)[ \t]*=[ \t]*([^\n]*?)[ \t]*$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
BULLET_RE = re.compile(r"^\*\s*(.+)$", re.MULTILINE)
NUMBERED_RE = re.compile(r"^#\s*(.+)$", re.MULTILINE)
COLON_RE = re.compile(r"^:\s*(.+)$", re.MULTILINE)
WIKILINK_STRIP_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")


def _clean_wikitext_line(text):
    """Strips [[wikilinks]] down to display text and collapses
    leftover whitespace - shared by every language's ingredient/step
    line cleanup."""
    text = WIKILINK_STRIP_RE.sub(r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)  # strip stray templates
    return " ".join(text.split())


def _extract_fields(infobox_body):
    """Splits MediaWiki template parameters on top-level '|', not
    just newline-separated '| key = value' lines - recipesummary
    turns out to ALSO appear as a single-line, pipe-separated
    one-liner on some pages (confirmed live: Cookbook:Kachumbari is
    '{{recipesummary|category=Salad recipes|servings=4|...}}' all on
    one line - the earlier newline-anchored version silently matched
    ZERO fields on this shape, not a partial match, a total miss).

    [[wikilink|display text]] pipes are protected first so they
    aren't mistaken for parameter separators - image fields commonly
    contain one, e.g. de-de's '[[Image:Foo.jpg|300px]]', confirmed on
    live Kochbuch/ Aioli.

    Also strips HTML comments used as inline usage instructions
    (de-de's template ships one per field, e.g. 'Kochbuch/ Saucen
    <!-- Name einer existierenden Kategorie -->', confirmed live) and
    normalizes empty values to None."""
    protected = []

    def _protect(m):
        protected.append(m.group(0))
        return f"\x00{len(protected) - 1}\x00"

    safe_body = re.sub(r"\[\[[^\]]*\]\]", _protect, infobox_body)

    fields = {}
    for part in safe_body.split("|"):
        part = part.replace("\n", " ")
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().lower()
        if not key or " " in key:
            continue
        value = HTML_COMMENT_RE.sub("", value).strip()
        for i, original in enumerate(protected):
            value = value.replace(f"\x00{i}\x00", original)
        fields[key] = value if value else None
    return fields


def _extract_list_items(body):
    """Tries `#` numbered, then `*` bulleted, then `:` colon-indented
    (a MediaWiki definition-list idiom some da-dk pages use for
    steps instead of a real list - confirmed live on
    WikiKogebogen/A Touch of Class) - first non-empty match wins.
    Found by testing against a real 10-page da-dk sample where a
    numbered-only extraction produced only ~1/10 successful parses;
    most of the "failures" turned out to be real recipes using `:`
    or `*` instead of `#`, not actually bad pages. Shared by
    ingredients (usually `*`, but tolerant here too) and steps."""
    for pattern in (NUMBERED_RE, BULLET_RE, COLON_RE):
        items = pattern.findall(body)
        if items:
            return items
    return []


def _extract_section(wikitext, heading_names):
    """Returns the wikitext body between one of the given `==Heading==`
    names and the next `==...==` heading, or None if not found. Tries
    each heading name in order (some languages/pages vary slightly)."""
    for heading in heading_names:
        m = re.search(rf"==\s*{re.escape(heading)}\s*==\n(.*?)(?=\n==|\Z)",
                       wikitext, re.DOTALL)
        if m:
            return m.group(1)
    return None


def parse_en_recipe(title, wikitext):
    """en-us: {{recipesummary|...}}, ==Ingredients== bulleted,
    ==Procedure== NUMBERED. Verified against Cookbook:Bobotie
    (multi-line infobox) and Cookbook:Kachumbari (single-line
    infobox - same template, different formatting) live wikitext,
    2026-08-21.

    The infobox is METADATA ONLY, not the quality gate - confirmed
    some real recipe pages (e.g. de-de's Kochbuch/ Schokokuchen) have
    NO infobox at all, just the Ingredients/Procedure sections
    directly. Requiring the infobox would have silently dropped those
    as false negatives. The real gate is: both sections present and
    non-empty."""
    m = re.search(r"\{\{\s*recipesummary\b(.*?)\}\}", wikitext,
                  re.DOTALL | re.IGNORECASE)
    fields = _extract_fields(m.group(1)) if m else {}

    ing_body = _extract_section(wikitext, ["Ingredients"])
    steps_body = _extract_section(wikitext, ["Procedure"])
    if ing_body is None or steps_body is None:
        return None

    ingredients = [_clean_wikitext_line(l) for l in _extract_list_items(ing_body)]
    steps = [_clean_wikitext_line(l) for l in _extract_list_items(steps_body)]
    if not ingredients or not steps:
        return None

    return {
        "title": title.split(":", 1)[-1],
        "category": fields.get("category"),
        "servings": fields.get("servings"),
        "time": fields.get("time"),
        "difficulty": fields.get("difficulty"),
        "ingredients": ingredients,
        "steps": steps,
    }


def parse_da_recipe(title, wikitext):
    """da-dk: {{Infoboks opskrift|...}}, ==Ingredienser== bulleted,
    ==Fremgangsmåde== NUMBERED/bulleted/colon-indented (see
    _extract_list_items). Verified against
    WikiKogebogen/Teriyaki Kylling live wikitext, 2026-08-21.

    Infobox is metadata only, not the quality gate - see
    parse_en_recipe()'s docstring for why (same reasoning applies).

    KNOWN GAP, NOT HANDLED: {{WikiKogebogen/Mangor|...}} is a THIRD
    infobox family (~20% of a 60-page live sample, 2026-08-21) used
    for historical recipes apparently sourced from an old physical
    cookbook ("Mangor's Kogebog" per earlier research). These have NO
    ingredients/steps STRUCTURE at all - just free-flowing prose
    describing the dish, no bullets, no numbers, no colon-indents.
    Forcing that into ingredients/steps would mean inventing
    structure the source doesn't have. Deliberately returns None for
    these (same as a genuine non-recipe page) rather than a fragile
    prose-splitting heuristic - see README.md/issue tracker for
    whether/how to handle this class of page (e.g. a separate
    'read the description aloud' answer shape, distinct from the
    ingredients+steps shape everything else uses)."""
    m = re.search(r"\{\{\s*Infoboks opskrift\b(.*?)\}\}", wikitext,
                  re.DOTALL | re.IGNORECASE)
    fields = _extract_fields(m.group(1)) if m else {}

    ing_body = _extract_section(wikitext, ["Ingredienser"])
    steps_body = _extract_section(wikitext, ["Fremgangsmåde"])
    if ing_body is None or steps_body is None:
        return None

    ingredients = [_clean_wikitext_line(l) for l in _extract_list_items(ing_body)]
    steps = [_clean_wikitext_line(l) for l in _extract_list_items(steps_body)]
    if not ingredients or not steps:
        return None

    return {
        "title": title.split("/", 1)[-1],
        "category": fields.get("kategori"),
        "servings": fields.get("portioner"),
        "time": fields.get("tid"),
        "difficulty": fields.get("sværhedsgrad"),
        "ingredients": ingredients,
        "steps": steps,
    }


def parse_de_recipe(title, wikitext):
    """de-de: {{:Kochbuch/_Vorlage/_RezeptBox|...}}, ==Zutaten==
    bulleted, ==Zubereitung== ALSO BULLETED (not numbered - confirmed
    against Aioli/Maispuffer/Schokokuchen, 2026-08-21). Steps are
    still split into a list, one bullet per step - order preserved
    from source order, just via `*` not `#`.

    Infobox is OFTEN ABSENT here (confirmed live: Kochbuch/
    Schokokuchen has none at all, just the sections directly) -
    metadata only, not the quality gate. See parse_en_recipe()'s
    docstring for the general reasoning."""
    m = re.search(r"\{\{:Kochbuch/_Vorlage/_RezeptBox\b(.*?)\}\}",
                  wikitext, re.DOTALL | re.IGNORECASE)
    fields = _extract_fields(m.group(1)) if m else {}

    ing_body = _extract_section(wikitext, ["Zutaten"])
    steps_body = _extract_section(wikitext, ["Zubereitung"])
    if ing_body is None or steps_body is None:
        return None

    ingredients = [_clean_wikitext_line(l) for l in _extract_list_items(ing_body)]
    steps = [_clean_wikitext_line(l) for l in _extract_list_items(steps_body)]
    if not ingredients or not steps:
        return None

    return {
        "title": title.split("/", 1)[-1].strip(),
        "category": fields.get("kategorie"),
        "servings": fields.get("portionen"),
        "time": fields.get("zubereitungszeit"),
        "difficulty": fields.get("schwierigkeitsgrad"),
        "ingredients": ingredients,
        "steps": steps,
    }


PARSERS = {
    "en-us": parse_en_recipe,
    "da-dk": parse_da_recipe,
    "de-de": parse_de_recipe,
}


LANG_CONFIGS = {
    "en-us": {
        "domain": "en.wikibooks.org",
        "discovery": "category",
        "category": "Category:Recipes",
    },
    "da-dk": {
        "domain": "da.wikibooks.org",
        "discovery": "prefix",
        "prefix": "WikiKogebogen/",
    },
    "de-de": {
        "domain": "de.wikibooks.org",
        "discovery": "category",
        "category": "Kategorie:Kochbuch/ Alle Rezepte",
    },
}


def discover_titles(lang, progress_file):
    config = LANG_CONFIGS[lang]
    if config["discovery"] == "category":
        return discover_by_category(config["domain"], config["category"], progress_file)
    elif config["discovery"] == "prefix":
        return discover_by_prefix(config["domain"], config["prefix"], progress_file)
    raise ValueError(f"Unknown discovery strategy for {lang}")


def build_recipes(lang, progress_file, recipes_file, candidates_file):
    domain = LANG_CONFIGS[lang]["domain"]
    parser = PARSERS[lang]

    if candidates_file.exists():
        with open(candidates_file, encoding="utf-8") as f:
            candidates = json.load(f)
        log(progress_file, f"[{lang}] Resuming candidate list: {len(candidates)} pages")
    else:
        log(progress_file, f"[{lang}] Discovering candidate pages...")
        candidates = discover_titles(lang, progress_file)
        with open(candidates_file, "w", encoding="utf-8") as f:
            json.dump(candidates, f, ensure_ascii=False, indent=2)

    recipes = {}
    if recipes_file.exists():
        with open(recipes_file, encoding="utf-8") as f:
            recipes = json.load(f)
        log(progress_file, f"[{lang}] Resuming: {len(recipes)} recipes already parsed")

    already_tried = set(recipes.keys())
    remaining = [t for t in candidates if t not in already_tried]
    log(progress_file, f"[{lang}] {len(remaining)} pages left to fetch (of {len(candidates)} candidates)")

    skipped = 0
    for i, title in enumerate(remaining):
        if i % 50 == 0:
            log(progress_file, f"  [{lang}] ...fetching #{i} ({title!r})")
        wikitext = fetch_page_wikitext(domain, title)
        if wikitext is not None:
            parsed = parser(title, wikitext)
        else:
            parsed = None
        if parsed:
            recipes[title] = parsed
        else:
            skipped += 1
        time.sleep(REQUEST_DELAY_SECONDS)

        if (i + 1) % CHECKPOINT_EVERY == 0:
            with open(recipes_file, "w", encoding="utf-8") as f:
                json.dump(recipes, f, ensure_ascii=False, indent=2)
            log(progress_file, f"  [{lang}] progress: {i + 1}/{len(remaining)} this run, "
                                f"{len(recipes)} recipes saved, {skipped} skipped (no matching infobox)")

    with open(recipes_file, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

    total_tried = len(recipes) + skipped
    coverage = (len(recipes) / total_tried * 100) if total_tried else 0.0
    log(progress_file, f"[{lang}] DONE. {len(recipes)} recipes saved to {recipes_file} "
                        f"({coverage:.1f}% parse coverage of {total_tried} pages tried this run)")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in LANG_CONFIGS:
        print(f"Usage: python3 build_data.py <lang-code>")
        print(f"Available: {list(LANG_CONFIGS.keys())}")
        sys.exit(1)

    lang = sys.argv[1]
    progress_file = OUTPUT_DIR / f"progress_{lang}.log"
    recipes_file = OUTPUT_DIR / f"recipes_{lang}.json"
    candidates_file = OUTPUT_DIR / f"candidates_{lang}.json"

    build_recipes(lang, progress_file, recipes_file, candidates_file)
