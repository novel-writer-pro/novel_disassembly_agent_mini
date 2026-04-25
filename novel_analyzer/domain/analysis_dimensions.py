"""Supported analysis dimensions aligned to the reference design."""

from enum import StrEnum


class AnalysisDimension(StrEnum):
    """Enumerates the default analysis dimensions."""

    CHAPTER_SUMMARY = "chapter_summary"
    KEY_EVENTS = "key_events"
    CHARACTER_STATES = "character_states"
    CHARACTER_RELATIONS = "character_relations"
    WORLDBUILDING = "worldbuilding"
    SETTING_CHANGES = "setting_changes"
    CONFLICTS = "conflicts"
    FORESHADOWING = "foreshadowing"
    PAYOFFS = "payoffs"
    EMOTIONAL_CURVE = "emotional_curve"
    PACING = "pacing"
    THEMES = "themes"
    POWER_SYSTEM = "power_system"
    WRITING_PATTERNS = "writing_patterns"
    VOLATILITY_PATTERNS = "volatility_patterns"
