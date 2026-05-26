import random
import re


_DICE_PATTERN = re.compile(r'^\s*(\d+)\s*\+\s*(\d+)d(\d+)\s*$')
_NUMBER_PATTERN = re.compile(r'^\s*(\d+)\s*$')


def calculate_starting_gold(formula: str) -> int | None:
    """Parse simple starting-gold formulas.

    Supported formats: `1000`, `1000 + 1d6`, `500 + 2d4`.
    Returns None for unsupported formats as a safe placeholder for future expansion.
    """
    number_match = _NUMBER_PATTERN.match(formula)
    if number_match:
        return int(number_match.group(1))

    dice_match = _DICE_PATTERN.match(formula)
    if not dice_match:
        return None

    base, count, sides = map(int, dice_match.groups())
    return base + sum(random.randint(1, sides) for _ in range(count))
