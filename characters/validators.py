from dataclasses import dataclass, field

from dnd_options.models import DNDOption


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[dict] = field(default_factory=list)


def _error(code: str, message: str, details: dict | None = None) -> dict:
    payload: dict[str, object] = {'code': code, 'message': message}
    if details:
        payload['details'] = details
    return payload


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
    option_ids.update(class_level_qs.exclude(
        subclass_option_id__isnull=True).values_list('subclass_option_id', flat=True))

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

    errors: list[dict] = []

    if character_build.character_level != ruleset.required_character_level:
        errors.append(_error(
            'character_level_mismatch',
            'Character level must match the ruleset required level.',
            {
                'character_level': character_build.character_level,
                'required_level': ruleset.required_character_level,
            },
        ))

    if ruleset.banned_options.filter(banned_character_build=character_build).exists():
        errors.append(_error(
            'build_explicitly_banned',
            'This character build is banned in the selected ruleset.',
        ))

    option_ids = _collect_selected_option_ids(character_build)

    banned_option_ids = set(
        ruleset.banned_options.exclude(banned_option_id__isnull=True).values_list(
            'banned_option_id', flat=True)
    )
    if option_ids.intersection(banned_option_ids):
        errors.append(_error(
            'contains_banned_option',
            'Character build includes one or more banned options.',
            {'banned_option_ids': sorted(
                option_ids.intersection(banned_option_ids))},
        ))

    if option_ids and ruleset.allowed_source_categories:
        disallowed_options = DNDOption.objects.filter(id__in=option_ids).exclude(
            source_category__in=ruleset.allowed_source_categories
        )
        if disallowed_options.exists():
            errors.append(_error(
                'disallowed_source_category',
                'Character build includes options from disallowed source categories.',
                {
                    'option_ids': list(disallowed_options.values_list('id', flat=True)),
                    'allowed_source_categories': list(ruleset.allowed_source_categories),
                },
            ))

    if not ruleset.allow_multiclassing and character_build.class_levels.count() > 1:
        errors.append(_error(
            'multiclassing_not_allowed',
            'Multiclassing is not allowed by this ruleset.',
        ))

    if not ruleset.allow_feats and character_build.selected_feats.exists():
        errors.append(_error(
            'feats_not_allowed',
            'Feats are not allowed by this ruleset.',
        ))

    missing_option_ids = sorted(option_ids.difference(
        set(DNDOption.objects.filter(id__in=option_ids).values_list('id', flat=True))))
    if missing_option_ids:
        errors.append(_error(
            'missing_options',
            'One or more selected options no longer exist.',
            {'missing_option_ids': missing_option_ids},
        ))

    for dnd_option in DNDOption.objects.filter(id__in=option_ids):
        prerequisites = dnd_option.prerequisites or {}
        min_level = prerequisites.get(
            'min_level', prerequisites.get('minimum_level'))
        if isinstance(min_level, int) and character_build.character_level < min_level:
            errors.append(_error(
                'prerequisite_min_level',
                f'Selection "{dnd_option.name}" requires minimum level {min_level}.',
                {'option_id': dnd_option.id, 'required_min_level': min_level},
            ))

        required_species_id = prerequisites.get('required_species_option_id')
        if isinstance(required_species_id, int) and character_build.species_option_id != required_species_id:
            errors.append(_error(
                'prerequisite_species',
                f'Selection "{dnd_option.name}" requires a different species.',
                {'option_id': dnd_option.id,
                    'required_species_option_id': required_species_id},
            ))

    return ValidationResult(is_valid=not errors, errors=errors)
