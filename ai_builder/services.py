from characters.validators import ValidationResult, validate_character_build
from dnd_options.selectors import search_options

from .selectors import (
    search_knowledge_classes,
    search_knowledge_feats,
    search_knowledge_species,
    search_knowledge_spells,
    search_knowledge_weapons,
)


def extract_build_intent(user_prompt: str) -> dict:
    return {
        'fantasy_summary': user_prompt.strip(),
        'desired_traits': [],
        'mechanical_priorities': [],
        'visual_reflavor': '',
        'explicit_constraints': [],
    }


def retrieve_candidate_options(intent: dict, ruleset) -> list:
    option_queryset = search_options(
        traits=intent.get('desired_traits') or None)
    if ruleset.allowed_source_categories:
        option_queryset = option_queryset.filter(
            source_category__in=ruleset.allowed_source_categories)
    return list(option_queryset[:25])


def retrieve_candidate_knowledge(intent: dict, ruleset, *, per_type_limit: int = 20) -> dict:
    """Retrieve filtered knowledge rows that align with intent and ruleset constraints."""
    desired_traits = intent.get('desired_traits') or []
    mechanical_priorities = intent.get('mechanical_priorities') or []
    allowed_sources = ruleset.allowed_source_categories or []

    return {
        'spells': list(
            search_knowledge_spells(
                required_traits=desired_traits,
                required_tags=mechanical_priorities,
                source_categories=allowed_sources,
            )[:per_type_limit]
        ),
        'feats': list(
            search_knowledge_feats(
                required_traits=desired_traits,
                required_tags=mechanical_priorities,
                source_categories=allowed_sources,
            )[:per_type_limit]
        ),
        'species': list(
            search_knowledge_species(
                required_traits=desired_traits,
                required_tags=mechanical_priorities,
                source_categories=allowed_sources,
            )[:per_type_limit]
        ),
        'classes': list(
            search_knowledge_classes(
                required_traits=desired_traits,
                required_tags=mechanical_priorities,
                source_categories=allowed_sources,
            )[:per_type_limit]
        ),
        'weapons': list(
            search_knowledge_weapons(
                source_categories=allowed_sources,
            )[:per_type_limit]
        ),
    }


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
    repaired['selected_option_ids'] = [
        option.id for option in legal_options[:3]]
    return repaired


def generate_validated_candidate_flow(*, user_prompt: str, ruleset, transient_character_build) -> tuple[dict, ValidationResult]:
    intent = extract_build_intent(user_prompt)
    legal_options = retrieve_candidate_options(intent, ruleset)
    candidate = generate_candidate_build(intent, legal_options, ruleset)
    validation = validate_character_build(transient_character_build, ruleset)
    if not validation.is_valid:
        candidate = repair_candidate_build(
            candidate, validation.errors, legal_options)
    return candidate, validation


def mark_linked_knowledge_for_refresh(*, dnd_option, reason: str) -> int:
    """Mark all knowledge rows linked to a DNDOption as needing refresh/review."""
    from ai_builder.models import (
        KnowledgeArmor,
        KnowledgeClass,
        KnowledgeFeat,
        KnowledgeSpecies,
        KnowledgeSpell,
        KnowledgeWeapon,
    )

    linked_models = (
        KnowledgeArmor,
        KnowledgeWeapon,
        KnowledgeSpell,
        KnowledgeFeat,
        KnowledgeSpecies,
        KnowledgeClass,
    )

    updated_count = 0
    for model_cls in linked_models:
        queryset = model_cls.objects.filter(dnd_option=dnd_option)
        for row in queryset:
            reasons = list(row.review_reasons or [])
            changed = False
            if reason not in reasons:
                reasons.append(reason)
                row.review_reasons = reasons
                changed = True
            if not row.needs_review:
                row.needs_review = True
                changed = True
            if changed:
                row.save(update_fields=['needs_review',
                         'review_reasons', 'updated_at'])
                updated_count += 1
    return updated_count
