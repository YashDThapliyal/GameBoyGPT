"""Authoritative Python port of the deterministic world rules in src/game.asm.

Independent reference used by solvability search and by ROM parity tests. Neither the
narrative model nor the display can change this state; the model only narrates outcomes.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace

ROOMS = ["FOREST", "MARSH", "RIVER", "RUINS", "SHRINE", "CAVE", "GATE", "TOWER"]
FOREST, MARSH, RIVER, RUINS, SHRINE, CAVE, GATE, TOWER = range(8)
ACTIONS = ["LEFT", "RIGHT", "FORWARD", "SEARCH"]
LEFT, RIGHT, FORWARD, SEARCH = range(4)
OUTCOMES = ["MOVE", "BLOCK", "DARK", "LOCKED", "LAMP", "KEY", "NOTHING", "HURT", "OPEN", "WIN", "LOSE"]
MOVE, BLOCK, DARK, LOCKED, LAMP, KEY, NOTHING, HURT, OPEN, WIN, LOSE = range(11)
WALL = 255
START_LIVES = 3
ENDED = (WIN, LOSE)


def rng_byte(state: int) -> tuple[int, int]:
    """Eight steps of a 16-bit Galois LFSR (taps $B400). Returns (new_state, low byte)."""
    for _ in range(8):
        lsb = state & 1
        state >>= 1
        if lsb:
            state ^= 0xB400
    return state, state & 0xFF


@dataclass(frozen=True)
class World:
    seed: int
    exits: tuple[tuple[int, int, int], ...]  # exits[room] = (left, right, forward)
    lamp_room: int
    cycle: tuple[int, ...]
    rng: int


@dataclass(frozen=True)
class State:
    room: int = FOREST
    lives: int = START_LIVES
    key: bool = False
    lamp: bool = False
    turn: int = 0
    rng: int = 1
    done: bool = False


def gen_world(seed: int) -> World:
    rng = (seed & 0xFFFF) or 1
    order = [MARSH, RIVER, RUINS, SHRINE, CAVE]
    for i in range(4, 0, -1):
        rng, b = rng_byte(rng)
        j = b % (i + 1)
        order[i], order[j] = order[j], order[i]
    cycle = [FOREST, *order, GATE]
    cave_idx = cycle.index(CAVE)
    rng, b = rng_byte(rng)
    lamp_room = cycle[b % cave_idx]
    exits = [[WALL, WALL, WALL] for _ in range(8)]
    for i, room in enumerate(cycle):
        exits[room][FORWARD] = cycle[i + 1] if i < 6 else TOWER
        for side in (LEFT, RIGHT):
            rng, roll = rng_byte(rng)
            rng, pick = rng_byte(rng)
            target = cycle[pick % 7]
            exits[room][side] = WALL if (roll & 3) == 0 or target == room else target
    exits[GATE][LEFT] = FOREST
    # The room before the cave dead-ends without the lamp, so it always has a way back.
    if cave_idx > 1:
        exits[cycle[cave_idx - 1]][RIGHT] = FOREST
    return World(seed, tuple(tuple(e) for e in exits), lamp_room, tuple(cycle), rng)


def start(world: World) -> State:
    return State(rng=world.rng)


def inv_code(s: State) -> int:
    """0 = nothing, 1 = lamp only, 2 = lamp and key. The key needs the lamp, so no key-only state exists."""
    return 2 if s.key else (1 if s.lamp else 0)


def step(world: World, s: State, action: int) -> tuple[State, int]:
    """Apply a player action; returns (next_state, outcome). Pure: inputs are never mutated."""
    room, key, lamp, rng, out = s.room, s.key, s.lamp, s.rng, None
    if room == TOWER:
        out = WIN if action == FORWARD else HURT if action == SEARCH else BLOCK
    elif action == SEARCH:
        if room == world.lamp_room and not lamp:
            lamp, out = True, LAMP
        elif room == CAVE and not key:
            key, out = True, KEY
        elif room == RUINS:
            rng, b = rng_byte(rng)
            out = HURT if b & 7 == 0 else NOTHING
        else:
            out = NOTHING
    else:
        target = world.exits[room][action]
        if target == WALL:
            out = BLOCK
        elif target == CAVE and not lamp:
            out = DARK
        elif room == GATE and action == FORWARD:
            if key:
                room, out = TOWER, OPEN
            else:
                out = LOCKED
        else:
            hazard = False
            if target in (MARSH, RIVER):
                rng, b = rng_byte(rng)
                hazard = b & 7 == 0
            if hazard:
                out = HURT
            else:
                room, out = target, MOVE
    lives = s.lives
    if out == HURT:
        lives -= 1
        if lives == 0:
            out = LOSE
    return replace(s, room=room, key=key, lamp=lamp, rng=rng, lives=lives, turn=s.turn + 1,
                   done=out in ENDED), out


def solve(world: World) -> int | None:
    """Fewest-turn win ignoring hazards' RNG (they only slow a run; lives are checked by simulation)."""
    from collections import deque
    begin = (FOREST, False, False)
    seen, q = {begin}, deque([(begin, 0)])
    while q:
        (room, key, lamp), d = q.popleft()
        for a in range(4):
            if room == TOWER:
                if a == FORWARD:
                    return d + 1
                continue
            nroom, nkey, nlamp = room, key, lamp
            if a == SEARCH:
                if room == world.lamp_room:
                    nlamp = True
                if room == CAVE:
                    nkey = True
            else:
                t = world.exits[room][a]
                if t == WALL or (t == CAVE and not lamp) or (room == GATE and a == FORWARD and not key):
                    continue
                nroom = t
            n = (nroom, nkey, nlamp)
            if n not in seen:
                seen.add(n)
                q.append((n, d + 1))
    return None


def softlocked_states(world: World) -> list[tuple[int, bool, bool]]:
    """All reachable (room,key,lamp) states from which the tower can no longer be won."""
    from collections import deque

    def succ(st):
        room, key, lamp = st
        out = []
        for a in range(4):
            if room == TOWER:
                continue
            if a == SEARCH:
                out.append((room, key or room == CAVE, lamp or room == world.lamp_room))
                continue
            t = world.exits[room][a]
            if t == WALL or (t == CAVE and not lamp) or (room == GATE and a == FORWARD and not key):
                continue
            out.append((t, key, lamp))
        return out

    begin = (FOREST, False, False)
    seen, q = {begin}, deque([begin])
    while q:
        for n in succ(q.popleft()):
            if n not in seen:
                seen.add(n)
                q.append(n)
    bad = []
    for st in seen:
        inner, q2, ok = {st}, deque([st]), False
        while q2 and not ok:
            cur = q2.popleft()
            if cur[0] == TOWER:
                ok = True
                break
            for n in succ(cur):
                if n not in inner:
                    inner.add(n)
                    q2.append(n)
        if not ok:
            bad.append(st)
    return bad
