from django import forms

from .models import Campaign, CampaignMembership


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'description', 'active_ruleset']


class CampaignMembershipForm(forms.ModelForm):
    class Meta:
        model = CampaignMembership
        fields = ['user', 'role']
