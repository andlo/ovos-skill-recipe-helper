# Recipe Helper

An offline cookbook for [OpenVoiceOS](https://openvoiceos.org). Ask for a recipe and OVOS reads you the ingredients and the steps. The skill never goes online for this: the recipes ship with it, taken from the [Wikibooks Cookbook](https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents).

That makes it handy in the kitchen of a device with no internet at all.

## Examples

- "Give me a recipe for pancakes"
- "How do I cook risotto?"
- "Opskrift på banankage"
- "Gib mir ein Rezept für Apfelkuchen"

## Recipes included

| Language | Recipes | Source |
|---|---|---|
| English (en-us) | about 3,100 | en.wikibooks.org Cookbook |
| German (de-de) | about 340 | de.wikibooks.org Kochbuch |
| Danish (da-dk) | about 150 | da.wikibooks.org WikiKogebogen |

Other languages (es, fr, it, nl, pt) work if a translate plugin is configured, for example `ovos-translate-plugin-nllb`, which runs locally. The skill translates the question to English, finds the recipe there and translates the answer back. Only the recipe you asked for is translated.

## Install

```bash
pip install ovos-skill-recipe-helper
```

## How it answers

- **"recipe for X"** sentences go to the skill's own intent.
- Other recipe questions are answered through Common Query and a low-priority fallback.
- Both only answer when a real recipe matches, so other sentences pass through untouched.

## Credits

The recipes are from Wikibooks, licensed CC BY-SA 4.0. See [CREDITS.md](CREDITS.md).

Design notes, data-pipeline details and the reasoning behind the choices are in [DEVELOPMENT.md](DEVELOPMENT.md). To rebuild the data, run `data/build_data.py`.

## Planned

- Search by ingredient (#1)
- A step-by-step walkthrough ("next step") (#2)
- An MCP extra (#3)
