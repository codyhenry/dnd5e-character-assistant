from django.db import models


class DNDOption(models.Model):
    class OptionType(models.TextChoices):
        CLASS = 'CLASS', 'Class'
        SUBCLASS = 'SUBCLASS', 'Subclass'
        SPECIES = 'SPECIES', 'Species/Race/Lineage'
        BACKGROUND = 'BACKGROUND', 'Background'
        FEAT = 'FEAT', 'Feat'
        SPELL = 'SPELL', 'Spell'
        EQUIPMENT = 'EQUIPMENT', 'Equipment'
        FEATURE = 'FEATURE', 'Feature/Trait'
        ATTACK = 'ATTACK', 'Attack/Action'
        FIGHTING_STYLE = 'FIGHTING_STYLE', 'Fighting Style'
        INVOCATION = 'INVOCATION', 'Invocation'
        MANEUVER = 'MANEUVER', 'Maneuver'
        OTHER = 'OTHER', 'Other'

    class SourceCategory(models.TextChoices):
        OFFICIAL = 'official', 'Official'
        SETTING_SPECIFIC = 'setting-specific', 'Setting Specific'
        UNEARTHED_ARCANA = 'unearthed-arcana', 'Unearthed Arcana'
        HOMEBREW = 'homebrew', 'Homebrew'
        CUSTOM = 'custom', 'Custom'

    name = models.CharField(max_length=255)
    option_type = models.CharField(max_length=30, choices=OptionType.choices)
    parent_option = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_options')
    source_url = models.URLField(blank=True)
    source_category = models.CharField(max_length=50, choices=SourceCategory.choices, default=SourceCategory.OFFICIAL)
    description = models.TextField(blank=True)
    prerequisites = models.JSONField(default=dict, blank=True)
    traits = models.JSONField(default=list, blank=True)
    normalized_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.option_type})'
