from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from rulesets.models import Ruleset
from ai_builder.models import KnowledgeFeat

from .models import DNDOption, DNDOptionReview, DNDOptionSuggestedChange
from .review_services import (
    add_review_comment,
    apply_suggested_change,
    approve_suggested_change,
    propose_option_change,
    resolve_review,
)
from .services import import_dnd_option_from_ai_payload


class DNDOptionReviewServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(username='dm', password='pw')
        self.player = user_model.objects.create_user(
            username='player', password='pw')
        self.admin = user_model.objects.create_superuser(
            username='admin', password='pw', email='admin@example.com')

        self.campaign = Campaign.objects.create(
            name='Test Campaign', owner=self.dm)
        CampaignMembership.objects.create(
            user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=self.player, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

    def _payload(self, *, needs_review=True, review_reasons=None):
        return {
            'name': 'Yuan-Ti',
            'type': 'species',
            'parent': None,
            'source_url': 'https://example.com/yuan-ti',
            'source_category': 'official',
            'description': 'Snake lineage',
            'summary': 'Serpentine lineage with variant entries',
            'prerequisites': {},
            'traits': {'poison': 0.8},
            'normalized_data': {
                    'creature_type': 'humanoid',
                    'variants': [
                        {
                            'name': 'Legacy',
                            'features': [
                                    {'name': 'Old Trait',
                                             'description': 'Old text'},
                                    {'name': 'Spellcasting',
                                     'description': 'CHA spellcasting'},
                            ],
                        }
                    ],
            },
            'primary_ability_scores': ['charisma'],
            'mechanical_tags': ['support'],
            'visual_or_flavor_tags': ['serpentine'],
            'build_notes': ['Contains multiple variants in source.'],
            'review_reasons': review_reasons or [
                "Page includes a newer Mordenkainen version and an older Volo's Guide version with materially different poison defenses and spellcasting ability."
            ],
            'needs_review': needs_review,
        }

    def test_import_needs_review_true_creates_open_review(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(needs_review=True), opened_by=self.dm)

        self.assertTrue(option.needs_review)
        self.assertEqual(option.review_status,
                         DNDOption.ReviewStatus.NEEDS_REVIEW)
        review = DNDOptionReview.objects.get(dnd_option=option)
        self.assertEqual(review.status, DNDOptionReview.Status.OPEN)
        self.assertEqual(review.severity, DNDOptionReview.Severity.MEDIUM)
        self.assertEqual(review.ai_review_reasons, option.review_reasons)

    def test_import_needs_review_false_does_not_create_review(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(needs_review=False), opened_by=self.dm)
        self.assertFalse(option.needs_review)
        self.assertEqual(option.review_status, DNDOption.ReviewStatus.CLEAN)
        self.assertFalse(option.reviews.exists())

    def test_reimport_updates_existing_open_review(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(needs_review=True), opened_by=self.dm)
        first_review = option.reviews.get()

        payload = self._payload(needs_review=True, review_reasons=[
                                'missing required fields in normalized_data'])
        import_dnd_option_from_ai_payload(payload, opened_by=self.dm)

        self.assertEqual(option.reviews.count(), 1)
        first_review.refresh_from_db()
        self.assertEqual(first_review.ai_review_reasons, [
                         'missing required fields in normalized_data'])
        self.assertEqual(first_review.severity, DNDOptionReview.Severity.HIGH)

    def test_comment_on_top_level_field_stores_snapshot(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        comment = add_review_comment(
            review, author=self.player, comment='Name should match Wikidot heading.', target_path='name')

        self.assertEqual(comment.target_snapshot, 'Yuan-Ti')

    def test_comment_on_nested_path_stores_snapshot(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        comment = add_review_comment(
            review,
            author=self.player,
            comment='Spellcasting ability differs by variant.',
            target_path='normalized_data.variants[0].features[1].description',
        )

        self.assertEqual(comment.target_snapshot, 'CHA spellcasting')

    def test_propose_and_apply_nested_change_flow(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        suggested_change = propose_option_change(
            review,
            proposed_by=self.player,
            target_path='normalized_data.variants[0].features[1].description',
            operation=DNDOptionSuggestedChange.Operation.REPLACE,
            proposed_value='INT spellcasting',
            reason='Match the newer source block.',
        )

        approve_suggested_change(suggested_change, reviewer=self.dm)
        apply_suggested_change(suggested_change, applier=self.dm)

        option.refresh_from_db()
        self.assertEqual(
            option.normalized_data['variants'][0]['features'][1]['description'],
            'INT spellcasting',
        )
        suggested_change.refresh_from_db()
        self.assertEqual(suggested_change.status,
                         DNDOptionSuggestedChange.Status.APPLIED)

    def test_invalid_json_path_is_rejected(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        with self.assertRaises(ValidationError):
            propose_option_change(
                review,
                proposed_by=self.player,
                target_path='normalized_data.features[abc].name',
                operation=DNDOptionSuggestedChange.Operation.REPLACE,
                proposed_value='Updated',
                reason='Invalid path test',
            )

    def test_protected_path_is_rejected(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        with self.assertRaises(ValidationError):
            propose_option_change(
                review,
                proposed_by=self.player,
                target_path='created_at',
                operation=DNDOptionSuggestedChange.Operation.REPLACE,
                proposed_value='2026-06-03T00:00:00Z',
                reason='Should fail',
            )

    def test_invalid_trait_name_is_rejected(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        with self.assertRaises(ValidationError):
            propose_option_change(
                review,
                proposed_by=self.player,
                target_path='traits.invalid_trait',
                operation=DNDOptionSuggestedChange.Operation.REPLACE,
                proposed_value=1.0,
                reason='Bad trait',
            )

    def test_invalid_trait_weight_is_rejected(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        with self.assertRaises(ValidationError):
            propose_option_change(
                review,
                proposed_by=self.player,
                target_path='traits.poison',
                operation=DNDOptionSuggestedChange.Operation.REPLACE,
                proposed_value=3.5,
                reason='Out of range',
            )

    def test_resolve_review_updates_option_status(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        resolve_review(
            review,
            resolver=self.dm,
            status=DNDOptionReview.Status.NO_CHANGE_NEEDED,
            resolution_notes='Current implementation is good.',
        )

        option.refresh_from_db()
        self.assertFalse(option.needs_review)
        self.assertEqual(option.review_status, DNDOption.ReviewStatus.REVIEWED)

    def test_apply_suggested_change_marks_linked_knowledge_for_refresh(self):
        option = import_dnd_option_from_ai_payload(
            self._payload(), opened_by=self.dm)
        review = option.reviews.get()

        knowledge = KnowledgeFeat.objects.create(
            name=option.name,
            source_url=option.source_url,
            source_category=option.source_category,
            feat_category='general',
            dnd_option=option,
            needs_review=False,
            review_reasons=[],
        )

        suggested_change = propose_option_change(
            review,
            proposed_by=self.player,
            target_path='summary',
            operation=DNDOptionSuggestedChange.Operation.REPLACE,
            proposed_value='Updated summary',
            reason='Refresh summary.',
        )
        approve_suggested_change(suggested_change, reviewer=self.dm)
        apply_suggested_change(suggested_change, applier=self.dm)

        knowledge.refresh_from_db()
        self.assertTrue(knowledge.needs_review)
        self.assertIn(
            'Linked D&D option was reviewed and updated; refresh knowledge row from source.',
            knowledge.review_reasons,
        )

    def test_direct_option_content_edit_marks_linked_knowledge_for_refresh(self):
        option = DNDOption.objects.create(
            name='Editable Option',
            option_type=DNDOption.OptionType.FEAT,
            source_url='https://example.com/editable-option',
            source_category=DNDOption.SourceCategory.OFFICIAL,
            summary='Before',
        )
        knowledge = KnowledgeFeat.objects.create(
            name='Editable Option',
            source_url='https://example.com/editable-option',
            source_category='official',
            feat_category='general',
            dnd_option=option,
            needs_review=False,
            review_reasons=[],
        )

        option.summary = 'After'
        option.save(update_fields=['summary', 'updated_at'])

        knowledge.refresh_from_db()
        self.assertTrue(knowledge.needs_review)
        self.assertIn(
            'Linked D&D option content changed; refresh knowledge row from source.',
            knowledge.review_reasons,
        )


class DNDOptionReviewViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dm = user_model.objects.create_user(
            username='dm_view', password='pw')
        self.player = user_model.objects.create_user(
            username='player_view', password='pw')

        self.campaign = Campaign.objects.create(name='Campaign', owner=self.dm)
        CampaignMembership.objects.create(
            user=self.dm, campaign=self.campaign, role=CampaignMembership.Role.DM)
        CampaignMembership.objects.create(
            user=self.player, campaign=self.campaign, role=CampaignMembership.Role.PLAYER)

        self.ruleset = Ruleset.objects.create(
            campaign=self.campaign,
            name='Rules',
            required_character_level=1,
            starting_gold_formula='1000 + 1d6',
            hidden_ai_guidance='this should stay hidden',
        )

        payload = {
            'name': 'Reviewable Option',
            'type': 'feature',
            'source_category': 'official',
            'source_url': 'https://example.com/feature',
            'normalized_data': {'features': [{'description': 'Old'}]},
            'traits': {'poison': 0.5},
            'needs_review': True,
            'review_reasons': ['Ambiguous source version'],
        }
        self.option = import_dnd_option_from_ai_payload(
            payload, opened_by=self.dm)
        self.review = self.option.reviews.get()

    def test_player_can_propose_change_but_cannot_apply(self):
        self.client.login(username='player_view', password='pw')

        propose_response = self.client.post(
            reverse('dnd_options:propose_change', args=[self.review.pk]),
            data={
                'target_path': 'normalized_data.features[0].description',
                'operation': 'REPLACE',
                'proposed_value': '"New text"',
                'reason': 'Fix wording',
            },
        )
        self.assertEqual(propose_response.status_code, 302)

        suggested_change = self.review.suggested_changes.get()
        apply_response = self.client.post(
            reverse('dnd_options:apply_change', args=[suggested_change.pk]))
        self.assertEqual(apply_response.status_code, 403)

    def test_dm_can_approve_and_apply_change(self):
        suggested_change = propose_option_change(
            self.review,
            proposed_by=self.player,
            target_path='normalized_data.features[0].description',
            operation=DNDOptionSuggestedChange.Operation.REPLACE,
            proposed_value='Fixed',
            reason='Update text',
        )

        self.client.login(username='dm_view', password='pw')

        approve_response = self.client.post(
            reverse('dnd_options:approve_change', args=[suggested_change.pk]))
        self.assertEqual(approve_response.status_code, 302)

        apply_response = self.client.post(
            reverse('dnd_options:apply_change', args=[suggested_change.pk]))
        self.assertEqual(apply_response.status_code, 302)

        self.option.refresh_from_db()
        self.assertEqual(
            self.option.normalized_data['features'][0]['description'], 'Fixed')

    def test_import_json_view_uses_import_service(self):
        self.client.login(username='dm_view', password='pw')

        response = self.client.post(
            reverse('dnd_options:import_json'),
            data={
                'payload': '{"name":"Imported Spell","type":"spell","source_category":"official","needs_review":true,"review_reasons":["missing required fields"]}'
            },
        )
        self.assertEqual(response.status_code, 302)

        imported = DNDOption.objects.get(name='Imported Spell')
        self.assertTrue(imported.needs_review)
        self.assertTrue(imported.reviews.filter(
            status=DNDOptionReview.Status.OPEN).exists())

    def test_hidden_dm_guidance_not_visible_on_review_page(self):
        self.client.login(username='player_view', password='pw')
        response = self.client.get(
            reverse('dnd_options:review_detail', args=[self.review.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.ruleset.hidden_ai_guidance)
