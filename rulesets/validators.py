import re

from django.core.exceptions import ValidationError


ALLOWED_STARTING_GOLD_DICE = {'4', '6', '8', '10', '12', '20', '100'}
_ALLOWED_DICE_PATTERN = '|'.join(sorted(ALLOWED_STARTING_GOLD_DICE, key=int))
_STARTING_GOLD_TOKEN_RE = re.compile(rf'^\d+$|^\d*d({_ALLOWED_DICE_PATTERN})$')


def validate_starting_gold_formula(value: str) -> None:
    """Validate formulas like "1000 + 10d6" for deferred dice rolling.

    Allowed tokens:
    - Integer constants (e.g. 1000)
    - Dice notation using d4, d6, d8, d10, d12, d20, d100 (e.g. d6, 2d8, 10d20)
    Operators are limited to + and -.
    """
    if value is None:
        raise ValidationError('Starting gold formula is required.')

    formula = value.strip().replace(' ', '')
    if not formula:
        raise ValidationError('Starting gold formula is required.')

    allowed_dice_text = ', '.join(f'd{die}' for die in sorted(
        ALLOWED_STARTING_GOLD_DICE, key=int))

    # Split while keeping operators, then validate alternating token/operator layout.
    parts = [part for part in re.split(r'([+-])', formula) if part]
    if not parts:
        raise ValidationError('Invalid starting gold formula.')

    expect_token = True
    for part in parts:
        if expect_token:
            if not _STARTING_GOLD_TOKEN_RE.fullmatch(part):
                raise ValidationError(
                    'Invalid token in starting gold formula. '
                    f'Use numbers or dice like 10d6 with {allowed_dice_text}.'
                )
        else:
            if part not in {'+', '-'}:
                raise ValidationError(
                    'Only + and - operators are allowed in starting gold formula.')
        expect_token = not expect_token

    if expect_token:
        raise ValidationError(
            'Starting gold formula cannot end with an operator.')


def source_category_allowed(source_category: str, allowed_source_categories: list[str]) -> bool:
    if not allowed_source_categories:
        return True
    return source_category in allowed_source_categories
