import copy
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List
from constants.app_configuration import settings
from core.handlers.mongo_handler import MongoDBService
from utils.logger import setup_logger

logger = setup_logger(__name__)


class JSONTranslator:
    """Handles JSON translation using dot-notation paths with wildcard support"""

    def __init__(self, rules: List[dict]):
        self.rules = rules

    def translate(self, data: Any) -> Any:
        """Apply all translation rules to the data"""
        if not self.rules or not isinstance(data, (dict, list)):
            return data
        return self._apply_rules(copy.deepcopy(data))

    def _apply_rules(self, node: Any) -> Any:
        """Apply all rules to the node"""
        for rule in self.rules:
            path = rule.get("path")
            replace = rule.get("replace")
            if not path:
                continue
            segments = path.split(".") if isinstance(path, str) else path
            self._apply_rule(node, segments, replace)
        return node

    def _apply_rule(self, node: Any, segments: List[str], replace: Any) -> None:
        """Recursively apply a single rule"""
        if not segments:
            return

        current = segments[0]
        remaining = segments[1:]

        if isinstance(node, list):
            self._apply_rule_to_list(node, current, remaining, segments, replace)
        elif isinstance(node, dict):
            self._apply_rule_to_dict(node, current, remaining, replace)

    def _apply_rule_to_list(
            self,
            node: list,
            current: str,
            remaining: List[str],
            segments: List[str],
            replace: Any
    ) -> None:
        """Apply rule to list nodes"""
        if current == "*":
            for item in node:
                self._apply_rule(item, remaining, replace)
        else:
            for item in node:
                self._apply_rule(item, segments, replace)

    def _apply_rule_to_dict(
            self,
            node: dict,
            current: str,
            remaining: List[str],
            replace: Any
    ) -> None:
        """Apply rule to dictionary nodes"""
        if current == "*":
            self._apply_wildcard_to_dict(node, remaining, replace)
        elif current in node:
            self._apply_specific_key(node, current, remaining, replace)

    def _apply_wildcard_to_dict(
            self,
            node: dict,
            remaining: List[str],
            replace: Any
    ) -> None:
        """Apply wildcard transformation to all keys in dict"""
        for key in node:
            if remaining:
                self._apply_rule(node[key], remaining, replace)
            else:
                node[key] = self._replace_value(node[key], replace)

    def _apply_specific_key(
            self,
            node: dict,
            key: str,
            remaining: List[str],
            replace: Any
    ) -> None:
        """Apply transformation to a specific key in dict"""
        if remaining:
            self._apply_rule(node[key], remaining, replace)
        else:
            node[key] = self._replace_value(node[key], replace)

    def _replace_value(self, original: Any, replace: Any) -> Any:
        """Replace original value with mapped or direct replacement"""
        if isinstance(replace, dict):
            return replace.get(str(original), replace.get("*", original))
        return replace


class TranslationService:
    """Singleton service for managing translations with caching"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_loaded: datetime = datetime.min
        self._initialized = True
        self._load_translations()

    def _should_refresh(self) -> bool:
        """Check if cache should be refreshed based on TTL"""
        age = datetime.now(UTC) - self._last_loaded
        should_refresh = age > timedelta(seconds=settings.cache_ttl_seconds)
        if should_refresh:
            logger.debug(f"Cache expired (age: {age.total_seconds()}s, TTL: {settings.cache_ttl_seconds}s)")
        return should_refresh

    def _load_translations(self) -> None:
        """Load translations from MongoDB into cache"""
        try:
            collection = MongoDBService.get_collection()
            languages = {}

            cursor = collection.find(
                {},
                {"languageId": 1, "translations": 1, "_id": 0}
            )

            for doc in cursor:
                lang_id = doc.get("languageId")
                if lang_id:
                    languages[lang_id] = doc.get("translations", {}) or {}

            self._cache = languages
            self._last_loaded = datetime.now(UTC)
            logger.info(f"Loaded {len(languages)} languages from MongoDB")

            if languages:
                logger.debug(f"Available languages: {list(languages.keys())}")

        except Exception as e:
            logger.exception(f"Failed to load translations from MongoDB: {e}")
            if not self._cache:
                self._cache = {}

    def get_translations(self, language: str) -> Dict[str, Any]:
        """Get translations for a specific language with auto-refresh"""
        if not self._cache or self._should_refresh():
            self._load_translations()

        translations = self._cache.get(language, {})
        if not translations:
            logger.warning(f"No translations found for language: {language}")
        else:
            logger.debug(f"Found {len(translations)} translation rules for: {language}")

        return translations

    def reload(self) -> Dict[str, Any]:
        """Manually reload translations from database"""
        logger.info("Manual translation reload triggered")
        self._load_translations()
        return {
            "status": "success",
            "languages_loaded": len(self._cache),
            "languages": list(self._cache.keys())
        }

    def get_available_languages(self) -> List[str]:
        """Get list of available languages"""
        if not self._cache or self._should_refresh():
            self._load_translations()
        return list(self._cache.keys())


# Singleton instance
translation_service = TranslationService()