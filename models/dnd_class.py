from dataclasses import dataclass, field

@dataclass
class Class:
    name: str
    hit_die: int
    abilities: list[str] = field(default_factory=list)