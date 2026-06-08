from typing import TYPE_CHECKING

from django import forms
from django.forms import ModelChoiceField

from dnd_options.models import DNDOption

from .models import RulesetBannedOption

if TYPE_CHECKING:
    from .models import Ruleset


class RulesetBannedOptionForm(forms.ModelForm):
    ruleset: 'Ruleset | None'

    banned_option = forms.ModelChoiceField(
        queryset=DNDOption.objects.none(),
        required=True,
        label='D&D option to restrict',
        help_text='Select a canonical D&D option that should be unavailable in this ruleset.',
    )

    class Meta:
        model = RulesetBannedOption
        fields = ['banned_option', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(
        self,
        *args,
        ruleset: 'Ruleset | None' = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.ruleset = ruleset
        banned_option_field = self.fields['banned_option']
        assert isinstance(banned_option_field, ModelChoiceField)
        banned_option_field.queryset = DNDOption.objects.order_by(
            'option_type', 'name'
        )

    def clean_banned_option(self):
        banned_option = self.cleaned_data['banned_option']
        if self.ruleset is None:
            return banned_option

        existing = RulesetBannedOption.objects.filter(
            ruleset=self.ruleset,
            banned_option=banned_option,
        )
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('This option is already restricted for this ruleset.')
        return banned_option

    def save(self, commit: bool = True) -> RulesetBannedOption:
        instance = super().save(commit=False)
        if self.ruleset is not None:
            instance.ruleset = self.ruleset
        if commit:
            instance.save()
        return instance
