from characters.validators import ValidationResult, validate_character_build
from dnd_options.selectors import search_options


def extract_build_intent(user_prompt: str) -> dict:
    return {
        'fantasy_summary': user_prompt.strip(),
        'desired_traits': [],
        'mechanical_priorities': [],
        'visual_reflavor': '',
        'explicit_constraints': [],
    }


def retrieve_candidate_options(intent: dict, ruleset) -> list:
    option_queryset = search_options(traits=intent.get('desired_traits') or None)
    if ruleset.allowed_source_categories:
        option_queryset = option_queryset.filter(source_category__in=ruleset.allowed_source_categories)
    return list(option_queryset[:25])


def generate_candidate_build(intent: dict, legal_options: list, ruleset) -> dict:
    return {
        'name': intent.get('fantasy_summary', 'AI Build')[:255] or 'AI Build',
        'ruleset_id': ruleset.id,
        'selected_option_ids': [option.id for option in legal_options[:5]],
        'notes': 'Mocked AI build candidate generated from local options only.',
    }


def repair_candidate_build(candidate_build: dict, validation_errors: list, legal_options: list) -> dict:
    repaired = dict(candidate_build)
    repaired['repair_notes'] = f'Repaired from {len(validation_errors)} validation issue(s).'
    repaired['selected_option_ids'] = [option.id for option in legal_options[:3]]
    return repaired


def generate_validated_candidate_flow(*, user_prompt: str, ruleset, transient_character_build) -> tuple[dict, ValidationResult]:
    intent = extract_build_intent(user_prompt)
    legal_options = retrieve_candidate_options(intent, ruleset)
    candidate = generate_candidate_build(intent, legal_options, ruleset)
    validation = validate_character_build(transient_character_build, ruleset)
    if not validation.is_valid:
        candidate = repair_candidate_build(candidate, validation.errors, legal_options)
    return candidate, validation
