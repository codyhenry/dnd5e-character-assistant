from dataclasses import dataclass, field


@dataclass
class BuildIntent:
    fantasy_summary: str
    desired_traits: list[str] = field(default_factory=list)
    mechanical_priorities: list[str] = field(default_factory=list)
    visual_reflavor: str = ''
    explicit_constraints: list[str] = field(default_factory=list)
