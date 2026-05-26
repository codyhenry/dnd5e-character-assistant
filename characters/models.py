from django.conf import settings
from django.db import models


class CharacterBuild(models.Model):
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
        PENDING = 'PENDING', 'Pending'
        VALID = 'VALID', 'Valid'
        INVALID = 'INVALID', 'Invalid'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='character_builds')
    campaign = models.ForeignKey('campaigns.Campaign', on_delete=models.CASCADE, related_name='character_builds')
    name = models.CharField(max_length=255)
    build_type = models.CharField(max_length=20, choices=BuildType.choices, default=BuildType.PLAYER_CHARACTER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
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
    selected_feats = models.ManyToManyField('dnd_options.DNDOption', blank=True, related_name='feat_builds')
    selected_spells = models.ManyToManyField('dnd_options.DNDOption', blank=True, related_name='spell_builds')
    selected_equipment = models.ManyToManyField('dnd_options.DNDOption', blank=True, related_name='equipment_builds')
    selected_features = models.ManyToManyField('dnd_options.DNDOption', blank=True, related_name='feature_builds')
    attacks_actions = models.ManyToManyField('dnd_options.DNDOption', blank=True, related_name='attack_builds')
    notes = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)
    ai_prompt_used = models.TextField(blank=True)
    ai_explanation = models.TextField(blank=True)
    validation_status = models.CharField(max_length=20, choices=ValidationStatus.choices, default=ValidationStatus.PENDING)
    validation_errors = models.JSONField(default=list, blank=True)
    manual_overrides = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class CharacterClassLevel(models.Model):
    character_build = models.ForeignKey(CharacterBuild, on_delete=models.CASCADE, related_name='class_levels')
    class_option = models.ForeignKey('dnd_options.DNDOption', on_delete=models.CASCADE, related_name='class_level_entries')
    subclass_option = models.ForeignKey(
        'dnd_options.DNDOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subclass_level_entries',
    )
    level_count = models.PositiveIntegerField(default=1)
    ordering = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['ordering']
        unique_together = ('character_build', 'ordering')

    def __str__(self):
        return f'{self.character_build} - {self.class_option} ({self.level_count})'
