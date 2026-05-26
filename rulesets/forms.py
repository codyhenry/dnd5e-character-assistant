from django import forms

from .models import Ruleset


class RulesetForm(forms.ModelForm):
    class Meta:
        model = Ruleset
        fields = [
            'name',
            'required_character_level',
            'starting_gold_formula',
            'allowed_source_categories',
            'allow_multiclassing',
            'allow_feats',
            'hidden_ai_guidance',
        ]
