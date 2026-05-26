from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from rulesets.models import Ruleset

from .models import Campaign, CampaignMembership


class CampaignFormBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dm1', password='Pass12345!')
        self.client.force_login(self.user)

    def test_create_form_does_not_include_active_ruleset(self):
        response = self.client.get(reverse('campaigns:create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('active_ruleset', response.context['form'].fields)

    def test_update_form_limits_active_ruleset_to_campaign_rulesets(self):
        campaign = Campaign.objects.create(
            name='Alpha', description='', owner=self.user)
        CampaignMembership.objects.create(
            user=self.user,
            campaign=campaign,
            role=CampaignMembership.Role.DM,
        )
        own_ruleset = Ruleset.objects.create(
            campaign=campaign, name='Alpha Rules')

        other_campaign = Campaign.objects.create(
            name='Beta', description='', owner=self.user)
        other_ruleset = Ruleset.objects.create(
            campaign=other_campaign, name='Beta Rules')

        response = self.client.get(
            reverse('campaigns:edit', args=[campaign.pk]))

        self.assertEqual(response.status_code, 200)
        queryset = response.context['form'].fields['active_ruleset'].queryset
        self.assertIn(own_ruleset, queryset)
        self.assertNotIn(other_ruleset, queryset)

    def test_update_rejects_active_ruleset_from_other_campaign(self):
        campaign = Campaign.objects.create(
            name='Alpha', description='', owner=self.user)
        CampaignMembership.objects.create(
            user=self.user,
            campaign=campaign,
            role=CampaignMembership.Role.DM,
        )

        other_campaign = Campaign.objects.create(
            name='Beta', description='', owner=self.user)
        other_ruleset = Ruleset.objects.create(
            campaign=other_campaign, name='Beta Rules')

        response = self.client.post(
            reverse('campaigns:edit', args=[campaign.pk]),
            {
                'name': 'Alpha Updated',
                'description': 'Updated description',
                'status': Campaign.Status.ACTIVE,
                'active_ruleset': other_ruleset.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('active_ruleset', response.context['form'].errors)
        self.assertIn('Select a valid choice. That choice is not one of the available choices.',
                      response.context['form'].errors['active_ruleset'])
        campaign.refresh_from_db()
        self.assertIsNone(campaign.active_ruleset)
