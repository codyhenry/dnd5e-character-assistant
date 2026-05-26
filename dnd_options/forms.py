from django import forms

from .models import DNDOption


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
        ]
