"""World rules: every seed solvable, no softlocks, hazards bounded, and transitions keep invariants."""
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reference import game as g


def test_lfsr_known_sequence_and_nonzero():
    s, b = g.rng_byte(1)
    assert s != 0 and 0 <= b <= 255
    seen = set()
    x = 1
    for _ in range(2000):
        x, _b = g.rng_byte(x)
        assert x != 0
        seen.add(x)
    assert len(seen) == 2000


def test_all_seeds_solvable_and_no_softlock():
    for seed in range(0, 65536, 37):  # 1772 seeds spanning the whole space
        w = g.gen_world(seed)
        assert g.solve(w) is not None, seed
        assert g.softlocked_states(w) == [], seed


def test_cave_precedes_nothing_required():
    for seed in range(500):
        w = g.gen_world(seed)
        cave = w.cycle.index(g.CAVE)
        assert w.lamp_room in w.cycle[:cave]
        assert w.exits[g.GATE][g.FORWARD] == g.TOWER
        assert w.exits[g.GATE][g.LEFT] == g.FOREST


def test_100_seed_random_play_terminates_with_valid_transitions():
    wins = losses = 0
    for seed in range(100):
        w, rnd = g.gen_world(seed), random.Random(seed)
        s = g.start(w)
        for _ in range(4000):
            a = rnd.randrange(4)
            n, out = g.step(w, s, a)
            assert s.turn + 1 == n.turn and 0 <= n.lives <= g.START_LIVES
            assert n.key >= s.key and n.lamp >= s.lamp
            assert not n.key or n.lamp
            if out == g.DARK:
                assert not s.lamp and n.room == s.room
            if out in (g.LOCKED, g.BLOCK, g.NOTHING):
                assert n.room == s.room
            s = n
            if s.done:
                wins += out == g.WIN
                losses += out == g.LOSE
                break
        assert s.done, seed
    assert wins + losses == 100


def test_step_is_pure():
    w = g.gen_world(7)
    s = g.start(w)
    a, _ = g.step(w, s, g.SEARCH)
    b, _ = g.step(w, s, g.SEARCH)
    assert a == b and s == g.start(w)
