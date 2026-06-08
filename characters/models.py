from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models


class CharacterBuild(models.Model):
    if TYPE_CHECKING:
        # Reverse relation from CharacterClassLevel.character_build.
        class_levels: Any
        # Reverse relation from CharacterSelectedOption.character_build.
        selected_options: Any
        campaign: Any
        owner_id: int
        # Django-generated FK id attributes used in validation/services.
        species_option_id: int | None
        background_option_id: int | None

    class BuildType(models.TextChoices):
        PLAYER_CHARACTER = 'PLAYER_CHARACTER', 'Player Character'
        NPC = 'NPC', 'NPC'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVED = 'ARCHIVED', 'Archived'

    class Visibility(models.TextChoices):
        PRIVATE = 'PRIVATE', 'Private'
        CAMPAIGN_VISIBLE = 'CAMPAIGN_VISIBLE', 'Campaign Visible'

    class ValidationStatus(models.TextChoices):
        VALID = 'VALID', 'Valid'
        INVALID = 'INVALID', 'Invalid'
        STALE = 'STALE', 'Stale'
        UNKNOWN = 'UNKNOWN', 'Unknown'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='character_builds')
    campaign = models.ForeignKey(
        'campaigns.Campaign', on_delete=models.CASCADE, related_name='character_builds')
    name = models.CharField(max_length=255)
    build_type = models.CharField(
        max_length=20, choices=BuildType.choices, default=BuildType.PLAYER_CHARACTER)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    character_level = models.PositiveIntegerField(default=1)
    species_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='species_builds',
    )
    background_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='background_builds',
    )
    ability_scores = models.JSONField(default=dict, blank=True)
    selected_feats = models.ManyToManyField(
        'dnd_options.DNDOption', blank=True, related_name='feat_builds')
    selected_spells = models.ManyToManyField(
        'dnd_options.DNDOption', blank=True, related_name='spell_builds')
    selected_equipment = models.ManyToManyField(
        'dnd_options.DNDOption', blank=True, related_name='equipment_builds')
    selected_features = models.ManyToManyField(
        'dnd_options.DNDOption', blank=True, related_name='feature_builds')
    attacks_actions = models.ManyToManyField(
        'dnd_options.DNDOption', blank=True, related_name='attack_builds')
    notes = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)
    ai_prompt_used = models.TextField(blank=True)
    ai_explanation = models.TextField(blank=True)
    needs_revalidation = models.BooleanField(default=False)
    revalidation_reason = models.TextField(blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=20, choices=ValidationStatus.choices, default=ValidationStatus.UNKNOWN)
    validation_errors = models.JSONField(default=list, blank=True)
    manual_overrides = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class CharacterClassLevel(models.Model):
    character_build = models.ForeignKey(
        CharacterBuild, on_delete=models.CASCADE, related_name='class_levels')
    class_option = models.ForeignKey(
        'dnd_options.DNDOption', on_delete=models.CASCADE, related_name='class_level_entries')
    subclass_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subclass_level_entries',
    )
    level_count = models.PositiveIntegerField(default=1)
    ordering = models.PositiveIntegerField(default=1)
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordering']
        unique_together = ('character_build', 'ordering')

    def __str__(self):
        return f'{self.character_build} - {self.class_option} ({self.level_count})'


class CharacterSelectedOption(models.Model):
    class OptionType(models.TextChoices):
        SPECIES = 'SPECIES', 'Species'
        BACKGROUND = 'BACKGROUND', 'Background'
        FEAT = 'FEAT', 'Feat'
        SPELL = 'SPELL', 'Spell'
        EQUIPMENT = 'EQUIPMENT', 'Equipment'
        FEATURE = 'FEATURE', 'Feature'
        ATTACK = 'ATTACK', 'Attack'

    character_build = models.ForeignKey(
        CharacterBuild,
        on_delete=models.CASCADE,
        related_name='selected_options',
    )
    dnd_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.CASCADE,
        related_name='character_selected_entries',
    )
    option_type = models.CharField(max_length=20, choices=OptionType.choices)
    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('character_build', 'dnd_option', 'option_type')
        ordering = ['selected_at']

    def __str__(self):
        return f'{self.character_build} - {self.option_type}: {self.dnd_option}'
