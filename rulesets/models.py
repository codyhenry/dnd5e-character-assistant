from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import models

from .validators import validate_starting_gold_formula


class Ruleset(models.Model):
    if TYPE_CHECKING:
        campaign: Any
        banned_options: Any
        _previous_ruleset_snapshot: dict[str, Any] | None

    campaign = models.ForeignKey(
        'campaigns.Campaign', on_delete=models.CASCADE, related_name='rulesets')
    name = models.CharField(max_length=255)
    banned_classes = models.JSONField(default=list)
    banned_subclasses = models.JSONField(default=list)
    banned_species = models.JSONField(default=list)
    banned_feats = models.JSONField(default=list)
    banned_spells = models.JSONField(default=list)
    required_character_level = models.PositiveIntegerField(default=1)
    starting_gold_formula = models.CharField(
        max_length=255,
        default='0',
        validators=[validate_starting_gold_formula],
    )
    allowed_source_categories = models.JSONField(default=list, blank=True)
    allow_multiclassing = models.BooleanField(default=True)
    allow_feats = models.BooleanField(default=True)
    hidden_ai_guidance = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.campaign}: {self.name}'


class RulesetBannedOption(models.Model):
    ruleset = models.ForeignKey(
        Ruleset, on_delete=models.CASCADE, related_name='banned_options')
    banned_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ruleset_bans',
    )
    banned_character_build = models.ForeignKey(
        'characters.CharacterBuild',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ruleset_bans',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.banned_option and not self.banned_character_build:
            raise ValidationError(
                'Either banned_option or banned_character_build must be set.')

    def __str__(self):
        return f'Ban for {self.ruleset}'
