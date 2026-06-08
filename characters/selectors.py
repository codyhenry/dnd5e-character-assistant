from django.db.models import Q

from campaigns.permissions import is_campaign_dm

from .models import CharacterBuild


VALIDATION_ATTENTION_STATUSES = [
    CharacterBuild.ValidationStatus.STALE,
    CharacterBuild.ValidationStatus.INVALID,
]


def visible_builds_for_user(user):
    base_query = Q(owner=user)
    member_visible = Q(
        visibility=CharacterBuild.Visibility.CAMPAIGN_VISIBLE,
        campaign__memberships__user=user,
    )
    dm_campaigns = [
        membership.campaign_id
        for membership in user.campaign_memberships.select_related('campaign')
        if membership.role == 'DM'
    ]
    dm_visible = Q(campaign_id__in=dm_campaigns)
    return CharacterBuild.objects.filter(base_query | member_visible | dm_visible).distinct()


def campaign_builds_for_dm(user, campaign):
    if not is_campaign_dm(user, campaign):
        return CharacterBuild.objects.none()
    return CharacterBuild.objects.filter(campaign=campaign)


def builds_requiring_validation_attention(queryset):
    return queryset.filter(
        Q(needs_revalidation=True) |
        Q(validation_status__in=VALIDATION_ATTENTION_STATUSES)
    )


def build_validation_summary(queryset):
    builds = list(queryset)
    counts = {
        'total': len(builds),
        'valid': 0,
        'stale': 0,
        'invalid': 0,
        'unknown': 0,
    }

    for build in builds:
        if build.needs_revalidation or build.validation_status == CharacterBuild.ValidationStatus.STALE:
            counts['stale'] += 1
        elif build.validation_status == CharacterBuild.ValidationStatus.INVALID:
            counts['invalid'] += 1
        elif build.validation_status == CharacterBuild.ValidationStatus.VALID:
            counts['valid'] += 1
        else:
            counts['unknown'] += 1

    counts['attention_required'] = counts['stale'] + counts['invalid']
    return counts
