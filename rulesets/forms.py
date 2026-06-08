from django import forms

from .models import Ruleset
from .validators import ALLOWED_STARTING_GOLD_DICE, validate_starting_gold_formula


def _parse_formula_for_structured_fields(formula: str) -> tuple[int, int | None, str | None]:
    """Extract base and first dice token from an existing formula for form defaults."""
    normalized = (formula or '').strip().replace(' ', '')
    if not normalized:
        return 0, None, None

    parts = [part for part in normalized.replace('-', '+').split('+') if part]

    base = 0
    dice_count = None
    dice_sides = None
    for part in parts:
        if part.isdigit() and base == 0:
            base = int(part)
            continue

        if 'd' not in part:
            continue

        count_part, sides_part = part.split('d', 1)
        if not sides_part.isdigit() or sides_part not in ALLOWED_STARTING_GOLD_DICE:
            continue

        dice_count = int(count_part) if count_part else 1
        dice_sides = sides_part
        break

    return base, dice_count, dice_sides


class RulesetForm(forms.ModelForm):
    starting_gold_base = forms.IntegerField(
        min_value=0,
        required=True,
        label='Starting gold base',
        help_text='Flat amount of starting gold before any dice are rolled.',
    )
    starting_gold_dice_count = forms.IntegerField(
        min_value=1,
        required=False,
        label='Starting gold dice count',
        help_text='How many dice to roll. Leave blank to use only base gold.',
    )
    starting_gold_dice_type = forms.ChoiceField(
        required=False,
        label='Starting gold dice type',
        choices=[('', 'No dice')] + [
            (f'd{sides}', f'd{sides}')
            for sides in sorted(ALLOWED_STARTING_GOLD_DICE, key=int)
        ],
    )

    class Meta:
        model = Ruleset
        fields = [
            'name',
            'required_character_level',
            'starting_gold_formula',
            'starting_gold_base',
            'starting_gold_dice_count',
            'starting_gold_dice_type',
            'allowed_source_categories',
            'allow_multiclassing',
            'allow_feats',
            'hidden_ai_guidance',
        ]
        widgets = {
            'starting_gold_formula': forms.HiddenInput(),
        }
        help_texts = {
            'starting_gold_formula': 'Calculated from the base, dice count, and dice type fields.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['starting_gold_formula'].required = False

        existing_formula = self.initial.get('starting_gold_formula')
        if existing_formula is None and self.instance and self.instance.pk:
            existing_formula = self.instance.starting_gold_formula

        base, dice_count, dice_sides = _parse_formula_for_structured_fields(
            existing_formula or '0')
        self.initial.setdefault('starting_gold_base', base)
        self.initial.setdefault('starting_gold_dice_count', dice_count)
        self.initial.setdefault(
            'starting_gold_dice_type',
            f'd{dice_sides}' if dice_sides else '',
        )

    def clean(self):
        cleaned_data = super().clean()

        base = cleaned_data.get('starting_gold_base')
        dice_count = cleaned_data.get('starting_gold_dice_count')
        dice_type = cleaned_data.get('starting_gold_dice_type')

        if base is None:
            return cleaned_data

        if (dice_count is None) != (not dice_type):
            raise forms.ValidationError(
                'Set both dice count and dice type, or leave both empty.'
            )

        if dice_count is None and not dice_type:
            formula = f'{base}'
        else:
            formula = f'{base} + {dice_count}{dice_type}'

        validate_starting_gold_formula(formula)
        cleaned_data['starting_gold_formula'] = formula
        return cleaned_data

    def clean_starting_gold_formula(self):
        formula = self.cleaned_data.get('starting_gold_formula', '')
        if not formula:
            return formula
        validate_starting_gold_formula(formula)
        return formula
