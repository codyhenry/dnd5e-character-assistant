from django import forms

from campaigns.models import Campaign

from .models import CharacterBuild, CharacterClassLevel


class CharacterBuildForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            queryset = Campaign.objects.filter(
                memberships__user=user,
                status=Campaign.Status.ACTIVE,
            ).distinct()

            # Keep the existing campaign selectable when editing legacy builds.
            if self.instance and self.instance.pk:
                queryset = (queryset | Campaign.objects.filter(
                    pk=self.instance.campaign_id)).distinct()

            self.fields['campaign'].queryset = queryset

    class Meta:
        model = CharacterBuild
        fields = [
            'campaign',
            'name',
            'build_type',
            'status',
            'visibility',
            'character_level',
            'species_option',
            'background_option',
            'ability_scores',
            'selected_feats',
            'selected_spells',
            'selected_equipment',
            'selected_features',
            'attacks_actions',
            'notes',
        ]


class CharacterClassLevelForm(forms.ModelForm):
    class Meta:
        model = CharacterClassLevel
        fields = ['class_option', 'subclass_option', 'level_count', 'ordering']
