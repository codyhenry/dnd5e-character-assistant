from .models import CharacterBuild
from .validators import validate_character_build

ABILITY_ORDER = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
SKILL_TO_ABILITY = {
    'Acrobatics': 'dexterity',
    'Animal Handling': 'wisdom',
    'Arcana': 'intelligence',
    'Athletics': 'strength',
    'Deception': 'charisma',
    'History': 'intelligence',
    'Insight': 'wisdom',
    'Intimidation': 'charisma',
    'Investigation': 'intelligence',
    'Medicine': 'wisdom',
    'Nature': 'intelligence',
    'Perception': 'wisdom',
    'Performance': 'charisma',
    'Persuasion': 'charisma',
    'Religion': 'intelligence',
    'Sleight of Hand': 'dexterity',
    'Stealth': 'dexterity',
    'Survival': 'wisdom',
}


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return 2 + max(0, (level - 1) // 4)


def build_character_sheet_context(build: CharacterBuild) -> dict:
    scores = {ability: int(build.ability_scores.get(ability, 10)) for ability in ABILITY_ORDER}
    modifiers = {ability: ability_modifier(score) for ability, score in scores.items()}
    prof = proficiency_bonus(build.character_level)

    saving_throws = {ability.title(): modifiers[ability] + prof for ability in ABILITY_ORDER}
    skills = {skill: modifiers[ability] + prof for skill, ability in SKILL_TO_ABILITY.items()}

    class_level = build.class_levels.first()
    spellcasting_ability = class_level.class_option.name if class_level else ''

    return {
        'ability_scores': scores,
        'ability_modifiers': modifiers,
        'proficiency_bonus': prof,
        'saving_throws': saving_throws,
        'skills': skills,
        'initiative': modifiers['dexterity'],
        'spellcasting_class': class_level.class_option.name if class_level else '',
        'spellcasting_ability': spellcasting_ability,
        'spell_save_dc': 8 + prof + (modifiers['intelligence'] if class_level else 0),
        'spell_attack_bonus': prof + (modifiers['intelligence'] if class_level else 0),
        'hp_max': build.manual_overrides.get('hp_max', 0),
        'armor_class': build.manual_overrides.get('armor_class', 10 + modifiers['dexterity']),
        'speed': build.manual_overrides.get('speed', 30),
    }


def validate_and_store_character_build(character_build: CharacterBuild, ruleset):
    result = validate_character_build(character_build, ruleset)
    character_build.validation_status = (
        CharacterBuild.ValidationStatus.VALID if result.is_valid else CharacterBuild.ValidationStatus.INVALID
    )
    character_build.validation_errors = result.errors
    character_build.save(update_fields=['validation_status', 'validation_errors', 'updated_at'])
    return result
