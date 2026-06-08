from __future__ import annotations

from copy import deepcopy
from typing import Any
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ai_builder.knowledge.allowed_traits import ALLOWED_TRAITS

from .json_path import (
    add_value_at_path,
    get_value_at_path,
    normalize_json_path,
    remove_value_at_path,
    set_value_at_path,
    validate_json_path,
)
from .models import DNDOption, DNDOptionReview, DNDOptionReviewComment, DNDOptionSuggestedChange

ALLOWED_TOP_LEVEL_PATHS = {
    'name',
    'option_type',
    'parent',
    'source_url',
    'source_category',
    'description',
    'prerequisites',
    'traits',
    'normalized_data',
    'summary',
    'primary_ability_scores',
    'mechanical_tags',
    'visual_or_flavor_tags',
    'build_notes',
    'review_reasons',
}

PROTECTED_PATHS = {
    'id',
    'created_at',
    'updated_at',
    'reviewed_by',
    'reviewed_at',
    'needs_review',
    'review_status',
    'validation_status',
    'validation_errors',
}

OPEN_REVIEW_STATUSES = {
    DNDOptionReview.Status.OPEN,
    DNDOptionReview.Status.IN_REVIEW,
    DNDOptionReview.Status.CHANGES_REQUESTED,
}


def _serialize_option_for_review(dnd_option: DNDOption) -> dict:
    return {
        'name': dnd_option.name,
        'option_type': dnd_option.option_type,
        'parent': dnd_option.parent_option.name if dnd_option.parent_option else None,
        'source_url': dnd_option.source_url,
        'source_category': dnd_option.source_category,
        'description': dnd_option.description,
        'summary': dnd_option.summary,
        'prerequisites': deepcopy(dnd_option.prerequisites),
        'traits': deepcopy(dnd_option.traits),
        'normalized_data': deepcopy(dnd_option.normalized_data),
        'primary_ability_scores': deepcopy(dnd_option.primary_ability_scores),
        'mechanical_tags': deepcopy(dnd_option.mechanical_tags),
        'visual_or_flavor_tags': deepcopy(dnd_option.visual_or_flavor_tags),
        'build_notes': deepcopy(dnd_option.build_notes),
        'review_reasons': deepcopy(dnd_option.review_reasons),
    }


def _save_option_from_review_document(dnd_option: DNDOption, document: dict) -> DNDOption:
    dnd_option.name = document['name']
    dnd_option.option_type = document['option_type']
    dnd_option.source_url = document.get('source_url', '')
    dnd_option.source_category = document['source_category']
    dnd_option.description = document.get('description', '')
    dnd_option.summary = document.get('summary', '')
    dnd_option.prerequisites = document.get('prerequisites') or {}
    dnd_option.traits = document.get('traits') or {}
    dnd_option.normalized_data = document.get('normalized_data') or {}
    dnd_option.primary_ability_scores = document.get(
        'primary_ability_scores') or []
    dnd_option.mechanical_tags = document.get('mechanical_tags') or []
    dnd_option.visual_or_flavor_tags = document.get(
        'visual_or_flavor_tags') or []
    dnd_option.build_notes = document.get('build_notes') or []
    dnd_option.review_reasons = document.get('review_reasons') or []

    parent_name = document.get('parent')
    if parent_name:
        parent_option = DNDOption.objects.filter(name=parent_name).first()
        if parent_option is None:
            raise ValidationError(
                'Parent option must reference an existing DNDOption by name.')
        dnd_option.parent_option = parent_option
    else:
        dnd_option.parent_option = None

    dnd_option.save()
    return dnd_option


def create_review_for_option(dnd_option, reason, ai_review_reasons=None, opened_by=None):
    ai_review_reasons = ai_review_reasons or []
    from .services import infer_review_severity

    return DNDOptionReview.objects.create(
        dnd_option=dnd_option,
        reason=reason,
        ai_review_reasons=ai_review_reasons,
        severity=infer_review_severity(ai_review_reasons),
        status=DNDOptionReview.Status.OPEN,
        opened_by=opened_by,
    )


def get_or_create_open_review_for_option(dnd_option, reason='AI flagged this option for review.', ai_review_reasons=None, opened_by=None):
    ai_review_reasons = ai_review_reasons or []
    from .services import infer_review_severity

    existing = dnd_option.reviews.filter(
        status__in=OPEN_REVIEW_STATUSES).order_by('-updated_at').first()
    if existing:
        existing.reason = reason
        existing.ai_review_reasons = ai_review_reasons
        existing.severity = infer_review_severity(ai_review_reasons)
        existing.save(
            update_fields=['reason', 'ai_review_reasons', 'severity', 'updated_at'])
        return existing

    return create_review_for_option(
        dnd_option,
        reason=reason,
        ai_review_reasons=ai_review_reasons,
        opened_by=opened_by,
    )


