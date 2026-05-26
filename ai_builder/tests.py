from django.contrib.auth import get_user_model
from django.test import TestCase

from campaigns.models import Campaign, CampaignMembership

from .forms import AICharacterPromptForm


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
        queryset = form.fields['campaign'].queryset

        self.assertIn(active_campaign, queryset)
        self.assertNotIn(ended_campaign, queryset)
