"""The branching story: scenes, choices, consequences and endings.

This is authored, deterministic game logic and the source of truth for src/story data. The transformer never
decides what happens. It receives a beat token saying what just happened, plus flags, and writes the narration.

State is (scene, flags, wounds). A choice may require flags, set flags, wound the player, and lead to a scene.
Some beats exist in two forms so that earlier decisions visibly change later events.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, replace

LAMP, KEY, FRIEND, SWORD, CURSED = 1, 2, 4, 8, 16
FLAG_NAMES = {LAMP: "LAMP", KEY: "KEY", FRIEND: "FRIEND", SWORD: "SWORD", CURSED: "CURSED"}
MAX_WOUNDS = 3


@dataclass(frozen=True)
class Choice:
    label: str               # at most 16 characters, shown in the menu
    beat: str                # what the narrator is told happened
    next: str                # next scene id
    requires: int = 0        # flags needed for this choice to appear
    forbids: int = 0         # flags that hide this choice
    sets: int = 0            # flags gained
    clears: int = 0          # flags lost
    wounds: int = 0          # wounds taken
    danger: bool = False     # the omen for the scene warns about this choice


@dataclass(frozen=True)
class Scene:
    id: str
    title: str               # room name on the band, at most 11 characters
    art: int                 # index into the eight existing scene images
    choices: tuple[Choice, ...] = ()
    ending: bool = False


FOREST, MARSH, RIVER, RUINS, SHRINE, CAVE, GATE, TOWER = range(8)

SCENES = (
    # Act 1: gather what you will need. Both early decisions change what is possible later.
    Scene("wood", "DARK FOREST", FOREST, (
        Choice("Follow the light", "SEE_RUINS", "ruins"),
        Choice("Hear the voice", "HEAR_VOICE", "pit"),
    )),
    Scene("ruins", "OLD RUINS", RUINS, (
        Choice("Take the lamp", "TAKE_LAMP", "fork", sets=LAMP),
        Choice("Take the sword", "TAKE_SWORD", "fork", sets=SWORD),
    )),
    Scene("pit", "BLACK MARSH", MARSH, (
        Choice("Free the prisoner", "FREE_PRISONER", "fork", sets=FRIEND),
        Choice("Take his ring", "TAKE_RING", "fork", sets=CURSED),
        Choice("Leave him", "LEAVE_PRISONER", "fork"),
    )),
    Scene("fork", "COLD RIVER", RIVER, (
        Choice("Cross the bridge", "CROSS_BRIDGE", "shrine", danger=True, wounds=1),
        Choice("Wade the shallows", "WADE_RIVER", "shrine"),
        Choice("Enter the cave", "ENTER_CAVE", "cave"),
    )),
    # Act 2: the key is here, and the lamp decides how you can reach it.
    Scene("cave", "DEEP CAVE", CAVE, (
        Choice("Light the lamp", "LIGHT_LAMP", "vault", requires=LAMP),
        Choice("Creep in the dark", "CREEP_DARK", "shrine", forbids=LAMP, danger=True, wounds=1),
        Choice("Call for help", "FRIEND_LEADS", "vault", requires=FRIEND),
        Choice("Turn back", "LEAVE_CAVE", "shrine"),
    )),
    Scene("vault", "DEEP CAVE", CAVE, (
        Choice("Take the key", "TAKE_KEY", "shrine", sets=KEY),
        Choice("Open the chest", "OPEN_CHEST", "shrine", sets=KEY, wounds=1, danger=True),
    )),
    Scene("shrine", "PALE SHRINE", SHRINE, (
        Choice("Pray at the altar", "PRAY", "gate", forbids=CURSED),
        Choice("Burn the ring", "BURN_RING", "gate", requires=CURSED, clears=CURSED, wounds=1),
        Choice("Take the blade", "TAKE_BLADE", "gate", sets=SWORD, forbids=SWORD, wounds=1, danger=True),
        Choice("Walk on", "PASS_SHRINE", "gate"),
    )),
    # Act 3: the gate and the guardian. What you carry decides which endings remain.
    Scene("gate", "IRON GATE", GATE, (
        Choice("Use the key", "OPEN_GATE", "hall", requires=KEY),
        Choice("Force the bars", "FORCE_GATE", "hall", requires=SWORD, wounds=1, danger=True),
        Choice("Friend lifts you", "FRIEND_LIFTS", "hall", requires=FRIEND, forbids=KEY),
        Choice("Climb the wall", "CLIMB_WALL", "hall", wounds=1, forbids=FRIEND),
        Choice("Give up and flee", "FLEE", "end_flee"),
    )),
    Scene("hall", "THE TOWER", TOWER, (
        Choice("Sneak past him", "SNEAK", "top", forbids=CURSED),
        Choice("Sneak past him", "SNEAK_CURSED", "duel", requires=CURSED),
        Choice("Wake him", "WAKE", "talk"),
        Choice("Strike him", "STRIKE", "duel", requires=SWORD, danger=True),
    )),
    Scene("talk", "THE TOWER", TOWER, (
        Choice("Free him", "FREE_GUARDIAN", "end_free", forbids=CURSED),
        Choice("Ask for the crown", "ASK_CROWN", "duel", danger=True),
        Choice("Show the ring", "SHOW_RING", "end_bound", requires=CURSED),
    )),
    Scene("duel", "THE TOWER", TOWER, (
        Choice("Fight on", "FIGHT_SWORD", "top", requires=SWORD, wounds=1),
        Choice("Friend holds him", "FRIEND_HOLDS", "top", requires=FRIEND, clears=FRIEND),
        Choice("Run for the stairs", "RUN_STAIRS", "end_fall", danger=True),
        Choice("Yield to him", "YIELD", "end_yield", forbids=SWORD),
    )),
    Scene("top", "THE TOWER", TOWER, (
        Choice("Take the crown", "TAKE_CROWN", "end_crown"),
        Choice("Break the crown", "BREAK_CROWN", "end_break"),
    )),
    # Endings. Every run reaches exactly one.
    Scene("end_crown", "THE TOWER", TOWER, ending=True),
    Scene("end_break", "THE TOWER", TOWER, ending=True),
    Scene("end_free", "THE TOWER", TOWER, ending=True),
    Scene("end_bound", "THE TOWER", TOWER, ending=True),
    Scene("end_fall", "THE TOWER", TOWER, ending=True),
    Scene("end_yield", "THE TOWER", TOWER, ending=True),
    Scene("end_flee", "DARK FOREST", FOREST, ending=True),
    Scene("end_dead", "BLACK MARSH", MARSH, ending=True),
)
BY_ID = {s.id: s for s in SCENES}
START = "wood"
DEATH_SCENE = "end_dead"
ENDING_NAMES = {"end_crown": "THE NEW KING", "end_break": "THE LAST LIGHT", "end_free": "THE FREED ONE", "end_bound": "THE RING KEEPER",
                "end_fall": "THE LONG FALL", "end_yield": "THE SERVANT", "end_flee": "THE COWARD", "end_dead": "THE MIST TAKES YOU"}
ACTS = {"wood": 1, "ruins": 1, "pit": 1, "fork": 1, "cave": 2, "vault": 2, "shrine": 2, "gate": 3, "hall": 3, "talk": 3, "duel": 3, "top": 3}
BEATS = tuple(sorted({c.beat for s in SCENES for c in s.choices}))


@dataclass(frozen=True)
class State:
    scene: str = START
    flags: int = 0
    wounds: int = 0
    turn: int = 0


def available(s: State) -> list[Choice]:
    """Choices the player can see right now. There is always at least one in a non-ending scene."""
    scene = BY_ID[s.scene]
    return [c for c in scene.choices if (s.flags & c.requires) == c.requires and not (s.flags & c.forbids)]


def step(s: State, c: Choice) -> State:
    wounds = s.wounds + c.wounds
    nxt = DEATH_SCENE if wounds >= MAX_WOUNDS else c.next
    return replace(s, scene=nxt, flags=(s.flags | c.sets) & ~c.clears, wounds=wounds, turn=s.turn + 1)


def reachable() -> set[State]:
    """Every state a player can reach, ignoring the turn counter."""
    begin = State()
    seen, q = {begin}, deque([begin])
    while q:
        cur = q.popleft()
        for c in available(cur):
            n = replace(step(cur, c), turn=0)
            if n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def narration_situations() -> set[tuple[str, int, int]]:
    """Every (beat, flags after the choice, wounds after the choice) that narration can be asked for."""
    out = set()
    for s in reachable():
        for c in available(s):
            n = step(s, c)
            out.add((c.beat, n.flags, n.wounds))
    return out
