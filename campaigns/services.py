from .models import CampaignMembership


def add_or_update_membership(*, campaign, user, role):
    membership, _ = CampaignMembership.objects.update_or_create(
        campaign=campaign,
        user=user,
        defaults={'role': role},
    )
    return membership
