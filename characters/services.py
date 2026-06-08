from dataclasses import dataclass, field

from django.db.models import Q
from django.utils import timezone

from .models import CharacterBuild, CharacterSelectedOption
from .validators import validate_character_build

ABILITY_ORDER = ['strength', 'dexterity',
                 'constitution', 'intelligence', 'wisdom', 'charisma']
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
    scores = {ability: int(build.ability_scores.get(ability, 10))
              for ability in ABILITY_ORDER}
    modifiers = {ability: ability_modifier(
        score) for ability, score in scores.items()}
    prof = proficiency_bonus(build.character_level)

    saving_throws = {
        ability.title(): modifiers[ability] + prof for ability in ABILITY_ORDER}
    skills = {skill: modifiers[ability] + prof for skill,
              ability in SKILL_TO_ABILITY.items()}

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
    character_build.needs_revalidation = not result.is_valid
    character_build.revalidation_reason = '' if result.is_valid else 'This build failed validation against current campaign rules.'
    character_build.last_validated_at = timezone.now()
    character_build.save(update_fields=[
        'validation_status',
        'validation_errors',
        'needs_revalidation',
        'revalidation_reason',
        'last_validated_at',
        'updated_at',
    ])
    return result


@dataclass
class ReuseValidationResult:
    is_valid: bool
    errors: list[dict] = field(default_factory=list)


def sync_selected_options_for_build(character_build: CharacterBuild) -> None:
    CharacterSelectedOption.objects.filter(
        character_build=character_build).delete()

    selected_rows: list[CharacterSelectedOption] = []

    if character_build.species_option_id:
        selected_rows.append(
            CharacterSelectedOption(
                character_build=character_build,
                dnd_option_id=character_build.species_option_id,
                option_type=CharacterSelectedOption.OptionType.SPECIES,
            )
        )

    if character_build.background_option_id:
        selected_rows.append(
            CharacterSelectedOption(
                character_build=character_build,
                dnd_option_id=character_build.background_option_id,
                option_type=CharacterSelectedOption.OptionType.BACKGROUND,
            )
        )

    selected_rows.extend(
        CharacterSelectedOption(
            character_build=character_build,
            dnd_option_id=option_id,
            option_type=CharacterSelectedOption.OptionType.FEAT,
        )
        for option_id in character_build.selected_feats.values_list('id', flat=True)
    )

    selected_rows.extend(
        CharacterSelectedOption(
            character_build=character_build,
            dnd_option_id=option_id,
            option_type=CharacterSelectedOption.OptionType.SPELL,
        )
        for option_id in character_build.selected_spells.values_list('id', flat=True)
    )

    selected_rows.extend(
        CharacterSelectedOption(
            character_build=character_build,
            dnd_option_id=option_id,
            option_type=CharacterSelectedOption.OptionType.EQUIPMENT,
        )
        for option_id in character_build.selected_equipment.values_list('id', flat=True)
    )

    selected_rows.extend(
        CharacterSelectedOption(
            character_build=character_build,
            dnd_option_id=option_id,
            option_type=CharacterSelectedOption.OptionType.FEATURE,
        )
        for option_id in character_build.selected_features.values_list('id', flat=True)
    )

    selected_rows.extend(
        CharacterSelectedOption(
            character_build=character_build,
            dnd_option_id=option_id,
            option_type=CharacterSelectedOption.OptionType.ATTACK,
        )
        for option_id in character_build.attacks_actions.values_list('id', flat=True)
    )

    if selected_rows:
        CharacterSelectedOption.objects.bulk_create(selected_rows)


def mark_builds_stale_for_dnd_option(dnd_option, reason: str) -> int:
    build_ids = CharacterBuild.objects.filter(
        Q(species_option=dnd_option)
        | Q(background_option=dnd_option)
        | Q(selected_feats=dnd_option)
        | Q(selected_spells=dnd_option)
        | Q(selected_equipment=dnd_option)
        | Q(selected_features=dnd_option)
        | Q(attacks_actions=dnd_option)
        | Q(class_levels__class_option=dnd_option)
        | Q(class_levels__subclass_option=dnd_option)
        | Q(selected_options__dnd_option=dnd_option)
    ).values_list('id', flat=True).distinct()

    return CharacterBuild.objects.filter(id__in=build_ids).update(
        needs_revalidation=True,
        validation_status=CharacterBuild.ValidationStatus.STALE,
        revalidation_reason=reason,
    )


def mark_builds_stale_for_ruleset(ruleset, reason: str) -> int:
    return CharacterBuild.objects.filter(campaign=ruleset.campaign).update(
        needs_revalidation=True,
        validation_status=CharacterBuild.ValidationStatus.STALE,
        revalidation_reason=reason,
    )


def revalidate_character_build(character_build: CharacterBuild):
    ruleset = character_build.campaign.active_ruleset
    if ruleset is None:
        errors = [{
            'code': 'missing_ruleset',
            'message': 'Campaign has no active ruleset to validate against.',
        }]
        character_build.needs_revalidation = True
        character_build.validation_status = CharacterBuild.ValidationStatus.INVALID
        character_build.validation_errors = errors
        character_build.revalidation_reason = 'No active campaign ruleset is configured.'
        character_build.last_validated_at = timezone.now()
        character_build.save(update_fields=[
            'needs_revalidation',
            'validation_status',
            'validation_errors',
            'revalidation_reason',
            'last_validated_at',
            'updated_at',
        ])
        return ReuseValidationResult(is_valid=False, errors=errors)

    result = validate_character_build(character_build, ruleset)
    now = timezone.now()
    if result.is_valid:
        character_build.needs_revalidation = False
        character_build.validation_status = CharacterBuild.ValidationStatus.VALID
        character_build.validation_errors = []
        character_build.revalidation_reason = ''
        character_build.last_validated_at = now
        character_build.save(update_fields=[
            'needs_revalidation',
            'validation_status',
            'validation_errors',
            'revalidation_reason',
            'last_validated_at',
            'updated_at',
        ])
        return ReuseValidationResult(is_valid=True, errors=[])

    character_build.needs_revalidation = True
    character_build.validation_status = CharacterBuild.ValidationStatus.INVALID
    character_build.validation_errors = result.errors
    character_build.revalidation_reason = 'One or more validation checks failed against current options and ruleset.'
    character_build.last_validated_at = now
    character_build.save(update_fields=[
        'needs_revalidation',
        'validation_status',
        'validation_errors',
        'revalidation_reason',
        'last_validated_at',
        'updated_at',
    ])
    return ReuseValidationResult(is_valid=False, errors=result.errors)


def require_valid_build_for_reuse(character_build: CharacterBuild):
    if character_build.needs_revalidation or character_build.validation_status in {
        CharacterBuild.ValidationStatus.STALE,
        CharacterBuild.ValidationStatus.UNKNOWN,
    }:
        return ReuseValidationResult(
            is_valid=False,
            errors=[
                {
                    'code': 'revalidation_required',
                    'message': 'This build must be explicitly revalidated before it can be reused.',
                }
            ],
        )

    if character_build.validation_status == CharacterBuild.ValidationStatus.INVALID:
        return ReuseValidationResult(is_valid=False, errors=character_build.validation_errors)

    return ReuseValidationResult(is_valid=True, errors=[])
