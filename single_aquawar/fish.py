from __future__ import annotations

"""Definitions for all fish types used in Aquawar.

The implementation follows the unofficial manual in ``game_description.md``.
Each fish is represented by an instance of :class:`Fish` (or subclasses)
that contains its current HP, ATK and all relevant status flags.

The module focuses on the core combat logic and exposes a small API used by
``game.py`` to run full rounds and games.

The code tries to closely follow the rules.  The engine is intentionally
written in a very explicit manner – readability is favoured over absolute
performance as games only contain a handful of entities.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, TYPE_CHECKING, Any
import random

if TYPE_CHECKING:
    from .game import GameState

MAX_HP = 400
BASE_ATK = 100

# ---------------------------------------------------------------------------
# Helper data structures
# ---------------------------------------------------------------------------

@dataclass
class Buff:
    """Represents a temporary effect that triggers on the next damage."""

    kind: str  # 'reduce', 'share', 'heal'
    value: float


@dataclass
class Fish:
    name: str
    hp: int = MAX_HP
    atk: int = BASE_ATK
    revealed: bool = False
    buffs: List[Buff] = field(default_factory=list)
    shields: int = 0
    dodge_chance: float = 0.0
    used_active_count: int = 0
    mimic_source: Optional[str] = None  # only used for Mimic Fish

    # ------------------------------------------------------------------
    # Life cycle helpers
    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        return self.hp > 0

    def reset(self) -> None:
        self.hp = MAX_HP
        self.atk = BASE_ATK
        self.revealed = False
        self.buffs.clear()
        self.shields = 0
        self.dodge_chance = 0.0
        self.used_active_count = 0
        self.mimic_source = None

    # ------------------------------------------------------------------
    # Damage processing
    # ------------------------------------------------------------------
    def take_damage(self, amount: int, source: Optional[Fish], *, direct: bool = True,
                    game: Optional[Any] = None) -> int:
        """Apply ``amount`` of damage to this fish.

        Returns the actual damage taken.  This method implements the order of
        operations defined in the manual: pre-damage (shield/dodge), on-damage
        (sharing / reduction), damage application and post-damage triggers.
        """
        
        if game and hasattr(game, '_debug_log'):
            game._debug_log(f"Fish.take_damage called: {self.name} taking {amount} damage, direct={direct}")

        if amount <= 0 or not self.is_alive():
            if game and hasattr(game, '_debug_log'):
                game._debug_log(f"Fish.take_damage: No damage to apply (amount={amount}, alive={self.is_alive()})")
            return 0

        # Pre-damage: shields and dodge
        if self.shields > 0:
            self.shields -= 1
            return 0

        if self.dodge_chance > 0 and random.random() < self.dodge_chance:
            return 0

        # On-damage: buffs that reduce or share damage
        shared: List[Fish] = []
        original_amount = amount
        for buff in list(self.buffs):
            if buff.kind == "reduce" and direct:
                amount = int(amount * (1.0 - buff.value))
                self.buffs.remove(buff)
            elif buff.kind == "share" and direct:
                amount = int(amount * buff.value)
                # remaining damage spreads to teammates - handled in game
                if game:
                    shared = [f for f in game.team_of(self).living_fish() if f is not self]
                    if shared:
                        split = (original_amount - amount) // len(shared)
                        for mate in shared:
                            mate.take_damage(split, source, direct=direct, game=game)
                self.buffs.remove(buff)

        # Damage application
        self.hp -= amount

        # Post-damage: healing buffs
        for buff in list(self.buffs):
            if buff.kind == "heal" and direct:
                self.hp += int(buff.value)
                if self.hp > MAX_HP:
                    self.hp = MAX_HP
                self.buffs.remove(buff)

        # Passive effects after taking damage
        if direct and game:
            self.after_direct_damage(amount, source, game)

        return amount

    # ------------------------------------------------------------------
    # Hooks for subclasses to override
    # ------------------------------------------------------------------
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        """Called after damage is successfully applied by a direct attack."""
        pass

    def after_teammate_attacked(self, mate: Fish, source: Fish, game: Any) -> None:
        """Called after a teammate was attacked."""
        pass

    def after_direct_attack(self, target: Fish, game: Any, *, used_normal: bool) -> None:
        """Called after this fish directly attacked ``target``."""
        pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def normal_attack(self, target: Fish, game: Any) -> None:
        dmg = int(0.5 * self.atk)
        actual = target.take_damage(dmg, self, direct=True, game=game)
        self.after_direct_attack(target, game, used_normal=True)
        # Notify teammates of retaliation style passives
        for mate in game.team_of(target).living_fish():
            if mate is not target:
                mate.after_teammate_attacked(target, self, game)

    def active(self, game: Any, actor_idx: int) -> None:
        """Perform the active ability.  Subclasses override."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Specific fish implementations
