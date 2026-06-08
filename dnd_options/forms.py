from django import forms
from django.core.exceptions import ValidationError

import json

from .json_path import validate_json_path
from .models import DNDOption, DNDOptionReviewComment, DNDOptionSuggestedChange


class DNDOptionForm(forms.ModelForm):
    class Meta:
        model = DNDOption
        fields = [
            'name',
            'option_type',
            'parent_option',
            'source_url',
            'source_category',
            'description',
            'prerequisites',
            'traits',
            'normalized_data',
            'summary',
            'primary_ability_scores',
            'mechanical_tags',
            'visual_or_flavor_tags',
            'build_notes',
            'review_reasons',
            'needs_review',
        ]


class DNDOptionImportPayloadForm(forms.Form):
    payload = forms.CharField(widget=forms.Textarea,
                              help_text='Paste AI-generated JSON payload.')

    def clean_payload(self):
        payload = self.cleaned_data['payload']
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f'Payload must be valid JSON: {exc}') from exc
        if not isinstance(parsed, dict):
            raise ValidationError('Payload JSON must be an object.')
        return parsed


class DNDOptionReviewCommentForm(forms.Form):
    comment = forms.CharField(widget=forms.Textarea)
    target_path = forms.CharField(required=False)
    visibility = forms.ChoiceField(
        choices=DNDOptionReviewComment.Visibility.choices, initial=DNDOptionReviewComment.Visibility.PUBLIC)

    def clean_target_path(self):
        target_path = self.cleaned_data.get('target_path', '').strip()
        if not target_path:
            return ''
        if not validate_json_path(target_path):
            raise ValidationError('Invalid target path syntax.')
        return target_path


class DNDOptionSuggestedChangeForm(forms.Form):
    target_path = forms.CharField()
    operation = forms.ChoiceField(
        choices=DNDOptionSuggestedChange.Operation.choices)
    proposed_value = forms.CharField(required=False, widget=forms.Textarea)
    reason = forms.CharField(widget=forms.Textarea)

    def clean_target_path(self):
        target_path = self.cleaned_data['target_path'].strip()
        if not validate_json_path(target_path):
            raise ValidationError('Invalid target path syntax.')
        return target_path

    def clean(self):
        cleaned_data = super().clean()
        operation = cleaned_data.get('operation')
        raw_proposed = cleaned_data.get('proposed_value', '').strip()

        if operation in {DNDOptionSuggestedChange.Operation.ADD, DNDOptionSuggestedChange.Operation.REPLACE}:
            if not raw_proposed:
                raise ValidationError(
                    'Proposed value is required for ADD and REPLACE.')
            try:
                cleaned_data['parsed_proposed_value'] = json.loads(
                    raw_proposed)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f'Proposed value must be valid JSON: {exc}') from exc
        else:
            cleaned_data['parsed_proposed_value'] = None

        return cleaned_data


class ReviewResolutionForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            ('APPROVED', 'APPROVED'),
            ('NO_CHANGE_NEEDED', 'NO_CHANGE_NEEDED'),
            ('REJECTED', 'REJECTED'),
            ('CLOSED', 'CLOSED'),
        ]
    )
    resolution_notes = forms.CharField(required=False, widget=forms.Textarea)


class RejectionReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea)
