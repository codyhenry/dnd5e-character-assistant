import tempfile
from pathlib import Path
from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from campaigns.models import Campaign, CampaignMembership
from dnd_options.models import DNDOption
from rulesets.models import Ruleset

from .forms import AICharacterPromptForm
from .models import (
    KnowledgeArmor,
    KnowledgeClass,
    KnowledgeFeat,
    KnowledgeSpecies,
    KnowledgeSpell,
    KnowledgeSpellComponent,
    KnowledgeTrait,
    KnowledgeWeapon,
    KnowledgeWeaponProperty,
)
from .selectors import (
    search_knowledge_classes,
    search_knowledge_feats,
    search_knowledge_species,
    search_knowledge_spells,
    search_knowledge_weapons,
)
from .services import retrieve_candidate_knowledge


class AIBuilderCampaignFilteringTests(TestCase):
    def test_form_campaign_dropdown_shows_only_active_campaigns(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username='aiuser', password='pw')

        active_campaign = Campaign.objects.create(
            name='Active Campaign',
            description='active',
            owner=user,
            status=Campaign.Status.ACTIVE,
        )
        ended_campaign = Campaign.objects.create(
            name='Ended Campaign',
            description='ended',
            owner=user,
            status=Campaign.Status.ENDED,
        )
        CampaignMembership.objects.create(
            user=user, campaign=active_campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=user, campaign=ended_campaign, role=CampaignMembership.Role.DM)

        form = AICharacterPromptForm(user=user)
        queryset = cast(forms.ModelChoiceField,
                        form.fields['campaign']).queryset

        self.assertIn(active_campaign, queryset)
        self.assertNotIn(ended_campaign, queryset)