# ---------------------------------------------------------------------------


class Archerfish(Fish):
    def after_teammate_attacked(self, mate: Fish, source: Fish, game: Any) -> None:
        if mate.hp > 0 and mate.hp < 120:
            source.take_damage(30, self, direct=True, game=game)

    def active(self, game: Any, actor_idx: int) -> None:
        dmg = int(self.atk * 0.35)
        for f in game.other_team_of(self).living_fish():
            f.take_damage(dmg, self, direct=True, game=game)
        self.after_direct_attack(None, game, used_normal=False)


class Pufferfish(Fish):
    def after_teammate_attacked(self, mate: Fish, source: Fish, game: Any) -> None:
        if mate.hp > 0 and mate.hp < 120:
            source.take_damage(30, self, direct=True, game=game)

    def active(self, game: Any, actor_idx: int) -> None:
        teammates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(teammates))
        if target is not None:
            target.take_damage(50, self, direct=True, game=game)
            self.atk += 70
        self.after_direct_attack(None, game, used_normal=False)


class ElectricEel(Fish):
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if amount > 0:
            taken_before = getattr(self, "_taken", 0) + amount
            setattr(self, "_taken", taken_before)
            while getattr(self, "_taken", 0) >= 200:
                self.atk += 20
                setattr(self, "_taken", getattr(self, "_taken", 0) - 200)

    def take_damage(self, amount: int, source: Optional[Fish], *, direct: bool = True,
                    game: Optional[Any] = None) -> int:
        if direct and game:
            mates = [f for f in game.team_of(self).living_fish() if f is not self]
            if mates:
                share = int(amount * 0.3)
                split = share // len(mates)
                for m in mates:
                    m.take_damage(split, source, direct=True, game=game)
                amount = amount - share
        return super().take_damage(amount, source, direct=direct, game=game)

    def active(self, game: Any, actor_idx: int) -> None:
        dmg = int(self.atk * 0.35)
        for f in game.other_team_of(self).living_fish():
            f.take_damage(dmg, self, direct=True, game=game)
        self.after_direct_attack(None, game, used_normal=False)


class Sunfish(ElectricEel):
    def active(self, game: Any, actor_idx: int) -> None:
        teammates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(teammates))
        if target is not None:
            target.take_damage(50, self, direct=True, game=game)
            self.atk += 70
        self.after_direct_attack(None, game, used_normal=False)


class SeaWolf(Fish):
    def __init__(self, name: str):
        super().__init__(name)
        self.dodge_chance = 0.3

    def active(self, game: Any, actor_idx: int) -> None:
        target = game.choose_enemy(actor_idx, len(game.other_team_of(self).living_fish()))
        if target is not None:
            target.take_damage(120, self, direct=True, game=game)
        self.after_direct_attack(target, game, used_normal=False)


class MantaRay(Fish):
    def __init__(self, name: str):
        super().__init__(name)
        self.dodge_chance = 0.3

    def active(self, game: Any, actor_idx: int) -> None:
        mates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(mates))
        if target is not None:
            target.buffs.append(Buff("reduce", 0.7))
            self.atk += 20
        self.after_direct_attack(None, game, used_normal=False)


class SeaTurtle(Fish):
    def __init__(self, name: str):
        super().__init__(name)
        self.shields = 3

    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if self.shields <= 0 and self.dodge_chance == 0:
            self.dodge_chance = 0.3

    def active(self, game: Any, actor_idx: int) -> None:
        mates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(mates))
        if target is not None:
            target.buffs.append(Buff("heal", 20))
            if self.used_active_count < 3:
                enemy = game.choose_enemy(actor_idx, len(game.other_team_of(self).living_fish()))
                if enemy is not None:
                    enemy.take_damage(120, self, direct=True, game=game)
        self.used_active_count += 1
        self.after_direct_attack(None, game, used_normal=False)


