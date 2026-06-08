from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Campaign


@receiver(pre_save, sender=Campaign)
def capture_previous_active_ruleset(sender, instance: Campaign, **kwargs):
    if not instance.pk:
        instance._previous_active_ruleset_id = None
        return

    previous = Campaign.objects.filter(
        pk=instance.pk).values('active_ruleset_id').first()
    instance._previous_active_ruleset_id = previous['active_ruleset_id'] if previous else None


@receiver(post_save, sender=Campaign)
def mark_builds_stale_when_campaign_ruleset_changes(sender, instance: Campaign, created: bool, **kwargs):
    if created:
        return

    previous_ruleset_id = getattr(
        instance, '_previous_active_ruleset_id', None)
    if previous_ruleset_id == instance.active_ruleset_id:
        return

    from characters.models import CharacterBuild

    CharacterBuild.objects.filter(campaign=instance).update(
        needs_revalidation=True,
        validation_status=CharacterBuild.ValidationStatus.STALE,
        revalidation_reason='The campaign ruleset changed after this character was last validated.',
    )
