from __future__ import annotations

from typing import Iterable

from django.db.models import QuerySet

from .models import (
    KnowledgeClass,
    KnowledgeFeat,
    KnowledgeSpecies,
    KnowledgeSpell,
    KnowledgeWeapon,
)


def _normalize_str_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _normalize_source_categories(source_categories: Iterable[str] | None) -> list[str]:
    return [category.strip() for category in source_categories or [] if str(category).strip()]


def _match_traits(traits_map: dict, required_traits: list[str], min_weight: float) -> bool:
    if not required_traits:
        return True
    for trait in required_traits:
        raw = traits_map.get(trait)
        if isinstance(raw, (int, float)) and float(raw) >= min_weight:
            return True
    return False


def _match_tags(record_tags: list, required_tags: list[str]) -> bool:
    if not required_tags:
        return True
    normalized_tags = {str(tag).strip().lower()
                       for tag in record_tags if str(tag).strip()}
    return bool(normalized_tags.intersection(required_tags))


def _apply_common_knowledge_filters(
    queryset: QuerySet,
    *,
    source_categories: Iterable[str] | None,
    name_query: str | None,
    include_needs_review: bool,
) -> QuerySet:
    if not include_needs_review:
        queryset = queryset.filter(needs_review=False)

    allowed_categories = _normalize_source_categories(source_categories)
    if allowed_categories:
        queryset = queryset.filter(source_category__in=allowed_categories)

    if name_query:
        queryset = queryset.filter(name__icontains=name_query.strip())

    return queryset


def search_knowledge_spells(
    *,
    levels: Iterable[int] | None = None,
    schools: Iterable[str] | None = None,
    spell_classes: Iterable[str] | None = None,
    required_traits: Iterable[str] | None = None,
    required_tags: Iterable[str] | None = None,
    source_categories: Iterable[str] | None = None,
    name_query: str | None = None,
    ritual: bool | None = None,
    concentration: bool | None = None,
    include_needs_review: bool = False,
    min_trait_weight: float = 0.4,
) -> QuerySet[KnowledgeSpell]:
    queryset = _apply_common_knowledge_filters(
        KnowledgeSpell.objects.all(),
        source_categories=source_categories,
        name_query=name_query,
        include_needs_review=include_needs_review,
    )

    if levels:
        queryset = queryset.filter(spell_level__in=list(levels))

    schools_list = _normalize_str_list(schools)
    if schools_list:
        queryset = queryset.filter(school__in=schools_list)

    if ritual is not None:
        queryset = queryset.filter(ritual=ritual)

    if concentration is not None:
        queryset = queryset.filter(concentration=concentration)

    required_classes = set(_normalize_str_list(spell_classes))
    required_traits_list = _normalize_str_list(required_traits)
    required_tags_list = _normalize_str_list(required_tags)

    if not (required_classes or required_traits_list or required_tags_list):
        return queryset.order_by('name')

    matched_ids = []
    for spell in queryset:
        class_ok = True
        if required_classes:
            spell_classes_normalized = {
                str(class_name).strip().lower() for class_name in spell.classes if str(class_name).strip()
            }
            class_ok = bool(
                spell_classes_normalized.intersection(required_classes))

        if not class_ok:
            continue

        if not _match_traits(spell.traits or {}, required_traits_list, min_trait_weight):
            continue

        if not _match_tags(spell.mechanical_tags or [], required_tags_list):
            continue

        matched_ids.append(spell.id)

    return queryset.filter(id__in=matched_ids).order_by('name')


def search_knowledge_feats(
    *,
    feat_categories: Iterable[str] | None = None,
    required_traits: Iterable[str] | None = None,
    required_tags: Iterable[str] | None = None,
    source_categories: Iterable[str] | None = None,
    name_query: str | None = None,
    include_needs_review: bool = False,
    min_trait_weight: float = 0.4,
) -> QuerySet[KnowledgeFeat]:
    queryset = _apply_common_knowledge_filters(
        KnowledgeFeat.objects.all(),
        source_categories=source_categories,
        name_query=name_query,
        include_needs_review=include_needs_review,
    )

    categories = _normalize_str_list(feat_categories)
    if categories:
        queryset = queryset.filter(feat_category__in=categories)

    required_traits_list = _normalize_str_list(required_traits)
    required_tags_list = _normalize_str_list(required_tags)
    if not (required_traits_list or required_tags_list):
        return queryset.order_by('name')

    matched_ids = []
    for feat in queryset:
        if not _match_traits(feat.traits or {}, required_traits_list, min_trait_weight):
            continue
        if not _match_tags(feat.mechanical_tags or [], required_tags_list):
            continue
        matched_ids.append(feat.id)

    return queryset.filter(id__in=matched_ids).order_by('name')


