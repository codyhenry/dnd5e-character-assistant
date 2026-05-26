from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from rulesets.models import Ruleset


class RulesetPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='dm', password='pw')
        self.player = user_model.objects.create_user(username='player', password='pw')

        self.campaign = Campaign.objects.create(name='Campaign', owner=self.dm)
        CampaignMembership.objects.create(user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(user=self.player, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

        self.ruleset = Ruleset.objects.create(
            campaign=self.campaign,
            name='Campaign Rules',
            required_character_level=1,
            starting_gold_formula='1000',
            allowed_source_categories=['official'],
            hidden_ai_guidance='prefer defensive builds',
        )

    def test_player_cannot_edit_ruleset(self):
        self.client.login(username='player', password='pw')

        response = self.client.post(
            reverse('rulesets:edit', args=[self.ruleset.pk]),
            data={
                'name': 'Updated Rules',
                'required_character_level': 1,
                'starting_gold_formula': '1000',
                'allowed_source_categories': ['official'],
                'allow_multiclassing': True,
                'allow_feats': True,
                'hidden_ai_guidance': 'hidden',
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_hidden_ai_guidance_not_visible_to_players(self):
        self.client.login(username='player', password='pw')
        player_response = self.client.get(reverse('rulesets:detail', args=[self.ruleset.pk]))

        self.assertEqual(player_response.status_code, 200)
        self.assertNotContains(player_response, self.ruleset.hidden_ai_guidance)

        self.client.login(username='dm', password='pw')
        dm_response = self.client.get(reverse('rulesets:detail', args=[self.ruleset.pk]))
        self.assertContains(dm_response, self.ruleset.hidden_ai_guidance)
