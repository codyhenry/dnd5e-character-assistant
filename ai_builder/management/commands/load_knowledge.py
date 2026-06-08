import ast
import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from ai_builder.models import (
    KnowledgeArmor,
    KnowledgeClass,
    KnowledgeFeat,
    KnowledgeSpecies,
    KnowledgeSpeciesFeature,
    KnowledgeSpeciesVariant,
    KnowledgeSpell,
    KnowledgeSpellComponent,
    KnowledgeTrait,
    KnowledgeWeapon,
    KnowledgeWeaponProperty,
)
from dnd_options.models import DNDOption


KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / 'knowledge'


class Command(BaseCommand):
    help = 'Load ai_builder/knowledge JSON data into database tables and link to DNDOption records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all knowledge tables before import.',
        )

    def handle(self, *args, **options):
        configured_dir = getattr(settings, 'AI_BUILDER_KNOWLEDGE_DIR', None)
        knowledge_dir = Path(
            configured_dir) if configured_dir else KNOWLEDGE_DIR
        if not knowledge_dir.exists():
            self.stderr.write(self.style.ERROR(
                f'Knowledge directory not found: {knowledge_dir}'))
            return

        with transaction.atomic():
            if options['clear']:
                self._clear_tables()

            summary = {
                'traits': self._load_traits(knowledge_dir / 'allowed_traits.py'),
                'armor': self._load_armor(knowledge_dir / 'armor.json'),
                'weapons': self._load_weapons(knowledge_dir / 'weapons.json'),
                'spell_components': self._load_spell_components(knowledge_dir / 'spells' / 'components.json'),
                'spells': self._load_spells(knowledge_dir / 'spells'),
                'feats': self._load_feats(knowledge_dir / 'feats.json'),
                'species': self._load_species(knowledge_dir / 'lineages.json'),
                'classes': self._load_classes(knowledge_dir / 'classes.json'),
            }

        rendered = ', '.join(f'{key}={value}' for key,
                             value in summary.items())
        self.stdout.write(self.style.SUCCESS(
            f'Knowledge import complete: {rendered}'))

    def _clear_tables(self) -> None:
        KnowledgeSpeciesFeature.objects.all().delete()
        KnowledgeSpeciesVariant.objects.all().delete()
        KnowledgeWeaponProperty.objects.all().delete()
        KnowledgeArmor.objects.all().delete()
        KnowledgeWeapon.objects.all().delete()
        KnowledgeSpellComponent.objects.all().delete()
        KnowledgeSpell.objects.all().delete()
        KnowledgeFeat.objects.all().delete()
        KnowledgeSpecies.objects.all().delete()
        KnowledgeClass.objects.all().delete()
        KnowledgeTrait.objects.all().delete()

    def _load_json(self, file_path: Path, *, default: Any) -> Any:
        if not file_path.exists():
            return default
        with file_path.open('r', encoding='utf-8') as file_handle:
            return json.load(file_handle)

    def _load_traits(self, file_path: Path) -> int:
        if not file_path.exists():
            return 0

        module = ast.parse(file_path.read_text(encoding='utf-8'))
        trait_values: list[str] = []
        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'ALLOWED_TRAITS':
                    trait_values = ast.literal_eval(node.value)
                    break

        for trait_name in trait_values:
            KnowledgeTrait.objects.update_or_create(
                name=str(trait_name).strip(),
                defaults={'category': ''},
            )
        return len(trait_values)

    def _build_shared_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            'source_url': payload.get('source_url', '') or '',
            'source_category': payload.get('source_category', '') or '',
            'summary': payload.get('summary', '') or '',
            'primary_ability_scores': payload.get('primary_ability_scores') or [],
            'prerequisites': payload.get('prerequisites') or {},
            'traits': payload.get('traits') or {},
            'mechanical_tags': payload.get('mechanical_tags') or [],
            'visual_or_flavor_tags': payload.get('visual_or_flavor_tags') or [],
            'build_notes': payload.get('build_notes') or [],
            'confidence': float(payload.get('confidence', 0.0) or 0.0),
            'needs_review': bool(payload.get('needs_review', False)),
            'review_reasons': payload.get('review_reasons') or [],
        }

    def _find_dnd_option(
        self,
        *,
        name: str,
        option_type: str,
        source_url: str,
        source_category: str,
    ) -> DNDOption | None:
        queryset = DNDOption.objects.filter(
            name=name, option_type=option_type).order_by('id')
        if not queryset.exists():
            return None

        if source_url:
            by_url = queryset.filter(source_url__iexact=source_url).first()
            if by_url:
                return by_url

        if source_category:
            by_source = queryset.filter(
                source_category=source_category).first()
            if by_source:
                return by_source

        return queryset.first()

    def _load_armor(self, file_path: Path) -> int:
        raw = self._load_json(file_path, default={})
        if not isinstance(raw, dict):
            return 0

        armor_data = raw.get('armor') or {}
        if not isinstance(armor_data, dict):
            return 0
        count = 0

        for category, entries in armor_data.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get('name', '')).strip()
                if not name:
                    continue

                dnd_option = self._find_dnd_option(
                    name=name,
                    option_type=DNDOption.OptionType.EQUIPMENT,
                    source_url='',
                    source_category=DNDOption.SourceCategory.OFFICIAL,
                )
                KnowledgeArmor.objects.update_or_create(
                    name=name,
                    armor_category=category,
                    defaults={
                        'armor_class_formula': entry.get('armor_class', '') or '',
                        'strength_requirement': entry.get('strength', '') or '',
                        'stealth_disadvantage': (entry.get('stealth') or '').lower() == 'disadvantage',
                        'weight': entry.get('weight', '') or '',
                        'cost': entry.get('cost', '') or '',
                        'dnd_option': dnd_option,
                        'source_category': DNDOption.SourceCategory.OFFICIAL,
                    },
                )
                count += 1
        return count

    def _load_weapons(self, file_path: Path) -> int:
        raw = self._load_json(file_path, default={})
        count = 0

        for weapon_category, by_attack_type in raw.items():
            if not isinstance(by_attack_type, dict):
                continue
            for attack_type, entries in by_attack_type.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get('name', '')).strip()
                    if not name:
                        continue

                    dnd_option = self._find_dnd_option(
                        name=name,
                        option_type=DNDOption.OptionType.EQUIPMENT,
                        source_url='',
                        source_category=DNDOption.SourceCategory.OFFICIAL,
                    )
                    weapon, _ = KnowledgeWeapon.objects.update_or_create(
                        name=name,
                        weapon_category=weapon_category,
                        attack_type=attack_type,
                        defaults={
                            'cost': entry.get('cost', '') or '',
                            'damage': entry.get('damage', '') or '',
                            'weight': entry.get('weight', '') or '',
                            'dnd_option': dnd_option,
                            'source_category': DNDOption.SourceCategory.OFFICIAL,
                        },
                    )

                    weapon.properties.all().delete()
                    for property_payload in entry.get('properties', []):
                        if not isinstance(property_payload, dict):
                            continue
                        property_name = str(
                            property_payload.get('name', '')).strip()
                        if not property_name:
                            continue
                        KnowledgeWeaponProperty.objects.create(
                            weapon=weapon,
                            name=property_name,
                            description=property_payload.get(
                                'description', '') or '',
                            range_raw=property_payload.get('range', '') or '',
                        )
                    count += 1
        return count

    def _load_spell_components(self, file_path: Path) -> int:
        entries = self._load_json(file_path, default=[])
        count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get('code', '')).strip()
            if not code:
                continue
            KnowledgeSpellComponent.objects.update_or_create(
                code=code,
                defaults={
                    'name': entry.get('name', '') or '',
                    'description': entry.get('description', '') or '',
                    'trade_off': entry.get('trade_off', '') or '',
                },
            )
            count += 1
        return count

    def _load_spells(self, spells_dir: Path) -> int:
        count = 0
        if not spells_dir.exists():
            return count

        for json_file in sorted(spells_dir.glob('*.json')):
            if json_file.name == 'components.json':
                continue
            entries = self._load_json(json_file, default=[])
            for payload in entries:
                if not isinstance(payload, dict):
                    continue
                name = str(payload.get('name', '')).strip()
                if not name:
                    continue

                normalized = payload.get('normalized_data') or {}
                components = normalized.get('components') or {}
                casting_time = normalized.get('casting_time') or {}
                range_data = normalized.get('range') or {}
                duration = normalized.get('duration') or {}

                source_url = payload.get('source_url', '') or ''
                source_category = payload.get('source_category', '') or ''
                dnd_option = self._find_dnd_option(
                    name=name,
                    option_type=DNDOption.OptionType.SPELL,
                    source_url=source_url,
                    source_category=source_category,
                )

                defaults = self._build_shared_defaults(payload)
                defaults.update(
                    {
                        'spell_level': normalized.get('spell_level') or 0,
                        'spell_level_label': normalized.get('spell_level_label', '') or '',
                        'school': normalized.get('school', '') or '',
                        'source_book': normalized.get('source_book', '') or '',
                        'casting_time_raw': casting_time.get('raw', '') or '',
                        'casting_time_action_type': casting_time.get('action_type', '') or '',
                        'casting_time_amount': casting_time.get('amount'),
                        'casting_time_unit': casting_time.get('unit', '') or '',
                        'casting_time_reaction_trigger': casting_time.get('reaction_trigger', '') or '',
                        'range_raw': range_data.get('raw', '') or '',
                        'range_type': range_data.get('type', '') or '',
                        'range_distance': range_data.get('distance'),
                        'range_unit': range_data.get('unit', '') or '',
                        'verbal': bool(components.get('verbal', False)),
                        'somatic': bool(components.get('somatic', False)),
                        'material': bool(components.get('material', False)),
                        'material_description': components.get('material_description', '') or '',
                        'material_consumed': bool(components.get('material_consumed', False)),
                        'material_cost_gp': components.get('material_cost_gp'),
                        'component_requirements': normalized.get('component_requirements') or [],
                        'duration_raw': duration.get('raw', '') or '',
                        'duration_type': duration.get('type', '') or '',
                        'duration_amount': duration.get('amount'),
                        'duration_unit': duration.get('unit', '') or '',
                        'concentration': bool(normalized.get('concentration', False)),
                        'ritual': bool(normalized.get('ritual', False)),
                        'classes': normalized.get('classes') or [],
                        'subclasses': normalized.get('subclasses') or [],
                        'damage': normalized.get('damage') or [],
                        'healing': normalized.get('healing') or [],
                        'saving_throw': normalized.get('saving_throw') or {},
                        'spell_attack': normalized.get('spell_attack') or {},
                        'area_of_effect': normalized.get('area_of_effect') or {},
                        'targeting': normalized.get('targeting') or {},
                        'conditions_inflicted': normalized.get('conditions_inflicted') or [],
                        'conditions_removed': normalized.get('conditions_removed') or [],
                        'buffs': normalized.get('buffs') or [],
                        'debuffs': normalized.get('debuffs') or [],
                        'summons': normalized.get('summons') or [],
                        'created_objects': normalized.get('created_objects') or [],
                        'movement_effects': normalized.get('movement_effects') or [],
                        'utility_effects': normalized.get('utility_effects') or [],
                        'scaling': normalized.get('scaling') or [],
                        'resource_interactions': normalized.get('resource_interactions') or [],
                        'restrictions': normalized.get('restrictions') or [],
                        'raw_effect_text': normalized.get('raw_effect_text', '') or '',
                        'validation_notes': normalized.get('validation_notes') or [],
                        'dnd_option': dnd_option,
                    }
                )

                KnowledgeSpell.objects.update_or_create(
                    name=name,
                    source_url=source_url,
                    defaults=defaults,
                )
                count += 1
        return count

    def _load_feats(self, file_path: Path) -> int:
        entries = self._load_json(file_path, default=[])
        count = 0

        for payload in entries:
            if not isinstance(payload, dict):
                continue
            name = str(payload.get('name', '')).strip()
            if not name:
                continue

            normalized = payload.get('normalized_data') or {}
            source_url = payload.get('source_url', '') or ''
            source_category = payload.get('source_category', '') or ''
            dnd_option = self._find_dnd_option(
                name=name,
                option_type=DNDOption.OptionType.FEAT,
                source_url=source_url,
                source_category=source_category,
            )

            defaults = self._build_shared_defaults(payload)
            defaults.update(
                {
                    'feat_category': normalized.get('feat_category', '') or '',
                    'ability_score_increases': normalized.get('ability_score_increases') or [],
                    'granted_spells': normalized.get('granted_spells') or [],
                    'granted_cantrips': normalized.get('granted_cantrips') or [],
                    'granted_proficiencies': normalized.get('granted_proficiencies') or {},
                    'granted_features': normalized.get('granted_features') or [],
                    'limited_use_features': normalized.get('limited_use_features') or [],
                    'optional_rules': normalized.get('optional_rules') or [],
                    'choice_points': normalized.get('choice_points') or [],
                    'dnd_option': dnd_option,
                }
            )
            KnowledgeFeat.objects.update_or_create(
                name=name,
                source_url=source_url,
                defaults=defaults,
            )
            count += 1
        return count

    def _load_species(self, file_path: Path) -> int:
        entries = self._load_json(file_path, default=[])
        count = 0

        for payload in entries:
            if not isinstance(payload, dict):
                continue
            name = str(payload.get('name', '')).strip()
            if not name:
                continue

            normalized = payload.get('normalized_data') or {}
            speed = normalized.get('speed') or {}
            senses = normalized.get('senses') or {}
            spellcasting = normalized.get('spellcasting') or {}

            source_url = payload.get('source_url', '') or ''
            source_category = payload.get('source_category', '') or ''
            dnd_option = self._find_dnd_option(
                name=name,
                option_type=DNDOption.OptionType.SPECIES,
                source_url=source_url,
                source_category=source_category,
            )

            defaults = self._build_shared_defaults(payload)
            defaults.update(
                {
                    'creature_type': normalized.get('creature_type', '') or '',
                    'size': normalized.get('size', '') or '',
                    'speed_walking': speed.get('walking'),
                    'speed_flying': speed.get('flying'),
                    'speed_swimming': speed.get('swimming'),
                    'speed_climbing': speed.get('climbing'),
                    'speed_burrowing': speed.get('burrowing'),
                    'darkvision': senses.get('darkvision'),
                    'blindsight': senses.get('blindsight'),
                    'tremorsense': senses.get('tremorsense'),
                    'truesight': senses.get('truesight'),
                    'ability_score_increases': normalized.get('ability_score_increases') or {},
                    'languages': normalized.get('languages') or [],
                    'proficiencies': normalized.get('proficiencies') or {},
                    'resistances': normalized.get('resistances') or [],
                    'damage_immunities': normalized.get('damage_immunities') or [],
                    'condition_immunities': normalized.get('condition_immunities') or [],
                    'has_lineage_spellcasting': bool(spellcasting.get('has_lineage_spellcasting', False)),
                    'lineage_spells': spellcasting.get('spells') or [],
                    'spellcasting_ability': spellcasting.get('spellcasting_ability', '') or '',
                    'dnd_option': dnd_option,
                }
            )
            species, _ = KnowledgeSpecies.objects.update_or_create(
                name=name,
                source_url=source_url,
                defaults=defaults,
            )

            species.features.all().delete()
            for feature in normalized.get('features') or []:
                if not isinstance(feature, dict):
                    continue
                feature_name = str(feature.get('name', '')).strip()
                if not feature_name:
                    continue
                KnowledgeSpeciesFeature.objects.create(
                    species=species,
                    name=feature_name,
                    description=feature.get('description', '') or '',
                    action_type=feature.get('action_type', '') or '',
                    uses=feature.get('uses', '') or '',
                    recovery=feature.get('recovery', '') or '',
                    scales_with_level=bool(
                        feature.get('scales_with_level', False)),
                    traits=feature.get('traits') or {},
                    raw_text=feature.get('raw_text', '') or '',
                )

            species.variants.all().delete()
            for variant in normalized.get('variants') or []:
                if not isinstance(variant, dict):
                    continue
                variant_name = str(variant.get('name', '')).strip()
                if not variant_name:
                    continue
                KnowledgeSpeciesVariant.objects.create(
                    species=species,
                    name=variant_name,
                    description=variant.get('description', '') or '',
                    traits=variant.get('traits') or {},
                )

            count += 1
        return count

    def _load_classes(self, file_path: Path) -> int:
        entries = self._load_json(file_path, default=[])
        count = 0
        classes_by_name: dict[str, KnowledgeClass] = {}
        pending_subclasses: list[tuple[KnowledgeClass, str]] = []

        for payload in entries:
            if not isinstance(payload, dict):
                continue
            name = str(payload.get('name', '')).strip()
            if not name:
                continue

            class_type = str(payload.get('type', '')).strip().lower()
            if class_type not in {KnowledgeClass.ClassType.CLASS, KnowledgeClass.ClassType.SUBCLASS}:
                continue

            source_url = payload.get('source_url', '') or ''
            source_category = payload.get('source_category', '') or ''
            option_type = (
                DNDOption.OptionType.CLASS
                if class_type == KnowledgeClass.ClassType.CLASS
                else DNDOption.OptionType.SUBCLASS
            )
            dnd_option = self._find_dnd_option(
                name=name,
                option_type=option_type,
                source_url=source_url,
                source_category=source_category,
            )

            defaults = self._build_shared_defaults(payload)
            defaults.update({'class_type': class_type,
                            'dnd_option': dnd_option})
            knowledge_class, _ = KnowledgeClass.objects.update_or_create(
                name=name,
                class_type=class_type,
                source_url=source_url,
                defaults=defaults,
            )

            if class_type == KnowledgeClass.ClassType.CLASS:
                classes_by_name[name] = knowledge_class
            else:
                parent_name = str(payload.get('parent', '')).strip()
                if parent_name:
                    pending_subclasses.append((knowledge_class, parent_name))

            count += 1

        for subclass, parent_name in pending_subclasses:
            parent = classes_by_name.get(parent_name)
            if parent:
                subclass.parent = parent
                subclass.save(update_fields=['parent', 'updated_at'])

        return count
