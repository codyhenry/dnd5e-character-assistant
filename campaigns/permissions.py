from .models import Campaign, CampaignMembership


def get_campaign_membership(user, campaign: Campaign):
    if not user.is_authenticated:
        return None
    return CampaignMembership.objects.filter(user=user, campaign=campaign).first()


def is_campaign_member(user, campaign: Campaign) -> bool:
    return get_campaign_membership(user, campaign) is not None


def is_campaign_dm(user, campaign: Campaign) -> bool:
    membership = get_campaign_membership(user, campaign)
    return bool(membership and membership.role == CampaignMembership.Role.DM)


def can_edit_ruleset(user, campaign: Campaign) -> bool:
    return is_campaign_dm(user, campaign)


def can_create_npc(user, campaign: Campaign) -> bool:
    return is_campaign_dm(user, campaign)


def can_view_build(user, build) -> bool:
    if not user.is_authenticated:
        return False
    if build.owner_id == user.id:
        return True
    if is_campaign_dm(user, build.campaign):
        return True
    if build.visibility == build.Visibility.CAMPAIGN_VISIBLE and is_campaign_member(user, build.campaign):
        return True
    return False
