from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CharacterBuild, CharacterClassLevel
from .selectors import (
    build_validation_summary,
    builds_requiring_validation_attention,
)
from .services import require_valid_build_for_reuse, revalidate_character_build
from .validators import validate_character_build

from campaigns.models import Campaign, CampaignMembership
from dnd_options.models import DNDOption
from dnd_options.review_services import (
    apply_suggested_change,
    approve_suggested_change,
    create_review_for_option,
    propose_option_change,
)
from rulesets.models import Ruleset, RulesetBannedOption


class CharacterPermissionsAndValidationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='dm', password='pw')
        self.player_one = user_model.objects.create_user(
            username='player1', password='pw')
        self.player_two = user_model.objects.create_user(
            username='player2', password='pw')

        self.campaign = Campaign.objects.create(
            name='Test Campaign', description='desc', owner=self.dm)
        CampaignMembership.objects.create(
            user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=self.player_one, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)
        CampaignMembership.objects.create(
            user=self.player_two, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

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

    def _assert_error_message(self, errors, message):
        self.assertIn(message, [error.get('message') for error in errors])

    def _create_player_build(self, owner=None, **kwargs):
        owner = owner or self.player_one
        build = CharacterBuild.objects.create(
            owner=owner,
            campaign=self.campaign,
            name=kwargs.pop('name', 'Player Build'),
            build_type=kwargs.pop(
                'build_type', CharacterBuild.BuildType.PLAYER_CHARACTER),
            visibility=kwargs.pop(
                'visibility', CharacterBuild.Visibility.PRIVATE),
            character_level=kwargs.pop(
                'character_level', self.ruleset.required_character_level),
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
        response = self.client.get(
            reverse('characters:detail', args=[private_build.pk]))

        self.assertEqual(response.status_code, 403)

    def test_dm_can_view_all_builds_in_campaign(self):
        private_build = self._create_player_build(owner=self.player_one)

        self.client.login(username='dm', password='pw')
        detail_response = self.client.get(
            reverse('characters:detail', args=[private_build.pk]))
        list_response = self.client.get(
            reverse('characters:dm_all_builds', args=[self.campaign.pk]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, private_build.name)

    def test_player_build_fails_validation_when_level_mismatch(self):
        build = self._create_player_build(character_level=2)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self._assert_error_message(
            result.errors,
            'Character level must match the ruleset required level.',
        )

    def test_player_build_fails_validation_for_banned_option(self):
        build = self._create_player_build()
        build.selected_feats.add(self.banned_feat)
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset, banned_option=self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self._assert_error_message(
            result.errors,
            'Character build includes one or more banned options.',
        )

    def test_player_build_fails_validation_for_disallowed_source_category(self):
        build = self._create_player_build()
        build.selected_spells.add(self.homebrew_spell)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self._assert_error_message(
            result.errors,
            'Character build includes options from disallowed source categories.',
        )

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
        self._assert_error_message(
            result.errors,
            'Multiclassing is not allowed by this ruleset.',
        )

    def test_player_build_fails_validation_when_feats_disabled(self):
        build = self._create_player_build()
        build.selected_feats.add(self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertFalse(result.is_valid)
        self._assert_error_message(
            result.errors, 'Feats are not allowed by this ruleset.')

    def test_npc_build_bypasses_player_ruleset_validation(self):
        build = self._create_player_build(
            name='NPC Build',
            build_type=CharacterBuild.BuildType.NPC,
            character_level=99,
        )
        build.selected_feats.add(self.banned_feat)
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset, banned_option=self.banned_feat)

        result = validate_character_build(build, self.ruleset)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])


class CampaignDropdownFilteringTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='builder', password='pw')

        self.active_campaign = Campaign.objects.create(
            name='Active Campaign',
            description='active',
            owner=self.user,
            status=Campaign.Status.ACTIVE,
        )
        self.ended_campaign = Campaign.objects.create(
            name='Ended Campaign',
            description='ended',
            owner=self.user,
            status=Campaign.Status.ENDED,
        )

        CampaignMembership.objects.create(
            user=self.user, campaign=self.active_campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=self.user, campaign=self.ended_campaign, role=CampaignMembership.Role.DM)

        self.client.login(username='builder', password='pw')

    def test_build_create_dropdown_shows_only_active_campaigns(self):
        response = self.client.get(reverse('characters:create'))

        self.assertEqual(response.status_code, 200)
        queryset = response.context['form'].fields['campaign'].queryset
        self.assertIn(self.active_campaign, queryset)
        self.assertNotIn(self.ended_campaign, queryset)

    def test_npc_create_dropdown_shows_only_active_campaigns(self):
        response = self.client.get(reverse('characters:npc_create'))

        self.assertEqual(response.status_code, 200)
        queryset = response.context['form'].fields['campaign'].queryset
        self.assertIn(self.active_campaign, queryset)
        self.assertNotIn(self.ended_campaign, queryset)


class CharacterBuildStalenessAndReuseTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(
            username='stale_dm', password='pw')
        self.player = user_model.objects.create_user(
            username='stale_player', password='pw')

        self.campaign = Campaign.objects.create(
            name='Stale Campaign', description='desc', owner=self.dm)
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
            name='Stale Rules',
            required_character_level=3,
            starting_gold_formula='1000 + 1d6',
            allowed_source_categories=['official'],
            allow_multiclassing=False,
            allow_feats=True,
        )
        self.campaign.active_ruleset = self.ruleset
        self.campaign.save(update_fields=['active_ruleset'])

        self.class_option = DNDOption.objects.create(
            name='Paladin',
            option_type=DNDOption.OptionType.CLASS,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.species_option = DNDOption.objects.create(
            name='Yuan-Ti',
            option_type=DNDOption.OptionType.SPECIES,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.background_option = DNDOption.objects.create(
            name='Acolyte',
            option_type=DNDOption.OptionType.BACKGROUND,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.valid_feat = DNDOption.objects.create(
            name='Inspiring Leader',
            option_type=DNDOption.OptionType.FEAT,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.homebrew_option = DNDOption.objects.create(
            name='Experimental Fireball',
            option_type=DNDOption.OptionType.SPELL,
            source_category=DNDOption.SourceCategory.HOMEBREW,
        )

    def _build(self, *, with_feat=True, with_homebrew=False, status=CharacterBuild.Status.DRAFT):
        build = CharacterBuild.objects.create(
            owner=self.player,
            campaign=self.campaign,
            name='Reusable Build',
            status=status,
            character_level=self.ruleset.required_character_level,
            species_option=self.species_option,
            background_option=self.background_option,
        )
        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.class_option,
            level_count=build.character_level,
            ordering=1,
        )
        if with_feat:
            build.selected_feats.add(self.valid_feat)
        if with_homebrew:
            build.selected_spells.add(self.homebrew_option)
        return build

    def test_applying_suggested_change_marks_referencing_builds_stale(self):
        build = self._build()
        review = create_review_for_option(
            self.species_option, reason='Update species wording', opened_by=self.dm)
        change = propose_option_change(
            review,
            proposed_by=self.dm,
            target_path='description',
            operation='REPLACE',
            proposed_value='Updated species details',
            reason='Fix wording',
        )
        approve_suggested_change(change, reviewer=self.dm)

        apply_suggested_change(change, applier=self.dm)

        build.refresh_from_db()
        self.assertTrue(build.needs_revalidation)
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.STALE)
        self.assertEqual(
            build.revalidation_reason,
            'One or more D&D options used by this character were reviewed and updated.',
        )

    def test_applying_suggested_change_does_not_modify_build_selections(self):
        build = self._build()
        original_species_id = build.species_option_id
        original_feat_ids = list(
            build.selected_feats.values_list('id', flat=True))

        review = create_review_for_option(
            self.species_option, reason='Update species text', opened_by=self.dm)
        change = propose_option_change(
            review,
            proposed_by=self.dm,
            target_path='description',
            operation='REPLACE',
            proposed_value='Another update',
            reason='Fix text',
        )
        approve_suggested_change(change, reviewer=self.dm)
        apply_suggested_change(change, applier=self.dm)

        build.refresh_from_db()
        self.assertEqual(build.species_option_id, original_species_id)
        self.assertEqual(list(build.selected_feats.values_list(
            'id', flat=True)), original_feat_ids)

    def test_changing_campaign_ruleset_marks_campaign_builds_stale(self):
        build = self._build()
        new_ruleset = Ruleset.objects.create(
            campaign=self.campaign,
            name='Updated Rules',
            required_character_level=3,
            starting_gold_formula='1000 + 1d6',
            allowed_source_categories=['official'],
        )

        self.campaign.active_ruleset = new_ruleset
        self.campaign.save(update_fields=['active_ruleset'])

        build.refresh_from_db()
        self.assertTrue(build.needs_revalidation)
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.STALE)
        self.assertEqual(
            build.revalidation_reason,
            'The campaign ruleset changed after this character was last validated.',
        )

    def test_stale_build_cannot_be_reused_until_revalidated(self):
        build = self._build(status=CharacterBuild.Status.DRAFT)
        build.needs_revalidation = True
        build.validation_status = CharacterBuild.ValidationStatus.STALE
        build.save(update_fields=['needs_revalidation', 'validation_status'])

        self.client.login(username='stale_player', password='pw')
        response = self.client.post(
            reverse('characters:edit', args=[build.pk]),
            data={
                'campaign': self.campaign.pk,
                'name': build.name,
                'build_type': build.build_type,
                'status': CharacterBuild.Status.ACTIVE,
                'visibility': build.visibility,
                'character_level': build.character_level,
                'species_option': build.species_option_id,
                'background_option': build.background_option_id,
                'ability_scores': build.ability_scores,
                'selected_feats': [self.valid_feat.pk],
                'selected_spells': [],
                'selected_equipment': [],
                'selected_features': [],
                'attacks_actions': [],
                'notes': build.notes,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'must pass current validation before it can be activated or reused')

    def test_revalidating_legal_stale_build_marks_it_valid(self):
        build = self._build()
        build.needs_revalidation = True
        build.validation_status = CharacterBuild.ValidationStatus.STALE
        build.save(update_fields=['needs_revalidation', 'validation_status'])

        result = revalidate_character_build(build)

        self.assertTrue(result.is_valid)
        build.refresh_from_db()
        self.assertFalse(build.needs_revalidation)
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.VALID)
        self.assertEqual(build.validation_errors, [])
        self.assertIsNotNone(build.last_validated_at)

    def test_revalidating_illegal_stale_build_marks_it_invalid(self):
        build = self._build(with_homebrew=True)
        build.needs_revalidation = True
        build.validation_status = CharacterBuild.ValidationStatus.STALE
        build.save(update_fields=['needs_revalidation', 'validation_status'])

        result = revalidate_character_build(build)

        self.assertFalse(result.is_valid)
        build.refresh_from_db()
        self.assertTrue(build.needs_revalidation)
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.INVALID)
        self.assertTrue(build.validation_errors)
        self.assertIsNotNone(build.last_validated_at)

    def test_newly_banned_option_makes_build_invalid_after_revalidation(self):
        build = self._build(with_feat=True)
        RulesetBannedOption.objects.create(
            ruleset=self.ruleset, banned_option=self.valid_feat)

        result = revalidate_character_build(build)

        self.assertFalse(result.is_valid)
        build.refresh_from_db()
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.INVALID)
        self.assertIn(
            'contains_banned_option',
            [error['code'] for error in build.validation_errors],
        )

    def test_disallowed_source_category_makes_build_invalid_after_revalidation(self):
        build = self._build(with_homebrew=True)

        result = revalidate_character_build(build)

        self.assertFalse(result.is_valid)
        build.refresh_from_db()
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.INVALID)
        self.assertIn(
            'disallowed_source_category',
            [error['code'] for error in build.validation_errors],
        )

    def test_build_can_be_reused_only_after_current_validation_passes(self):
        build = self._build()
        build.needs_revalidation = True
        build.validation_status = CharacterBuild.ValidationStatus.STALE
        build.save(update_fields=['needs_revalidation', 'validation_status'])

        result = require_valid_build_for_reuse(build)

        self.assertFalse(result.is_valid)

        revalidate_character_build(build)
        build.refresh_from_db()
        result_after_revalidation = require_valid_build_for_reuse(build)

        self.assertTrue(result_after_revalidation.is_valid)
        self.assertEqual(build.validation_status,
                         CharacterBuild.ValidationStatus.VALID)


class BuildValidationDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(
            username="dash_dm",
            password="pw",
        )
        self.player = user_model.objects.create_user(
            username="dash_player",
            password="pw",
        )

        self.campaign = Campaign.objects.create(
            name="Dashboard Campaign",
            owner=self.dm,
        )

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

        self.class_option = DNDOption.objects.create(
            name="Dashboard Fighter",
            option_type=DNDOption.OptionType.CLASS,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )
        self.species_option = DNDOption.objects.create(
            name="Dashboard Human",
            option_type=DNDOption.OptionType.SPECIES,
            source_category=DNDOption.SourceCategory.OFFICIAL,
        )

    def _build(
        self,
        name: str,
        validation_status: str,
        *,
        needs_revalidation: bool = False,
    ) -> CharacterBuild:
        build = CharacterBuild.objects.create(
            owner=self.player,
            campaign=self.campaign,
            name=name,
            character_level=1,
            species_option=self.species_option,
            validation_status=validation_status,
            needs_revalidation=needs_revalidation,
            revalidation_reason="Rules changed" if needs_revalidation else "",
        )

        CharacterClassLevel.objects.create(
            character_build=build,
            class_option=self.class_option,
            level_count=1,
            ordering=1,
        )

        return build

    def test_build_validation_summary_counts_statuses(self):
        self._build("Valid Build", CharacterBuild.ValidationStatus.VALID)
        self._build(
            "Old Build",
            CharacterBuild.ValidationStatus.VALID,
            needs_revalidation=True,
        )
        self._build("Broken Build", CharacterBuild.ValidationStatus.INVALID)
        self._build("Unknown Build", CharacterBuild.ValidationStatus.UNKNOWN)

        summary = build_validation_summary(CharacterBuild.objects.all())

        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["valid"], 1)
        self.assertEqual(summary["stale"], 1)
        self.assertEqual(summary["invalid"], 1)
        self.assertEqual(summary["unknown"], 1)
        self.assertEqual(summary["attention_required"], 2)

    def test_builds_requiring_validation_attention_returns_stale_and_invalid(self):
        valid_build = self._build(
            "Valid Build",
            CharacterBuild.ValidationStatus.VALID,
        )
        stale_build = self._build(
            "Old Build",
            CharacterBuild.ValidationStatus.VALID,
            needs_revalidation=True,
        )
        invalid_build = self._build(
            "Broken Build",
            CharacterBuild.ValidationStatus.INVALID,
        )

        attention_builds = builds_requiring_validation_attention(
            CharacterBuild.objects.all()
        )

        self.assertNotIn(valid_build, attention_builds)
        self.assertIn(stale_build, attention_builds)
        self.assertIn(invalid_build, attention_builds)

    def test_player_dashboard_exposes_validation_context(self):
        self._build(
            "Old Build",
            CharacterBuild.ValidationStatus.VALID,
            needs_revalidation=True,
        )
        self.client.login(username="dash_player", password="pw")

        response = self.client.get(reverse("characters:player_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["validation_summary"]["stale"], 1)
        self.assertContains(response, "Builds Needing Attention")
        self.assertContains(response, "Old Build")

    def test_dm_build_list_filters_attention_builds(self):
        self._build("Valid Build", CharacterBuild.ValidationStatus.VALID)
        self._build("Broken Build", CharacterBuild.ValidationStatus.INVALID)
        self.client.login(username="dash_dm", password="pw")

        response = self.client.get(
            reverse("characters:dm_all_builds", args=[self.campaign.pk]),
            data={"validation_status": "ATTENTION"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Broken Build")
        self.assertNotContains(response, "Valid Build")

    def test_dm_build_list_filters_stale_builds(self):
        self._build("Valid Build", CharacterBuild.ValidationStatus.VALID)
        self._build(
            "Old Build",
            CharacterBuild.ValidationStatus.VALID,
            needs_revalidation=True,
        )
        self.client.login(username="dash_dm", password="pw")

        response = self.client.get(
            reverse("characters:dm_all_builds", args=[self.campaign.pk]),
            data={"validation_status": "STALE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old Build")
        self.assertNotContains(response, "Valid Build")

    def test_dm_build_list_exposes_validation_summary_context(self):
        self._build("Valid Build", CharacterBuild.ValidationStatus.VALID)
        self._build("Broken Build", CharacterBuild.ValidationStatus.INVALID)
        self.client.login(username="dash_dm", password="pw")

        response = self.client.get(
            reverse("characters:dm_all_builds", args=[self.campaign.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["validation_summary"]["total"], 2)
        self.assertEqual(response.context["validation_summary"]["valid"], 1)
        self.assertEqual(response.context["validation_summary"]["invalid"], 1)
