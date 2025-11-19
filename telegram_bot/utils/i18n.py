# telegram_bot/utils/i18n.py

import json
import os
import logging
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

_translations = {}
SUPPORTED_LANGUAGES = ['en', 'km']
DEFAULT_LANGUAGE = 'en'


def load_translations():
    """Loads translation files into memory."""
    if _translations:
        return

    base_dir = os.path.dirname(os.path.dirname(__file__))
    locales_dir = os.path.join(base_dir, 'locales')

    for lang in SUPPORTED_LANGUAGES:
        file_path = os.path.join(locales_dir, f'{lang}.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)
            log.info(f"Loaded locale: {lang}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.error(f"Failed to load locale '{lang}': {e}")

    if DEFAULT_LANGUAGE not in _translations:
        raise RuntimeError(f"Default language '{DEFAULT_LANGUAGE}' could not be loaded.")


def t(key: str, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> str:
    """
    Translates a dot-separated key into the user's preferred language.

    Dynamic Fallback:
    If a key starting with 'categories.' is missing (e.g. custom categories),
    it returns the category name itself instead of the key path.
    """
    if not _translations:
        load_translations()

    # Determine language
    lang = DEFAULT_LANGUAGE
    if context.user_data and 'profile' in context.user_data:
        lang = context.user_data['profile'].get('settings', {}).get('language', DEFAULT_LANGUAGE)

    if lang not in _translations:
        lang = DEFAULT_LANGUAGE

    # Lookup key
    try:
        value = _translations[lang]
        for k in key.split('.'):
            value = value[k]

        if isinstance(value, str):
            return value.format(**kwargs)
        return key

    except (KeyError, TypeError):
        # --- HYBRID LOGIC START ---
        # If it's a category key (e.g., "categories.Sewing Fee"), fallback to the name itself.
        if key.startswith("categories."):
            try:
                # Return the part after the first dot ("Sewing Fee")
                return key.split(".", 1)[1]
            except IndexError:
                return key
        # --- HYBRID LOGIC END ---

        # Only log warnings for system keys, not user content
        log.warning(f"Translation missing for system key '{key}' in lang '{lang}'")
        return key
    except Exception as e:
        log.error(f"Translation error for '{key}': {e}")
        return key