def get_snapshot_for_path(dnd_option, target_path):
    document = _serialize_option_for_review(dnd_option)
    return get_value_at_path(document, target_path)


def add_review_comment(review, author, comment, target_path=None, visibility='PUBLIC'):
    snapshot = None
    normalized_path = None
    if target_path:
        normalized_path = normalize_json_path(target_path)
        if not validate_json_path(normalized_path):
            raise ValidationError('Invalid target path syntax.')
        try:
            snapshot = get_snapshot_for_path(
                review.dnd_option, normalized_path)
        except (KeyError, IndexError):
            snapshot = None

    return DNDOptionReviewComment.objects.create(
        review=review,
        author=author,
        comment=comment,
        target_path=normalized_path,
        target_snapshot=snapshot,
        visibility=visibility,
    )


def _is_trait_path(target_path: str) -> bool:
    return target_path.startswith('traits') or '.traits' in target_path


def _validate_trait_map(trait_map):
    if not isinstance(trait_map, dict):
        raise ValidationError('Trait maps must be JSON objects.')
    for trait_name, weight in trait_map.items():
        if trait_name not in ALLOWED_TRAITS:
            raise ValidationError(f'Unsupported trait: {trait_name}')
        if not isinstance(weight, (int, float)) or weight < 0.0 or weight > 1.0:
            raise ValidationError(
                f'Trait weight must be between 0.0 and 1.0 for {trait_name}.')


def _validate_general_document(document: dict):
    if document['option_type'] not in DNDOption.OptionType.values:
        raise ValidationError('Invalid option_type.')
    if document['source_category'] not in DNDOption.SourceCategory.values:
        raise ValidationError('Invalid source_category.')


def _top_level_path(target_path: str) -> str:
    first = target_path.split('.', 1)[0]
    return first.split('[', 1)[0]


def _validate_target_path_permissions(target_path: str):
    top = _top_level_path(target_path)
    if top in PROTECTED_PATHS:
        raise ValidationError(
            f'Path {top} is protected and cannot be changed.')
    if top not in ALLOWED_TOP_LEVEL_PATHS:
        raise ValidationError(f'Path {top} is not editable.')


def _path_exists(document: dict, target_path: str) -> bool:
    try:
        get_value_at_path(document, target_path)
        return True
    except (KeyError, IndexError):
        return False


def propose_option_change(review, proposed_by, target_path, operation, proposed_value, reason):
    normalized_path = normalize_json_path(target_path)
    if not validate_json_path(normalized_path):
        raise ValidationError('Invalid target path syntax.')

    _validate_target_path_permissions(normalized_path)

    if operation not in DNDOptionSuggestedChange.Operation.values:
        raise ValidationError('Invalid operation.')

    document = _serialize_option_for_review(review.dnd_option)
    path_exists = _path_exists(document, normalized_path)

    if operation in {DNDOptionSuggestedChange.Operation.REPLACE, DNDOptionSuggestedChange.Operation.REMOVE} and not path_exists:
        raise ValidationError(
            'Target path must exist for REPLACE and REMOVE operations.')

    if operation in {DNDOptionSuggestedChange.Operation.REPLACE, DNDOptionSuggestedChange.Operation.ADD} and proposed_value is None:
        raise ValidationError(
            'proposed_value is required for ADD and REPLACE operations.')

    current_value = get_value_at_path(
        document, normalized_path) if path_exists else None

    suggested_change = DNDOptionSuggestedChange.objects.create(
        review=review,
        proposed_by=proposed_by,
        target_path=normalized_path,
        current_value=current_value,
        proposed_value=proposed_value,
        operation=operation,
        reason=reason,
    )
    validate_suggested_change(suggested_change)
    return suggested_change


def validate_suggested_change(suggested_change):
    document = _serialize_option_for_review(suggested_change.review.dnd_option)
    target_path = suggested_change.target_path

    _validate_target_path_permissions(target_path)

    if suggested_change.operation == DNDOptionSuggestedChange.Operation.REPLACE:
        updated_document = set_value_at_path(
            document, target_path, suggested_change.proposed_value)
    elif suggested_change.operation == DNDOptionSuggestedChange.Operation.ADD:
        updated_document = add_value_at_path(
            document, target_path, suggested_change.proposed_value)
    elif suggested_change.operation == DNDOptionSuggestedChange.Operation.REMOVE:
        updated_document = remove_value_at_path(document, target_path)
    else:
        raise ValidationError('Unsupported operation.')

    if not isinstance(updated_document, dict):
        raise ValidationError('Updated document must be a JSON object.')

    if _is_trait_path(target_path):
        if '.traits' in target_path:
            traits_path = target_path.split('.traits', 1)[0] + '.traits'
            trait_map = get_value_at_path(updated_document, traits_path)
            _validate_trait_map(trait_map)
        elif target_path == 'traits':
            _validate_trait_map(updated_document.get('traits'))
        else:
            _validate_trait_map(updated_document.get('traits'))

    _validate_general_document(updated_document)
    return True


