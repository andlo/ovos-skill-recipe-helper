"""Shared fixtures for the recipe-helper test suite."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("recipehelper_skill", _INIT_PATH)
module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = module
_spec.loader.exec_module(module)

RecipeHelper = module.RecipeHelper


@pytest.fixture
def skill(monkeypatch):
    s = RecipeHelper.__new__(RecipeHelper)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-recipe-helper.test"
    s._bus = MagicMock()
    monkeypatch.setattr(RecipeHelper, "lang", "en-us", raising=False)
    s.speak = MagicMock()
    s.speak_dialog = MagicMock()
    # never load a translation model in tests
    monkeypatch.setattr(module, "_translator_configured", lambda: True)
    monkeypatch.setattr(module, "lookup_recipe_via_translation", lambda *a, **k: None)
    return s
