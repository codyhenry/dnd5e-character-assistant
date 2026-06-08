from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from characters.models import CharacterBuild, CharacterClassLevel
from dnd_options.models import DNDOption
from rulesets.models import Ruleset, RulesetBannedOption
from rulesets.option_forms import RulesetBannedOptionForm


class RulesetOptionRestrictionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='option_dm', password='pw')
        self.player = user_model.objects.create_user(username='option_player', password='pw')

        self.campaign = Campaign.objects.create(name='Option Campaign', owner=self.dm)
        CampaignMembership.objects.create(
            user=self.dm,
            campaign=self.campaign,
            role=CampaignMembership.Role.DM,
        )
        CampaignMembership.objects.create(
            user=self.player,
            campaign=self.campaign,
            role=CampaignMembership.Role.PLAYER,
        )

        self.ruleset = Ruleset.objects.create(
            campaign=self.campaign,
            name='Option Rules',
            required_character_level=3,
            starting_gold_formula='1000 + 1d6',
            allowed_source_categories=['official'],
        )
        self.campaign.active_ruleset = self.ruleset
        self.campaign.save(update_fields=['active_ruleset'])

        self.class_option = DNDOption.objects.create(
            name='Restriction Fighter',
            option_type=DNDOption.OptionType.CLASS,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.species_option = DNDOption.objects.create(
            name='Restriction Human',
            option_type=DNDOption.OptionType.SPECIES,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.feat_option = DNDOption.objects.create(
            name='Restriction Sharpshooter',
            option_type=DNDOption.OptionType.FEAT,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )

    def _build(self):
        build = CharacterBuild.objects.create(
            owner=self.player,
            campaign=self.campaign,
            name='Restriction Build',
            character_level=self.ruleset.required_character_level,
            species_option=self.species_option,
        )
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.class_option,
            level_count=build.character_level,
            ordering=1,
        )
        build.selected_feats.add(self.feat_option)
        return build

    def test_dm_can_add_option_restriction(self):
        build = self._build()
        self.client.login(username='option_dm', password='pw')

        response = self.client.post(
            reverse('rulesets:add_option_restriction', args=[self.ruleset.pk]),
            data={
                'banned_option': self.feat_option.pk,
                'notes': 'Too strong for this table.',
            },
        )

        self.assertEqual(response.status_code, 302)
        restriction = RulesetBannedOption.objects.get(
            ruleset=self.ruleset,
            banned_option=self.feat_option,
        )
        self.assertEqual(restriction.notes, 'Too strong for this table.')

        build.refresh_from_db()
        self.assertTrue(build.needs_revalidation)
        self.assertEqual(build.validation_status, CharacterBuild.ValidationStatus.STALE)

    def test_player_cannot_add_option_restriction(self):
        self.client.login(username='option_player', password='pw')

        response = self.client.post(
            reverse('rulesets:add_option_restriction', args=[self.ruleset.pk]),
            data={
                'banned_option': self.feat_option.pk,
                'notes': 'Player should not be allowed.',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(RulesetBannedOption.objects.filter(ruleset=self.ruleset).exists())

    def test_duplicate_option_restriction_is_rejected(self):
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset,
            banned_option=self.feat_option,
        )

        form = RulesetBannedOptionForm(
            data={'banned_option': self.feat_option.pk, 'notes': 'Duplicate'},
            ruleset=self.ruleset,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('banned_option', form.errors)

    def test_dm_can_remove_option_restriction(self):
        build = self._build()
        restriction = RulesetBannedOption.objects.create(
            ruleset=self.ruleset,
            banned_option=self.feat_option,
        )
        build.needs_revalidation = False
        build.validation_status = CharacterBuild.ValidationStatus.VALID
        build.revalidation_reason = ''
        build.save(update_fields=['needs_revalidation', 'validation_status', 'revalidation_reason'])

        self.client.login(username='option_dm', password='pw')
        response = self.client.post(
            reverse(
                'rulesets:remove_option_restriction',
                args=[self.ruleset.pk, restriction.pk],
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(RulesetBannedOption.objects.filter(pk=restriction.pk).exists())

        build.refresh_from_db()
        self.assertTrue(build.needs_revalidation)
        self.assertEqual(build.validation_status, CharacterBuild.ValidationStatus.STALE)

    def test_player_can_view_but_not_manage_option_restrictions(self):
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset,
            banned_option=self.feat_option,
            notes='Restricted option.',
        )
        self.client.login(username='option_player', password='pw')

        response = self.client.get(reverse('rulesets:detail', args=[self.ruleset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.feat_option.name)
        self.assertNotContains(response, 'Add Option Restriction')
        self.assertNotContains(response, 'Remove')
