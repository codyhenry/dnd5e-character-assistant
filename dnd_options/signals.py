from __future__ import annotations

from copy import deepcopy

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import DNDOption

CONTENT_FIELDS = {
    'name',
    'option_type',
    'parent_option_id',
    'source_url',
    'source_category',
    'description',
    'summary',
    'prerequisites',
    'traits',
    'normalized_data',
    'primary_ability_scores',
    'mechanical_tags',
    'visual_or_flavor_tags',
    'build_notes',
    'review_reasons',
}


def _snapshot_content(option: DNDOption) -> dict:
    return {
        'name': option.name,
        'option_type': option.option_type,
        'parent_option_id': option.parent_option_id,
        'source_url': option.source_url,
        'source_category': option.source_category,
        'description': option.description,
        'summary': option.summary,
        'prerequisites': deepcopy(option.prerequisites),
        'traits': deepcopy(option.traits),
        'normalized_data': deepcopy(option.normalized_data),
        'primary_ability_scores': deepcopy(option.primary_ability_scores),
        'mechanical_tags': deepcopy(option.mechanical_tags),
        'visual_or_flavor_tags': deepcopy(option.visual_or_flavor_tags),
        'build_notes': deepcopy(option.build_notes),
        'review_reasons': deepcopy(option.review_reasons),
    }


@receiver(pre_save, sender=DNDOption)
def _capture_previous_dnd_option_content(sender, instance: DNDOption, **kwargs):
    if not instance.pk:
        instance._previous_content_snapshot = None
        return

    previous = DNDOption.objects.filter(pk=instance.pk).first()
    instance._previous_content_snapshot = _snapshot_content(
        previous) if previous else None


@receiver(post_save, sender=DNDOption)
def _mark_linked_knowledge_for_option_content_change(sender, instance: DNDOption, created: bool, **kwargs):
    if created:
        return

    previous = getattr(instance, '_previous_content_snapshot', None)
    if previous is None:
        return

    current = _snapshot_content(instance)
    changed_fields = [field for field in CONTENT_FIELDS if previous.get(
        field) != current.get(field)]
    if not changed_fields:
        return

    from ai_builder.services import mark_linked_knowledge_for_refresh

    mark_linked_knowledge_for_refresh(
        dnd_option=instance,
        reason='Linked D&D option content changed; refresh knowledge row from source.',
    )
