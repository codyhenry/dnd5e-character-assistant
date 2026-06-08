from django.contrib.auth import get_user_model
from django.test import TestCase

from campaigns.models import Campaign, CampaignMembership
from characters.models import CharacterBuild, CharacterClassLevel
from characters.validators import validate_character_build
from dnd_options.models import DNDOption
from rulesets.models import Ruleset, RulesetBannedOption


class CharacterValidationErrorCodeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='code_dm', password='pw')
        self.player = user_model.objects.create_user(username='code_player', password='pw')

        self.campaign = Campaign.objects.create(name='Code Campaign', owner=self.dm)
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
            name='Code Rules',
            required_character_level=3,
            starting_gold_formula='1000 + 1d6',
            allowed_source_categories=['official'],
            allow_multiclassing=False,
            allow_feats=False,
        )

        self.class_option = DNDOption.objects.create(
            name='Code Fighter',
            option_type=DNDOption.OptionType.CLASS,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.second_class_option = DNDOption.objects.create(
            name='Code Wizard',
            option_type=DNDOption.OptionType.CLASS,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.species_option = DNDOption.objects.create(
            name='Code Human',
            option_type=DNDOption.OptionType.SPECIES,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.feat_option = DNDOption.objects.create(
            name='Code Sharpshooter',
            option_type=DNDOption.OptionType.FEAT,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.homebrew_spell = DNDOption.objects.create(
            name='Code Custom Blast',
            option_type=DNDOption.OptionType.SPELL,
            source_category=DNDOption.SourceCategory.HOMEBREW,
        )

    def _build(self, *, character_level=None):
        build = CharacterBuild.objects.create(
            owner=self.player,
            campaign=self.campaign,
            name='Code Build',
            character_level=character_level or self.ruleset.required_character_level,
            species_option=self.species_option,
        )
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.class_option,
            level_count=build.character_level,
            ordering=1,
        )
        return build

    def _error_codes(self, build):
        result = validate_character_build(build, self.ruleset)
        self.assertFalse(result.is_valid)
        return {error['code'] for error in result.errors}

    def test_level_mismatch_reports_stable_error_code(self):
        build = self._build(character_level=2)

        self.assertIn('character_level_mismatch', self._error_codes(build))

    def test_banned_option_reports_stable_error_code(self):
        build = self._build()
        build.selected_feats.add(self.feat_option)
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset,
            banned_option=self.feat_option,
        )

        self.assertIn('contains_banned_option', self._error_codes(build))

    def test_disallowed_source_category_reports_stable_error_code(self):
        build = self._build()
        build.selected_spells.add(self.homebrew_spell)

        self.assertIn('disallowed_source_category', self._error_codes(build))

    def test_multiclassing_disabled_reports_stable_error_code(self):
        build = self._build()
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.second_class_option,
            level_count=1,
            ordering=2,
        )

        self.assertIn('multiclassing_not_allowed', self._error_codes(build))

    def test_feats_disabled_reports_stable_error_code(self):
        build = self._build()
        build.selected_feats.add(self.feat_option)

        self.assertIn('feats_not_allowed', self._error_codes(build))
