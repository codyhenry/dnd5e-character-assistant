from typing import cast

from django import forms

from campaigns.models import Campaign


class AICharacterPromptForm(forms.Form):
    campaign = forms.ModelChoiceField(queryset=None)
    prompt = forms.CharField(widget=forms.Textarea, label='Character concept')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            campaign_field = cast(forms.ModelChoiceField,
                                  self.fields['campaign'])
            campaign_field.queryset = Campaign.objects.filter(
                memberships__user=user,
                status=Campaign.Status.ACTIVE,
            ).distinct()
