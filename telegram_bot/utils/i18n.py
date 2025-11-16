# --- Start of new file: telegram_bot/utils/i18n.py ---
import json
import os
from telegram.ext import ContextTypes

# In-memory cache for translations
translations = {}
SUPPORTED_LANGUAGES = ['en', 'km']
DEFAULT_LANGUAGE = 'en'


def load_translations():
    """
    Loads all translation files from the 'locales' directory into memory.
    """
    global translations
    if translations:
        return  # Already loaded

    locales_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'locales'
    )
    print(f"Loading translations from: {locales_dir}")

    for lang in SUPPORTED_LANGUAGES:
        file_path = os.path.join(locales_dir, f'{lang}.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
                print(f"Successfully loaded '{lang}' locale.")
        except FileNotFoundError:
            print(f"Warning: Translation file not found for '{lang}'")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON for '{lang}'")

    if DEFAULT_LANGUAGE not in translations:
        raise RuntimeError(
            f"Default language '{DEFAULT_LANGUAGE}' file is missing or invalid."
        )


def t(key: str, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> str:
    """
    Translates a given key into the user's preferred language.
    Args:
        key: The dot-separated key (e.g., "common.welcome").
        context: The bot's context, used to find the user's profile.
        **kwargs: Variables to format into the string.
    Returns:
        The translated and formatted string.
    """
    if not translations:
        load_translations()

    # 1. Get user's language from cached profile
    lang = DEFAULT_LANGUAGE

    # --- THIS IS THE FIX ---
    # The decorator caches at 'profile', not 'user_profile'
    if context.user_data and 'profile' in context.user_data:
        lang = (
            context.user_data['profile']
            .get('settings', {})
            .get('language', DEFAULT_LANGUAGE)
        )
    # --- END FIX ---

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    # 2. Navigate the dot-separated key
    try:
        keys = key.split('.')
        temp_translation = translations.get(lang, translations[DEFAULT_LANGUAGE])
        for k in keys:
            temp_translation = temp_translation[k]

        # 3. Format the string
        return temp_translation.format(**kwargs)

    except (KeyError, TypeError):
        # Fallback: return the key itself
        print(f"Translation key not found: '{key}' for lang '{lang}'")
        return key
    except Exception as e:
        print(f"Error during translation of key '{key}': {e}")
        return key

# --- End of new file ---