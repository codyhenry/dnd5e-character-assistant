from typing import TYPE_CHECKING, Any

from django.db import models


class KnowledgeBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OptionLinkedKnowledgeModel(KnowledgeBaseModel):
    if TYPE_CHECKING:
        dnd_option: Any

    dnd_option = models.OneToOneField(
        'dnd_options.DNDOption',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_record',
    )
    source_url = models.URLField(blank=True)
    source_category = models.CharField(max_length=50, blank=True)
    summary = models.TextField(blank=True)
    primary_ability_scores = models.JSONField(default=list, blank=True)
    prerequisites = models.JSONField(default=dict, blank=True)
    traits = models.JSONField(default=dict, blank=True)
    mechanical_tags = models.JSONField(default=list, blank=True)
    visual_or_flavor_tags = models.JSONField(default=list, blank=True)
    build_notes = models.JSONField(default=list, blank=True)
    confidence = models.FloatField(default=0.0)
    needs_review = models.BooleanField(default=False)
    review_reasons = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True


class KnowledgeTrait(KnowledgeBaseModel):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class KnowledgeArmor(OptionLinkedKnowledgeModel):
    class ArmorCategory(models.TextChoices):
        LIGHT = 'light', 'Light'
        MEDIUM = 'medium', 'Medium'
        HEAVY = 'heavy', 'Heavy'
        SHIELD = 'shield', 'Shield'

    name = models.CharField(max_length=120)
    armor_category = models.CharField(
        max_length=20, choices=ArmorCategory.choices)
    armor_class_formula = models.CharField(max_length=120)
    strength_requirement = models.CharField(max_length=80, blank=True)
    stealth_disadvantage = models.BooleanField(default=False)
    weight = models.CharField(max_length=50, blank=True)
    cost = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'armor_category')]

    def __str__(self) -> str:
        return f'{self.name} ({self.armor_category})'


class KnowledgeWeapon(OptionLinkedKnowledgeModel):
    if TYPE_CHECKING:
        properties: Any

    class WeaponCategory(models.TextChoices):
        SIMPLE = 'simple', 'Simple'
        MARTIAL = 'martial', 'Martial'

    class AttackType(models.TextChoices):
        MELEE = 'melee', 'Melee'
        RANGED = 'ranged', 'Ranged'

    name = models.CharField(max_length=120)
    weapon_category = models.CharField(
        max_length=20, choices=WeaponCategory.choices)
    attack_type = models.CharField(max_length=20, choices=AttackType.choices)
    cost = models.CharField(max_length=50, blank=True)
    damage = models.CharField(max_length=80, blank=True)
    weight = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'weapon_category', 'attack_type')]

    def __str__(self) -> str:
        return f'{self.name} ({self.weapon_category} {self.attack_type})'


class KnowledgeWeaponProperty(KnowledgeBaseModel):
    weapon = models.ForeignKey(
        KnowledgeWeapon, on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    range_raw = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['weapon_id', 'name']

    def __str__(self) -> str:
        return f'{self.weapon.name}: {self.name}'


class KnowledgeSpellComponent(KnowledgeBaseModel):
    code = models.CharField(max_length=1, unique=True)
    name = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    trade_off = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self) -> str:
        return self.code


class KnowledgeSpell(OptionLinkedKnowledgeModel):
    name = models.CharField(max_length=160)
    spell_level = models.PositiveSmallIntegerField(default=0)
    spell_level_label = models.CharField(max_length=50, blank=True)
    school = models.CharField(max_length=40, blank=True)
    source_book = models.CharField(max_length=80, blank=True)

    casting_time_raw = models.CharField(max_length=120, blank=True)
    casting_time_action_type = models.CharField(max_length=50, blank=True)
    casting_time_amount = models.PositiveSmallIntegerField(
        null=True, blank=True)
    casting_time_unit = models.CharField(max_length=30, blank=True)
    casting_time_reaction_trigger = models.TextField(blank=True)

    range_raw = models.CharField(max_length=120, blank=True)
    range_type = models.CharField(max_length=40, blank=True)
    range_distance = models.PositiveIntegerField(null=True, blank=True)
    range_unit = models.CharField(max_length=30, blank=True)

    verbal = models.BooleanField(default=False)
    somatic = models.BooleanField(default=False)
    material = models.BooleanField(default=False)
    material_description = models.TextField(blank=True)
    material_consumed = models.BooleanField(default=False)
    material_cost_gp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    component_requirements = models.JSONField(default=list, blank=True)

    duration_raw = models.CharField(max_length=120, blank=True)
    duration_type = models.CharField(max_length=40, blank=True)
    duration_amount = models.PositiveIntegerField(null=True, blank=True)
    duration_unit = models.CharField(max_length=30, blank=True)
    concentration = models.BooleanField(default=False)
    ritual = models.BooleanField(default=False)

    classes = models.JSONField(default=list, blank=True)
    subclasses = models.JSONField(default=list, blank=True)
    damage = models.JSONField(default=list, blank=True)
    healing = models.JSONField(default=list, blank=True)
    saving_throw = models.JSONField(default=dict, blank=True)
    spell_attack = models.JSONField(default=dict, blank=True)
    area_of_effect = models.JSONField(default=dict, blank=True)
    targeting = models.JSONField(default=dict, blank=True)
    conditions_inflicted = models.JSONField(default=list, blank=True)
    conditions_removed = models.JSONField(default=list, blank=True)
    buffs = models.JSONField(default=list, blank=True)
    debuffs = models.JSONField(default=list, blank=True)
    summons = models.JSONField(default=list, blank=True)
    created_objects = models.JSONField(default=list, blank=True)
    movement_effects = models.JSONField(default=list, blank=True)
    utility_effects = models.JSONField(default=list, blank=True)
    scaling = models.JSONField(default=list, blank=True)
    resource_interactions = models.JSONField(default=list, blank=True)
    restrictions = models.JSONField(default=list, blank=True)
    raw_effect_text = models.TextField(blank=True)
    validation_notes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'source_url')]

    def __str__(self) -> str:
        return self.name