class LoadKnowledgeCommandTests(TestCase):
    def _write_file(self, file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')

    def test_load_knowledge_imports_data_and_links_dnd_options(self):
        dnd_class = DNDOption.objects.create(
            name='Artificer',
            option_type=DNDOption.OptionType.CLASS,
            source_url='https://example.com/class',
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        dnd_spell = DNDOption.objects.create(
            name='Blade Ward',
            option_type=DNDOption.OptionType.SPELL,
            source_url='https://example.com/spell',
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        dnd_feat = DNDOption.objects.create(
            name='Actor',
            option_type=DNDOption.OptionType.FEAT,
            source_url='https://example.com/feat',
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        dnd_species = DNDOption.objects.create(
            name='Dragonborn',
            option_type=DNDOption.OptionType.SPECIES,
            source_url='https://example.com/species',
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        dnd_equipment = DNDOption.objects.create(
            name='Club',
            option_type=DNDOption.OptionType.EQUIPMENT,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_root = Path(tmpdir)
            self._write_file(
                knowledge_root / 'allowed_traits.py',
                'ALLOWED_TRAITS = ["melee", "support"]\n',
            )
            self._write_file(
                knowledge_root / 'armor.json',
                '{"armor": {"light": [{"name": "Leather", "armor_class": "11 + Dex modifier", "strength": null, "stealth": null, "weight": "10 lb.", "cost": "10 gp"}]}}\n',
            )
            self._write_file(
                knowledge_root / 'weapons.json',
                '{"simple": {"melee": [{"name": "Club", "cost": "1 sp", "damage": "1d4 bludgeoning", "weight": "2 lb.", "properties": [{"name": "Light", "description": "test"}]}], "ranged": []}, "martial": {"melee": [], "ranged": []}}\n',
            )
            self._write_file(
                knowledge_root / 'classes.json',
                '[{"name": "Artificer", "type": "class", "source_url": "https://example.com/class", "source_category": "official", "summary": "", "primary_ability_scores": ["intelligence"], "prerequisites": {}, "traits": {}, "mechanical_tags": [], "visual_or_flavor_tags": [], "build_notes": [], "confidence": 0.9, "needs_review": false, "review_reasons": []}]\n',
            )
            self._write_file(
                knowledge_root / 'feats.json',
                '[{"name": "Actor", "type": "feat", "source_url": "https://example.com/feat", "source_category": "official", "summary": "", "primary_ability_scores": ["charisma"], "prerequisites": {}, "traits": {}, "mechanical_tags": [], "visual_or_flavor_tags": [], "build_notes": [], "confidence": 0.9, "needs_review": false, "review_reasons": [], "normalized_data": {"feat_category": "general", "ability_score_increases": [], "granted_spells": [], "granted_cantrips": [], "granted_proficiencies": {}, "granted_features": [], "limited_use_features": [], "optional_rules": [], "choice_points": []}}]\n',
            )
            self._write_file(
                knowledge_root / 'lineages.json',
                '[{"name": "Dragonborn", "type": "species", "source_url": "https://example.com/species", "source_category": "official", "summary": "", "primary_ability_scores": ["strength"], "prerequisites": {}, "traits": {}, "mechanical_tags": [], "visual_or_flavor_tags": [], "build_notes": [], "confidence": 0.9, "needs_review": false, "review_reasons": [], "normalized_data": {"creature_type": "Humanoid", "size": "Medium", "speed": {"walking": 30, "flying": null, "swimming": null, "climbing": null, "burrowing": null}, "ability_score_increases": {}, "languages": ["Common"], "proficiencies": {}, "resistances": [], "damage_immunities": [], "condition_immunities": [], "senses": {"darkvision": null, "blindsight": null, "tremorsense": null, "truesight": null}, "spellcasting": {"has_lineage_spellcasting": false, "spells": [], "spellcasting_ability": null}, "features": [], "variants": []}}]\n',
            )
            self._write_file(knowledge_root / 'poisons.json', '[]\n')
            self._write_file(
                knowledge_root / 'spells' / 'components.json',
                '[{"code": "V", "name": "Verbal", "description": "", "trade_off": ""}]\n',
            )
            self._write_file(
                knowledge_root / 'spells' / 'abjuration.json',
                '[{"name": "Blade Ward", "type": "spell", "source_url": "https://example.com/spell", "source_category": "official", "summary": "", "primary_ability_scores": [], "prerequisites": {}, "traits": {}, "mechanical_tags": [], "visual_or_flavor_tags": [], "build_notes": [], "confidence": 0.9, "needs_review": false, "review_reasons": [], "normalized_data": {"spell_level": 0, "spell_level_label": "cantrip", "school": "abjuration", "source_book": "PHB", "casting_time": {"raw": "1 action", "action_type": "action", "amount": 1, "unit": "action", "reaction_trigger": null}, "range": {"raw": "Self", "type": "self", "distance": null, "unit": null}, "components": {"codes": ["V"], "verbal": true, "somatic": false, "material": false, "material_description": null, "material_consumed": null, "material_cost_gp": null}, "component_requirements": [], "duration": {"raw": "1 round", "type": "timed", "amount": 1, "unit": "round", "concentration": false}, "ritual": false, "concentration": false, "classes": ["Wizard"], "subclasses": [], "damage": [], "healing": [], "saving_throw": {}, "spell_attack": {}, "area_of_effect": {}, "targeting": {}, "conditions_inflicted": [], "conditions_removed": [], "buffs": [], "debuffs": [], "summons": [], "created_objects": [], "movement_effects": [], "utility_effects": [], "scaling": [], "resource_interactions": [], "restrictions": [], "raw_effect_text": "", "validation_notes": []}}]\n',
            )

            with self.settings(AI_BUILDER_KNOWLEDGE_DIR=str(knowledge_root)):
                call_command('load_knowledge', verbosity=0)
                call_command('load_knowledge', verbosity=0)

        self.assertEqual(KnowledgeTrait.objects.count(), 2)
        self.assertEqual(KnowledgeArmor.objects.count(), 1)
        self.assertEqual(KnowledgeWeapon.objects.count(), 1)
        self.assertEqual(KnowledgeSpellComponent.objects.count(), 1)
        self.assertEqual(KnowledgeSpell.objects.count(), 1)
        self.assertEqual(KnowledgeFeat.objects.count(), 1)
        self.assertEqual(KnowledgeSpecies.objects.count(), 1)
        self.assertEqual(KnowledgeClass.objects.count(), 1)

        self.assertEqual(KnowledgeWeapon.objects.get(
            name='Club').dnd_option, dnd_equipment)
        self.assertEqual(KnowledgeSpell.objects.get(
            name='Blade Ward').dnd_option, dnd_spell)
        self.assertEqual(KnowledgeFeat.objects.get(
            name='Actor').dnd_option, dnd_feat)
        self.assertEqual(KnowledgeSpecies.objects.get(
            name='Dragonborn').dnd_option, dnd_species)
        self.assertEqual(KnowledgeClass.objects.get(
            name='Artificer').dnd_option, dnd_class)


class KnowledgeSelectorTests(TestCase):
    def setUp(self):
        self.spell_blade_ward = KnowledgeSpell.objects.create(
            name='Blade Ward',
            source_url='https://example.com/spell/blade-ward',
            source_category='official',
            spell_level=0,
            school='abjuration',
            classes=['Wizard', 'Sorcerer'],
            traits={'damage resistance': 0.9},
            mechanical_tags=['cantrip', 'self buff'],
            needs_review=False,
        )
        KnowledgeSpell.objects.create(
            name='Hex',
            source_url='https://example.com/spell/hex',
            source_category='homebrew',
            spell_level=1,
            school='enchantment',
            classes=['Warlock'],
            traits={'debuffing': 0.8},
            mechanical_tags=['curse'],
            needs_review=False,
        )
        KnowledgeSpell.objects.create(
            name='Under Review Spell',
            source_url='https://example.com/spell/review',
            source_category='official',
            spell_level=2,
            school='evocation',
            classes=['Wizard'],
            traits={'area damage': 0.9},
            mechanical_tags=['blast'],
            needs_review=True,
        )

        KnowledgeFeat.objects.create(
            name='Alert',
            source_url='https://example.com/feat/alert',
            source_category='official',
            feat_category='general',
            traits={'initiative bonus': 1.0},
            mechanical_tags=['initiative'],
            needs_review=False,
        )

        fighter = KnowledgeClass.objects.create(
            name='Fighter',
            source_url='https://example.com/class/fighter',
            source_category='official',
            class_type=KnowledgeClass.ClassType.CLASS,
            traits={'melee': 0.8},
            mechanical_tags=['martial'],
            needs_review=False,
        )
        KnowledgeClass.objects.create(
            name='Champion',
            source_url='https://example.com/class/champion',
            source_category='official',
            class_type=KnowledgeClass.ClassType.SUBCLASS,
            parent=fighter,
            traits={'melee': 0.7},
            mechanical_tags=['critical hits'],
            needs_review=False,
        )

        KnowledgeSpecies.objects.create(
            name='Dragonborn',
            source_url='https://example.com/species/dragonborn',
            source_category='official',
            creature_type='humanoid',
            size='medium',
            traits={'dragon': 1.0},
            mechanical_tags=['damage resistance'],
            needs_review=False,
        )

        dagger = KnowledgeWeapon.objects.create(
            name='Dagger',
            weapon_category=KnowledgeWeapon.WeaponCategory.SIMPLE,
            attack_type=KnowledgeWeapon.AttackType.MELEE,
            source_category='official',
            needs_review=False,
        )
        KnowledgeWeaponProperty.objects.create(
            weapon=dagger,
            name='Thrown',
            description='Can be thrown.',
            range_raw='20/60',
        )

    def test_search_knowledge_spells_filters_by_class_and_school_and_excludes_review_rows(self):
        queryset = search_knowledge_spells(
            schools=['abjuration'],
            spell_classes=['wizard'],
            required_traits=['damage resistance'],
            source_categories=['official'],
        )
        self.assertEqual(list(queryset.values_list(
            'name', flat=True)), ['Blade Ward'])

    def test_search_knowledge_feats_filters_by_tag(self):
        queryset = search_knowledge_feats(required_tags=['initiative'])
        self.assertEqual(
            list(queryset.values_list('name', flat=True)), ['Alert'])

    def test_search_knowledge_classes_filters_subclass_parent(self):
        queryset = search_knowledge_classes(
            class_types=[KnowledgeClass.ClassType.SUBCLASS],
            parent_name='Fighter',
        )
        self.assertEqual(list(queryset.values_list(
            'name', flat=True)), ['Champion'])

    def test_search_knowledge_weapons_filters_property_name(self):
        queryset = search_knowledge_weapons(property_names=['thrown'])
        self.assertEqual(
            list(queryset.values_list('name', flat=True)), ['Dagger'])

    def test_retrieve_candidate_knowledge_applies_ruleset_source_filter(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='selector_dm', password='pw')
        campaign = Campaign.objects.create(
            name='Selector Campaign', owner=user)
        ruleset = Ruleset.objects.create(
            campaign=campaign,
            name='Official Only',
            required_character_level=1,
            starting_gold_formula='0',
            allowed_source_categories=['official'],
        )

        intent = {
            'desired_traits': ['damage resistance'],
            'mechanical_priorities': ['cantrip'],
        }
        knowledge = retrieve_candidate_knowledge(
            intent, ruleset, per_type_limit=10)

        self.assertEqual(
            [row.name for row in knowledge['spells']], ['Blade Ward'])
