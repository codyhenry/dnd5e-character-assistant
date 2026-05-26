from dataclasses import dataclass, field

from dnd_options.models import DNDOption


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def _collect_selected_option_ids(character_build):
    option_ids = {
        opt_id
        for opt_id in [
            character_build.species_option_id,
            character_build.background_option_id,
        ]
        if opt_id
    }

    class_level_qs = character_build.class_levels.all()
    option_ids.update(class_level_qs.values_list('class_option_id', flat=True))
    option_ids.update(class_level_qs.exclude(subclass_option_id__isnull=True).values_list('subclass_option_id', flat=True))

    for relation in [
        character_build.selected_feats,
        character_build.selected_spells,
        character_build.selected_equipment,
        character_build.selected_features,
        character_build.attacks_actions,
    ]:
        option_ids.update(relation.values_list('id', flat=True))

    return option_ids


def validate_character_build(character_build, ruleset) -> ValidationResult:
    if character_build.build_type == character_build.BuildType.NPC:
        return ValidationResult(is_valid=True, errors=[])

    errors = []

    if character_build.character_level != ruleset.required_character_level:
        errors.append('Character level must match the ruleset required level.')

    if ruleset.banned_options.filter(banned_character_build=character_build).exists():
        errors.append('This character build is banned in the selected ruleset.')

    option_ids = _collect_selected_option_ids(character_build)

    banned_option_ids = set(
        ruleset.banned_options.exclude(banned_option_id__isnull=True).values_list('banned_option_id', flat=True)
    )
    if option_ids.intersection(banned_option_ids):
        errors.append('Character build includes one or more banned options.')

    if option_ids and ruleset.allowed_source_categories:
        disallowed_options = DNDOption.objects.filter(id__in=option_ids).exclude(
            source_category__in=ruleset.allowed_source_categories
        )
        if disallowed_options.exists():
            errors.append('Character build includes options from disallowed source categories.')

    if not ruleset.allow_multiclassing and character_build.class_levels.count() > 1:
        errors.append('Multiclassing is not allowed by this ruleset.')

    if not ruleset.allow_feats and character_build.selected_feats.exists():
        errors.append('Feats are not allowed by this ruleset.')

    return ValidationResult(is_valid=not errors, errors=errors)