def search_knowledge_species(
    *,
    creature_types: Iterable[str] | None = None,
    sizes: Iterable[str] | None = None,
    required_traits: Iterable[str] | None = None,
    required_tags: Iterable[str] | None = None,
    source_categories: Iterable[str] | None = None,
    name_query: str | None = None,
    include_needs_review: bool = False,
    min_trait_weight: float = 0.4,
) -> QuerySet[KnowledgeSpecies]:
    queryset = _apply_common_knowledge_filters(
        KnowledgeSpecies.objects.all(),
        source_categories=source_categories,
        name_query=name_query,
        include_needs_review=include_needs_review,
    )

    normalized_creature_types = _normalize_str_list(creature_types)
    if normalized_creature_types:
        queryset = queryset.filter(creature_type__in=normalized_creature_types)

    normalized_sizes = _normalize_str_list(sizes)
    if normalized_sizes:
        queryset = queryset.filter(size__in=normalized_sizes)

    required_traits_list = _normalize_str_list(required_traits)
    required_tags_list = _normalize_str_list(required_tags)

    if not (required_traits_list or required_tags_list):
        return queryset.order_by('name')

    matched_ids = []
    for species in queryset:
        if not _match_traits(species.traits or {}, required_traits_list, min_trait_weight):
            continue
        if not _match_tags(species.mechanical_tags or [], required_tags_list):
            continue
        matched_ids.append(species.id)

    return queryset.filter(id__in=matched_ids).order_by('name')


def search_knowledge_classes(
    *,
    class_types: Iterable[str] | None = None,
    parent_name: str | None = None,
    required_traits: Iterable[str] | None = None,
    required_tags: Iterable[str] | None = None,
    source_categories: Iterable[str] | None = None,
    name_query: str | None = None,
    include_needs_review: bool = False,
    min_trait_weight: float = 0.4,
) -> QuerySet[KnowledgeClass]:
    queryset = _apply_common_knowledge_filters(
        KnowledgeClass.objects.all(),
        source_categories=source_categories,
        name_query=name_query,
        include_needs_review=include_needs_review,
    )

    normalized_class_types = _normalize_str_list(class_types)
    if normalized_class_types:
        queryset = queryset.filter(class_type__in=normalized_class_types)

    if parent_name:
        queryset = queryset.filter(parent__name__iexact=parent_name.strip())

    required_traits_list = _normalize_str_list(required_traits)
    required_tags_list = _normalize_str_list(required_tags)

    if not (required_traits_list or required_tags_list):
        return queryset.order_by('name')

    matched_ids = []
    for class_row in queryset:
        if not _match_traits(class_row.traits or {}, required_traits_list, min_trait_weight):
            continue
        if not _match_tags(class_row.mechanical_tags or [], required_tags_list):
            continue
        matched_ids.append(class_row.id)

    return queryset.filter(id__in=matched_ids).order_by('name')


def search_knowledge_weapons(
    *,
    weapon_categories: Iterable[str] | None = None,
    attack_types: Iterable[str] | None = None,
    property_names: Iterable[str] | None = None,
    source_categories: Iterable[str] | None = None,
    name_query: str | None = None,
    include_needs_review: bool = False,
) -> QuerySet[KnowledgeWeapon]:
    queryset = _apply_common_knowledge_filters(
        KnowledgeWeapon.objects.all(),
        source_categories=source_categories,
        name_query=name_query,
        include_needs_review=include_needs_review,
    )

    normalized_weapon_categories = _normalize_str_list(weapon_categories)
    if normalized_weapon_categories:
        queryset = queryset.filter(
            weapon_category__in=normalized_weapon_categories)

    normalized_attack_types = _normalize_str_list(attack_types)
    if normalized_attack_types:
        queryset = queryset.filter(attack_type__in=normalized_attack_types)

    normalized_property_names = _normalize_str_list(property_names)
    if normalized_property_names:
        queryset = queryset.filter(
            properties__name__in=[prop_name.title()
                                  for prop_name in normalized_property_names]
        ).distinct()

    return queryset.order_by('name')
