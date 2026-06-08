from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from .models import DNDOption
from .review_services import get_or_create_open_review_for_option


def create_option(**kwargs) -> DNDOption:
    return DNDOption.objects.create(**kwargs)


def infer_review_severity(review_reasons: list[str]) -> str:
    joined = ' '.join(review_reasons).lower()

    high_markers = [
        'invalid',
        'missing required',
        'contradiction',
        'unsupported trait',
        'malformed json',
        'impossible',
        'validation failure',
    ]
    if any(marker in joined for marker in high_markers):
        return 'HIGH'

    medium_markers = [
        'variant',
        'older version',
        'newer version',
        'conflicting version',
        'materially different',
        'ambiguous source',
        'multiple version',
    ]
    if any(marker in joined for marker in medium_markers):
        return 'MEDIUM'

    return 'LOW'


def _normalize_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValidationError('Expected list value in AI payload.')


def import_dnd_option_from_ai_payload(payload: dict, opened_by=None) -> DNDOption:
    """Create or update a DNDOption from an AI payload and auto-open reviews."""
    required_keys = ['name', 'type', 'source_category']
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValidationError(
            f'Missing required payload keys: {", ".join(missing)}')

    option_type = str(payload['type']).upper()
    if option_type not in DNDOption.OptionType.values:
        raise ValidationError(f'Unsupported option type: {option_type}')

    source_category = str(payload['source_category']).lower()
    if source_category not in DNDOption.SourceCategory.values:
        raise ValidationError(
            f'Unsupported source category: {source_category}')

    parent_name = payload.get('parent')
    parent_option = None
    if parent_name:
        parent_option = DNDOption.objects.filter(name=parent_name).first()

    defaults = {
        'option_type': option_type,
        'parent_option': parent_option,
        'source_url': payload.get('source_url', ''),
        'source_category': source_category,
        'description': payload.get('description', ''),
        'summary': payload.get('summary', ''),
        'prerequisites': payload.get('prerequisites') or {},
        'traits': payload.get('traits') or {},
        'normalized_data': payload.get('normalized_data') or {},
        'primary_ability_scores': _normalize_list(payload.get('primary_ability_scores')),
        'mechanical_tags': _normalize_list(payload.get('mechanical_tags')),
        'visual_or_flavor_tags': _normalize_list(payload.get('visual_or_flavor_tags')),
        'build_notes': _normalize_list(payload.get('build_notes')),
        'review_reasons': _normalize_list(payload.get('review_reasons')),
    }

    needs_review = bool(payload.get('needs_review'))
    defaults['needs_review'] = needs_review
    defaults['review_status'] = (
        DNDOption.ReviewStatus.NEEDS_REVIEW if needs_review else DNDOption.ReviewStatus.CLEAN
    )

    option, _created = DNDOption.objects.update_or_create(
        name=payload['name'],
        option_type=option_type,
        defaults=defaults,
    )

    if needs_review:
        review_reasons = defaults['review_reasons']
        reason = review_reasons[0] if review_reasons else 'AI payload flagged this option for review.'
        get_or_create_open_review_for_option(
            option,
            reason=reason,
            ai_review_reasons=review_reasons,
            opened_by=opened_by,
        )

    return option
