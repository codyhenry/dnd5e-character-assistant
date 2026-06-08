from typing import cast

from django import forms

from .models import Campaign, CampaignMembership


class CampaignCreateForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'description']


class CampaignUpdateForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'description', 'status', 'active_ruleset']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_ruleset_field = cast(
            forms.ModelChoiceField, self.fields['active_ruleset'])
        # Only allow assigning active rulesets that belong to this campaign.
        if self.instance and self.instance.pk:
            active_ruleset_field.queryset = self.instance.rulesets.all()
        else:
            active_ruleset_field.queryset = active_ruleset_field.queryset.none()


class CampaignMembershipForm(forms.ModelForm):
    class Meta:
        model = CampaignMembership
        fields = ['user', 'role']
