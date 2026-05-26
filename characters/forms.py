from django import forms

from .models import CharacterBuild, CharacterClassLevel


class CharacterBuildForm(forms.ModelForm):
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
