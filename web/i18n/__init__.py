# Copyright (C) 2025 Lumina AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
International language support for Lumina Video Studio Web UI
"""

import json
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

_locales: Dict[str, dict] = {}
_current_language: str = "en_US"


def load_locales() -> Dict[str, dict]:
    """Load all locale files from locales directory"""
    global _locales
    
    locales_dir = Path(__file__).parent / "locales"
    
    if not locales_dir.exists():
        logger.warning(f"Locales directory not found: {locales_dir}")
        return _locales
    
    for json_file in locales_dir.glob("*.json"):
        lang_code = json_file.stem
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                _locales[lang_code] = json.load(f)
            logger.debug(f"Loaded locale: {lang_code}")
        except Exception as e:
            logger.error(f"Failed to load locale {lang_code}: {e}")
    
    logger.info(f"Loaded {len(_locales)} locales: {list(_locales.keys())}")
    return _locales


def set_language(lang_code: str):
    """Set current language"""
    global _current_language
    if lang_code in _locales:
        _current_language = lang_code
        logger.debug(f"Language set to: {lang_code}")
    else:
        logger.warning(f"Language {lang_code} not found, keeping {_current_language}")


def get_language() -> str:
    """Get current language"""
    return _current_language


def tr(key: str, fallback: Optional[str] = None, **kwargs) -> str:
    """
    Translate a key to current language (English only)
    
    Args:
        key: Translation key (e.g., "app.title")
        fallback: Fallback text if key not found
        **kwargs: Format parameters for string interpolation
    
    Returns:
        Translated text
    """
    locale = _locales.get(_current_language, {})
    translations = locale.get("t", {})
    
    result = translations.get(key)
    
    if result is None:
        if fallback is not None:
            result = fallback
        elif "en_US" in _locales:
            result = _locales["en_US"].get("t", {}).get(key)
        
        if result is None:
            result = key
            logger.debug(f"Translation missing: {key}")
    
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to format translation '{key}': {e}")
    
    return result


def get_language_name(lang_code: Optional[str] = None) -> str:
    """Get display name of a language"""
    if lang_code is None:
        lang_code = _current_language
    locale = _locales.get(lang_code, {})
    return locale.get("language_name", lang_code)


def get_available_languages() -> Dict[str, str]:
    """Get all available languages with their display names"""
    return {
        code: locale.get("language_name", code)
        for code, locale in _locales.items()
    }


# Auto-load locales on import
load_locales()
_current_language = "en_US"
logger.info(f"Language initialized to: {_current_language}")