class KnowledgeFeat(OptionLinkedKnowledgeModel):
    name = models.CharField(max_length=160)
    feat_category = models.CharField(max_length=80, blank=True)
    ability_score_increases = models.JSONField(default=list, blank=True)
    granted_spells = models.JSONField(default=list, blank=True)
    granted_cantrips = models.JSONField(default=list, blank=True)
    granted_proficiencies = models.JSONField(default=dict, blank=True)
    granted_features = models.JSONField(default=list, blank=True)
    limited_use_features = models.JSONField(default=list, blank=True)
    optional_rules = models.JSONField(default=list, blank=True)
    choice_points = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'source_url')]

    def __str__(self) -> str:
        return self.name


class KnowledgeSpecies(OptionLinkedKnowledgeModel):
    if TYPE_CHECKING:
        features: Any
        variants: Any

    name = models.CharField(max_length=160)
    creature_type = models.CharField(max_length=60, blank=True)
    size = models.CharField(max_length=30, blank=True)

    speed_walking = models.PositiveSmallIntegerField(null=True, blank=True)
    speed_flying = models.PositiveSmallIntegerField(null=True, blank=True)
    speed_swimming = models.PositiveSmallIntegerField(null=True, blank=True)
    speed_climbing = models.PositiveSmallIntegerField(null=True, blank=True)
    speed_burrowing = models.PositiveSmallIntegerField(null=True, blank=True)

    darkvision = models.PositiveSmallIntegerField(null=True, blank=True)
    blindsight = models.PositiveSmallIntegerField(null=True, blank=True)
    tremorsense = models.PositiveSmallIntegerField(null=True, blank=True)
    truesight = models.PositiveSmallIntegerField(null=True, blank=True)

    ability_score_increases = models.JSONField(default=dict, blank=True)
    languages = models.JSONField(default=list, blank=True)
    proficiencies = models.JSONField(default=dict, blank=True)
    resistances = models.JSONField(default=list, blank=True)
    damage_immunities = models.JSONField(default=list, blank=True)
    condition_immunities = models.JSONField(default=list, blank=True)

    has_lineage_spellcasting = models.BooleanField(default=False)
    lineage_spells = models.JSONField(default=list, blank=True)
    spellcasting_ability = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'source_url')]

    def __str__(self) -> str:
        return self.name


class KnowledgeSpeciesFeature(KnowledgeBaseModel):
    species = models.ForeignKey(
        KnowledgeSpecies, on_delete=models.CASCADE, related_name='features')
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    action_type = models.CharField(max_length=40, blank=True)
    uses = models.CharField(max_length=80, blank=True)
    recovery = models.CharField(max_length=80, blank=True)
    scales_with_level = models.BooleanField(default=False)
    traits = models.JSONField(default=dict, blank=True)
    raw_text = models.TextField(blank=True)

    class Meta:
        ordering = ['species_id', 'name']

    def __str__(self) -> str:
        return f'{self.species.name}: {self.name}'


class KnowledgeSpeciesVariant(KnowledgeBaseModel):
    species = models.ForeignKey(
        KnowledgeSpecies, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    traits = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['species_id', 'name']

    def __str__(self) -> str:
        return f'{self.species.name}: {self.name}'


class KnowledgeClass(OptionLinkedKnowledgeModel):
    if TYPE_CHECKING:
        parent: Any

    class ClassType(models.TextChoices):
        CLASS = 'class', 'Class'
        SUBCLASS = 'subclass', 'Subclass'

    name = models.CharField(max_length=160)
    class_type = models.CharField(max_length=20, choices=ClassType.choices)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='subclasses',
    )

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'class_type', 'source_url')]

    def __str__(self) -> str:
        return f'{self.name} ({self.class_type})'