class Octopus(Fish):
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if self.is_alive():
            self.hp = min(MAX_HP, self.hp + 20)

    def active(self, game: Any, actor_idx: int) -> None:
        mates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(mates))
        if target is not None:
            target.buffs.append(Buff("reduce", 0.7))
            self.atk += 20
        self.after_direct_attack(None, game, used_normal=False)


class GreatWhiteShark(Fish):
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if self.is_alive():
            self.hp = min(MAX_HP, self.hp + 20)

    def active(self, game: Any, actor_idx: int) -> None:
        enemies = game.other_team_of(self).living_fish()
        if not enemies:
            return
        target = min(enemies, key=lambda f: f.hp)
        dmg = int(self.atk * (1.4 if target.hp < 160 else 1.2))
        target.take_damage(dmg, self, direct=True, game=game)
        self.after_direct_attack(target, game, used_normal=False)


class HammerheadShark(GreatWhiteShark):
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if self.hp < 80:
            self.atk = BASE_ATK + 15
        if self.is_alive():
            self.hp = min(MAX_HP, self.hp + 20)

    def take_damage(self, amount: int, source: Optional[Fish], *, direct: bool = True,
                    game: Optional[Any] = None) -> int:
        before = self.hp
        result = super().take_damage(amount, source, direct=direct, game=game)
        if direct and self.hp <= 0 and source is not None:
            source.take_damage(40, self, direct=True, game=game)
        return result


class Clownfish(Fish):
    def after_direct_damage(self, amount: int, source: Optional[Fish], game: Any) -> None:
        if self.hp < 120 and source is not None:
            source.take_damage(30, self, direct=True, game=game)

    def active(self, game: Any, actor_idx: int) -> None:
        mates = game.team_of(self).living_fish()
        target = game.choose_teammate(actor_idx, len(mates))
        if target is not None:
            target.buffs.append(Buff("share", 0.7))
            if self.used_active_count < 3:
                dmg = int(self.atk * 0.35)
                for f in game.other_team_of(self).living_fish():
                    f.take_damage(dmg, self, direct=True, game=game)
        self.used_active_count += 1
        self.after_direct_attack(None, game, used_normal=False)


class MimicFish(Fish):
    def copy_from(self, template: Fish) -> None:
        self.mimic_source = template.name
        # Copy active method properly
        template_class = template.__class__
        self.active = lambda game, actor_idx: template_class.active(self, game, actor_idx)
        
        # Copy other methods if they are overridden, but be more careful with take_damage
        if hasattr(template_class, 'after_direct_damage') and template_class.after_direct_damage != Fish.after_direct_damage:
            self.after_direct_damage = lambda amount, source, game: template_class.after_direct_damage(self, amount, source, game)
            
        # Don't copy take_damage method - let Mimic Fish use the base Fish implementation
        # This avoids method binding issues that were causing assertion damage to be ignored
        
        # Copy special attributes
        if hasattr(template, 'dodge_chance') and template.dodge_chance != 0:
            self.dodge_chance = template.dodge_chance
        if hasattr(template, 'shields') and template.shields != 0:
            self.shields = template.shields

    def active(self, game: Any, actor_idx: int) -> None:  # pragma: no cover - replaced
        pass


# Mapping helper ----------------------------------------------------------------

FISH_FACTORIES: Dict[str, Callable[[str], Fish]] = {
    "Archerfish": Archerfish,
    "Pufferfish": Pufferfish,
    "Electric Eel": ElectricEel,
    "Sunfish": Sunfish,
    "Sea Wolf": SeaWolf,
    "Manta Ray": MantaRay,
    "Sea Turtle": SeaTurtle,
    "Octopus": Octopus,
    "Great White Shark": GreatWhiteShark,
    "Hammerhead Shark": HammerheadShark,
    "Clownfish": Clownfish,
    "Mimic Fish": MimicFish,
}


def create_fish(name: str) -> Fish:
    factory = FISH_FACTORIES[name]
    return factory(name)

