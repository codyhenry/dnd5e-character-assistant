from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Ruleset, RulesetBannedOption


@receiver(pre_save, sender=Ruleset)
def capture_previous_ruleset_fields(sender, instance: Ruleset, **kwargs):
    if not instance.pk:
        instance._previous_ruleset_snapshot = None
        return

    previous = Ruleset.objects.filter(pk=instance.pk).values(
        'allowed_source_categories',
        'allow_multiclassing',
        'allow_feats',
    ).first()
    instance._previous_ruleset_snapshot = previous


@receiver(post_save, sender=Ruleset)
def mark_builds_stale_when_ruleset_restrictions_change(sender, instance: Ruleset, created: bool, **kwargs):
    if created:
        return

    previous = getattr(instance, '_previous_ruleset_snapshot', None)
    if not previous:
        return

    changed = (
        previous['allowed_source_categories'] != instance.allowed_source_categories
        or previous['allow_multiclassing'] != instance.allow_multiclassing
        or previous['allow_feats'] != instance.allow_feats
    )
    if not changed:
        return

    from characters.services import mark_builds_stale_for_ruleset

    mark_builds_stale_for_ruleset(
        instance,
        reason='The campaign ruleset changed after this character was last validated.',
    )


@receiver(post_save, sender=RulesetBannedOption)
def mark_builds_stale_when_ban_added(sender, instance: RulesetBannedOption, **kwargs):
    from characters.services import mark_builds_stale_for_ruleset

    mark_builds_stale_for_ruleset(
        instance.ruleset,
        reason='The campaign ruleset changed after this character was last validated.',
    )


@receiver(post_delete, sender=RulesetBannedOption)
def mark_builds_stale_when_ban_removed(sender, instance: RulesetBannedOption, **kwargs):
    from characters.services import mark_builds_stale_for_ruleset

    mark_builds_stale_for_ruleset(
        instance.ruleset,
        reason='The campaign ruleset changed after this character was last validated.',
    )