def approve_suggested_change(suggested_change, reviewer):
    suggested_change.status = DNDOptionSuggestedChange.Status.APPROVED
    suggested_change.reviewed_by = reviewer
    suggested_change.reviewed_at = timezone.now()
    suggested_change.rejection_reason = ''
    suggested_change.save(update_fields=[
                          'status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at'])
    return suggested_change


def reject_suggested_change(suggested_change, reviewer, reason):
    suggested_change.status = DNDOptionSuggestedChange.Status.REJECTED
    suggested_change.reviewed_by = reviewer
    suggested_change.reviewed_at = timezone.now()
    suggested_change.rejection_reason = reason
    suggested_change.save(update_fields=[
                          'status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at'])
    return suggested_change


def apply_suggested_change(suggested_change, applier):
    if suggested_change.status != DNDOptionSuggestedChange.Status.APPROVED:
        raise ValidationError(
            'Suggested change must be approved before it can be applied.')

    with transaction.atomic():
        dnd_option = suggested_change.review.dnd_option
        document = _serialize_option_for_review(dnd_option)

        if suggested_change.operation == DNDOptionSuggestedChange.Operation.REPLACE:
            previous_value = get_value_at_path(
                document, suggested_change.target_path)
            updated_document = set_value_at_path(
                document, suggested_change.target_path, suggested_change.proposed_value)
        elif suggested_change.operation == DNDOptionSuggestedChange.Operation.ADD:
            previous_value = get_value_at_path(document, suggested_change.target_path) if _path_exists(
                document, suggested_change.target_path) else None
            updated_document = add_value_at_path(
                document, suggested_change.target_path, suggested_change.proposed_value)
        else:
            previous_value = get_value_at_path(
                document, suggested_change.target_path)
            updated_document = remove_value_at_path(
                document, suggested_change.target_path)

        if not isinstance(updated_document, dict):
            raise ValidationError('Updated document must be a JSON object.')

        suggested_change.current_value = previous_value
        _validate_general_document(updated_document)
        if _is_trait_path(suggested_change.target_path):
            if suggested_change.target_path.startswith('traits'):
                _validate_trait_map(updated_document.get('traits'))
            else:
                nested_traits_path = suggested_change.target_path.split('.traits', 1)[
                    0] + '.traits'
                _validate_trait_map(get_value_at_path(
                    updated_document, nested_traits_path))
        _save_option_from_review_document(dnd_option, updated_document)

        from characters.services import mark_builds_stale_for_dnd_option
        mark_builds_stale_for_dnd_option(
            dnd_option,
            reason='One or more D&D options used by this character were reviewed and updated.',
        )

        from ai_builder.services import mark_linked_knowledge_for_refresh
        mark_linked_knowledge_for_refresh(
            dnd_option=dnd_option,
            reason='Linked D&D option was reviewed and updated; refresh knowledge row from source.',
        )

        suggested_change.status = DNDOptionSuggestedChange.Status.APPLIED
        suggested_change.applied_by = applier
        suggested_change.applied_at = timezone.now()
        suggested_change.save(update_fields=[
                              'current_value', 'status', 'applied_by', 'applied_at', 'updated_at'])

    return suggested_change


def resolve_review(review, resolver, status, resolution_notes):
    if status not in {
        DNDOptionReview.Status.APPROVED,
        DNDOptionReview.Status.NO_CHANGE_NEEDED,
        DNDOptionReview.Status.REJECTED,
        DNDOptionReview.Status.CLOSED,
    }:
        raise ValidationError('Invalid resolution status.')

    review.status = status
    review.resolution_notes = resolution_notes
    review.resolved_by = resolver
    review.resolved_at = timezone.now()
    review.save(update_fields=['status', 'resolution_notes',
                'resolved_by', 'resolved_at', 'updated_at'])

    if status in {DNDOptionReview.Status.APPROVED, DNDOptionReview.Status.NO_CHANGE_NEEDED}:
        mark_option_reviewed(review.dnd_option, resolver,
                             notes=resolution_notes)

    return review


def mark_option_reviewed(dnd_option, reviewer, notes=''):
    dnd_option.needs_review = False
    dnd_option.review_status = DNDOption.ReviewStatus.REVIEWED
    dnd_option.reviewed_by = reviewer
    dnd_option.reviewed_at = timezone.now()
    dnd_option.review_notes = notes
    dnd_option.save(update_fields=['needs_review', 'review_status',
                    'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])
    return dnd_option


def import_dnd_option_from_ai_payload(payload: dict, opened_by=None):
    from .services import import_dnd_option_from_ai_payload as _import

    return _import(payload, opened_by=opened_by)
