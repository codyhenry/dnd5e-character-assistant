from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from rulesets.forms import RulesetForm
from rulesets.models import Ruleset
from rulesets.validators import validate_starting_gold_formula


class RulesetPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='dm', password='pw')
        self.player = user_model.objects.create_user(
            username='player', password='pw')

        self.campaign = Campaign.objects.create(name='Campaign', owner=self.dm)
        CampaignMembership.objects.create(
            user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=self.player, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

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
        player_response = self.client.get(
            reverse('rulesets:detail', args=[self.ruleset.pk]))

        self.assertEqual(player_response.status_code, 200)
        self.assertNotContains(
            player_response, self.ruleset.hidden_ai_guidance)

        self.client.login(username='dm', password='pw')
        dm_response = self.client.get(
            reverse('rulesets:detail', args=[self.ruleset.pk]))
        self.assertContains(dm_response, self.ruleset.hidden_ai_guidance)


class RulesetStartingGoldInputTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(
            username='formula_dm', password='pw')
        self.campaign = Campaign.objects.create(
            name='Formula Campaign', owner=self.dm)

    def _build_form(self, base: int, dice_count: int | None = None, dice_type: str = '') -> RulesetForm:
        return RulesetForm(
            data={
                'name': 'Formula Rules',
                'required_character_level': 1,
                'starting_gold_base': base,
                'starting_gold_dice_count': dice_count,
                'starting_gold_dice_type': dice_type,
                'allowed_source_categories': ['official'],
                'allow_multiclassing': True,
                'allow_feats': True,
                'hidden_ai_guidance': '',
            }
        )

    def test_accepts_structured_starting_gold_inputs(self):
        valid_cases = [
            (1000, 10, 'd6'),
            (300, 2, 'd4'),
            (900, 1, 'd12'),
            (2000, 1, 'd20'),
            (100, 1, 'd100'),
            (0, None, ''),
        ]

        for base, dice_count, dice_type in valid_cases:
            with self.subTest(base=base, dice_count=dice_count, dice_type=dice_type):
                form = self._build_form(base, dice_count, dice_type)
                self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_incomplete_structured_dice_inputs(self):
        invalid_cases = [
            (1000, 2, ''),
            (1000, None, 'd6'),
        ]

        for base, dice_count, dice_type in invalid_cases:
            with self.subTest(base=base, dice_count=dice_count, dice_type=dice_type):
                form = self._build_form(base, dice_count, dice_type)
                self.assertFalse(form.is_valid())
                self.assertIn('__all__', form.errors)


class RulesetStartingGoldFormulaValidatorTests(TestCase):
    def test_accepts_legacy_complex_formula(self):
        validate_starting_gold_formula('750 + 4d6 - 1d8')

    def test_rejects_non_standard_dice_formula(self):
        with self.assertRaises(ValidationError):
            validate_starting_gold_formula('1000 + 1d30')
