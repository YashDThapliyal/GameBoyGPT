"""Story graph rules: no dead ends, every ending reachable, and early choices really change later options."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from reference import story as st


def test_no_state_is_a_dead_end():
    for s in st.reachable():
        scene = st.BY_ID[s.scene]
        if not scene.ending:
            assert st.available(s), f"no choices at {s}"


def test_every_scene_and_ending_is_reachable():
    seen = {s.scene for s in st.reachable()}
    assert seen == set(st.BY_ID), set(st.BY_ID) - seen


def test_every_run_ends():
    """The graph has no cycles, so no sequence of choices can go on forever."""
    def visit(sid, path):
        assert sid not in path, f"cycle through {sid}"
        for c in st.BY_ID[sid].choices:
            visit(c.next, path | {sid})
    visit(st.START, frozenset())


def test_items_change_what_you_can_do():
    with_lamp = st.State(scene="cave", flags=st.LAMP)
    without = st.State(scene="cave", flags=0)
    assert "Light the lamp" in [c.label for c in st.available(with_lamp)]
    assert "Light the lamp" not in [c.label for c in st.available(without)]
    keyless = [c.label for c in st.available(st.State(scene="gate"))]
    with_key = [c.label for c in st.available(st.State(scene="gate", flags=st.KEY))]
    assert "Use the key" in with_key and "Use the key" not in keyless


def test_every_ending_needs_different_earlier_choices():
    """Each ending must be reachable, and at least one must be impossible from a given Act 1 decision."""
    def endings_from(state):
        found, stack, seen = set(), [state], set()
        while stack:
            cur = stack.pop()
            if st.BY_ID[cur.scene].ending:
                found.add(cur.scene)
                continue
            for c in st.available(cur):
                n = st.step(cur, c)
                key = (n.scene, n.flags, n.wounds)
                if key not in seen:
                    seen.add(key)
                    stack.append(n)
        return found

    cursed = endings_from(st.State(scene="fork", flags=st.CURSED))
    friend = endings_from(st.State(scene="fork", flags=st.FRIEND))
    assert "end_bound" in cursed
    assert "end_bound" not in friend, "only the ring path reaches the ring ending"
    assert len(endings_from(st.State())) == 8


def test_labels_fit_the_screen():
    for s in st.SCENES:
        assert len(s.title) <= 11
        for c in s.choices:
            assert len(c.label) <= 18, c.label
        assert len(st.available(st.State(scene=s.id, flags=31))) <= 4 or s.ending


def test_no_scene_forces_a_single_choice():
    for s in st.reachable():
        if not st.BY_ID[s.scene].ending:
            assert len(st.available(s)) >= 2, (s, [c.label for c in st.available(s)])


def test_menu_never_needs_more_than_four_rows():
    assert max(len(st.available(s)) for s in st.reachable()) <= 4


def test_three_wounds_kill():
    s = st.State(scene="fork", wounds=2)
    bridge = next(c for c in st.available(s) if c.danger)
    assert st.step(s, bridge).scene == st.DEATH_SCENE
