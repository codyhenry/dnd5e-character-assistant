from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from characters.models import CharacterBuild, CharacterClassLevel
from characters.validators import validate_character_build
from dnd_options.models import DNDOption
from rulesets.models import Ruleset, RulesetBannedOption


class CharacterPermissionsAndValidationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='dm', password='pw')
        self.player_one = user_model.objects.create_user(username='player1', password='pw')
        self.player_two = user_model.objects.create_user(username='player2', password='pw')

        self.campaign = Campaign.objects.create(name='Test Campaign', description='desc', owner=self.dm)
        CampaignMembership.objects.create(user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(user=self.player_one, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)
        CampaignMembership.objects.create(user=self.player_two, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

        self.ruleset = Ruleset.objects.create(
            campaign=self.campaign,
            name='Core Rules',
            required_character_level=3,
            starting_gold_formula='1000 + 1d6',
            allowed_source_categories=['official'],
            allow_multiclassing=False,
            allow_feats=False,
            hidden_ai_guidance='no flying builds',
        )
        self.campaign.active_ruleset = self.ruleset
        self.campaign.save(update_fields=['active_ruleset'])

        self.class_option = DNDOption.objects.create(
            name='Fighter', option_type=DNDOption.OptionType.CLASS, source_category=DNDOption.SourceCategory.OFFICIAL
        )
        self.second_class_option = DNDOption.objects.create(
            name='Wizard', option_type=DNDOption.OptionType.CLASS, source_category=DNDOption.SourceCategory.OFFICIAL
        )
        self.species_option = DNDOption.objects.create(
            name='Human', option_type=DNDOption.OptionType.SPECIES, source_category=DNDOption.SourceCategory.OFFICIAL
        )
        self.banned_feat = DNDOption.objects.create(
            name='Sharpshooter', option_type=DNDOption.OptionType.FEAT, source_category=DNDOption.SourceCategory.OFFICIAL
        )
        self.homebrew_spell = DNDOption.objects.create(
            name='Custom Blast', option_type=DNDOption.OptionType.SPELL, source_category=DNDOption.SourceCategory.HOMEBREW
        )

    def _create_player_build(self, owner=None, **kwargs):
        owner = owner or self.player_one
        build = CharacterBuild.objects.create(
            owner=owner,
            campaign=self.campaign,
            name=kwargs.pop('name', 'Player Build'),
            build_type=kwargs.pop('build_type', CharacterBuild.BuildType.PLAYER_CHARACTER),
            visibility=kwargs.pop('visibility', CharacterBuild.Visibility.PRIVATE),
            character_level=kwargs.pop('character_level', self.ruleset.required_character_level),
            species_option=kwargs.pop('species_option', self.species_option),
            **kwargs,
        )
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.class_option,
            level_count=build.character_level,
            ordering=1,
        )
        return build

    def test_player_cannot_view_another_players_private_build(self):
        private_build = self._create_player_build(owner=self.player_one)

        self.client.login(username='player2', password='pw')
        response = self.client.get(reverse('characters:detail', args=[private_build.pk]))

        self.assertEqual(response.status_code, 403)

    def test_dm_can_view_all_builds_in_campaign(self):
        private_build = self._create_player_build(owner=self.player_one)

        self.client.login(username='dm', password='pw')
        detail_response = self.client.get(reverse('characters:detail', args=[private_build.pk]))
        list_response = self.client.get(reverse('characters:dm_all_builds', args=[self.campaign.pk]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, private_build.name)

    def test_player_build_fails_validation_when_level_mismatch(self):
        build = self._create_player_build(character_level=2)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self.assertIn('Character level must match the ruleset required level.', result.errors)

    def test_player_build_fails_validation_for_banned_option(self):
        build = self._create_player_build()
        build.selected_feats.add(self.banned_feat)
        RulesetBannedOption.objects.create(ruleset=self.ruleset, banned_option=self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self.assertIn('Character build includes one or more banned options.', result.errors)

    def test_player_build_fails_validation_for_disallowed_source_category(self):
        build = self._create_player_build()
        build.selected_spells.add(self.homebrew_spell)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self.assertIn('Character build includes options from disallowed source categories.', result.errors)

    def test_player_build_fails_validation_when_multiclassing_disallowed(self):
        build = self._create_player_build()
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.second_class_option,
            level_count=1,
            ordering=2,
        )

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self.assertIn('Multiclassing is not allowed by this ruleset.', result.errors)

    def test_player_build_fails_validation_when_feats_disabled(self):
        build = self._create_player_build()
        build.selected_feats.add(self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self.assertIn('Feats are not allowed by this ruleset.', result.errors)

    def test_npc_build_bypasses_player_ruleset_validation(self):
        build = self._create_player_build(
            name='NPC Build',
            build_type=CharacterBuild.BuildType.NPC,
            character_level=99,
        )
        build.selected_feats.add(self.banned_feat)
        RulesetBannedOption.objects.create(ruleset=self.ruleset, banned_option=self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
