from django.db.models import Q

from campaigns.permissions import is_campaign_dm

from .models import CharacterBuild


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
