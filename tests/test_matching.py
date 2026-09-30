"""Issue #5: the fallback took other skills' sentences, while the skill's own
examples never reached it."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from conftest import module


def _msg(utterance, lang="en-us", **data):
    m = MagicMock()
    m.data = {"utterances": [utterance], "lang": lang, **data}
    return m


@pytest.mark.parametrize("utterance", [
    "set intercom name to living room",   # ovos-skill-intercom
    "can you see my Sony TV",             # ovos-skill-network-scanner
    "how do i make a phone call",
    "how do i make money",
    "what do i need for my passport",
])
def test_the_fallback_declines_what_is_not_a_recipe(skill, utterance):
    """It used to say yes to anything whenever a translator was configured."""
    assert skill.can_answer(_msg(utterance)) is False


@pytest.mark.parametrize("utterance,lang", [
    ("how do i make pancakes", "en-us"),
    ("what do i need for carbonara", "en-us"),
    ("recipe for bobotie", "en-us"),
    ("how do i make a cake", "en-us"),
    ("hvordan laver jeg pandekager", "da-dk"),
    ("wie mache ich pfannkuchen", "de-de"),
])
def test_the_fallback_takes_a_real_recipe(skill, utterance, lang):
    assert skill.can_answer(_msg(utterance, lang)) is True


def test_translated_languages_stay_with_common_query(skill):
    """A translated lookup can block ~40 s loading a model - never in the
    fallback's ping."""
    assert skill.can_answer(_msg("comment faire des crêpes", "fr-fr")) is False


@pytest.mark.parametrize("phrase,title", [
    ("pancakes", "Corn Pancakes"),           # the dish as a word in a title
    ("carbonara", "Carbonara Pasta"),
    ("a cake", "Cola Cake"),                 # article dropped
    ("bobotie", "Bobotie"),                  # exact
])
def test_dish_names_find_a_recipe(phrase, title):
    key = module.resolve_recipe_key(phrase, "en-us")
    assert module.RECIPES_BY_LANG["en-us"][key]["title"] == title


def test_danish_and_german_compounds():
    key = module.resolve_recipe_key("pandekager", "da-dk")
    assert module.RECIPES_BY_LANG["da-dk"][key]["title"] == "Kikærtepandekage"
    key = module.resolve_recipe_key("pfannkuchen", "de-de")
    assert module.RECIPES_BY_LANG["de-de"][key]["title"] == "Eierpfannkuchen"


def test_short_words_find_nothing():
    assert module.resolve_recipe_key("tea", "en-us") is None


def test_an_exact_recipe_wins_common_query(skill):
    answer, confidence = skill.handle_common_query("recipe for bobotie", "en-us")
    assert confidence == 1.0 and "Bobotie" in answer
    answer, confidence = skill.handle_common_query("what do i need for carbonara", "en-us")
    assert confidence == 0.8
    assert skill.handle_common_query("what is the capital of france", "en-us") is None


def test_recipe_intent_reads_the_recipe(skill):
    skill.handle_recipe(_msg("give me a recipe for bobotie", dish="bobotie"))
    assert "Bobotie" in skill.speak.call_args[0][0]


def test_recipe_intent_says_so_when_there_is_none(skill):
    skill.handle_recipe(_msg("give me a recipe for unicorn stew", dish="unicorn stew"))
    skill.speak_dialog.assert_called_once_with("no_recipe", {"dish": "unicorn stew"})


def test_every_recipe_language_ships_the_intent_and_dialog():
    root = Path(module.__file__).parent / "locale"
    for lang in module.RECIPE_LANGS:
        assert (root / lang / "recipe.intent").read_text().strip()
        assert "{dish}" in (root / lang / "no_recipe.dialog").read_text()
