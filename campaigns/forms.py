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
        # Only allow assigning active rulesets that belong to this campaign.
        if self.instance and self.instance.pk:
            self.fields['active_ruleset'].queryset = self.instance.rulesets.all()
        else:
            self.fields['active_ruleset'].queryset = self.fields['active_ruleset'].queryset.none()


class CampaignMembershipForm(forms.ModelForm):
    class Meta:
        model = CampaignMembership
        fields = ['user', 'role']
