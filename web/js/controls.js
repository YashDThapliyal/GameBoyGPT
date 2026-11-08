// Mouse, touch and keyboard input for the shell's buttons. Press and release go straight to the emulated joypad.
const KEYMAP = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", KeyX: "a", KeyA: "a", KeyZ: "b", KeyB: "b", Enter: "start", ShiftLeft: "select", ShiftRight: "select", Tab: "select" };

export function bindControls(root, getEmulator, onFirstInput) {
  const buttons = new Map();
  for (const el of root.querySelectorAll("[data-pad]")) buttons.set(el.dataset.pad, el);

  const set = (name, down) => {
    const el = buttons.get(name);
    if (el) el.classList.toggle("down", down);
    getEmulator()?.press(name, down);
    if (down) onFirstInput();
  };

  for (const [name, el] of buttons) {
    el.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      el.setPointerCapture(ev.pointerId);
      set(name, true);
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) el.addEventListener(type, () => set(name, false));
    el.addEventListener("contextmenu", (ev) => ev.preventDefault());
    el.addEventListener("keydown", (ev) => { if (ev.code === "Space") { ev.preventDefault(); set(name, true); } });
    el.addEventListener("keyup", (ev) => { if (ev.code === "Space") { ev.preventDefault(); set(name, false); } });
  }

  window.addEventListener("keydown", (ev) => {
    const name = KEYMAP[ev.code];
    if (!name || ev.metaKey || ev.ctrlKey || ev.altKey || ev.target.closest?.("input[type=text]")) return;
    if (ev.code === "Enter" && ev.target.closest?.("button:not([data-pad])")) return;
    ev.preventDefault();
    if (!ev.repeat) set(name, true);
  });
  window.addEventListener("keyup", (ev) => {
    const name = KEYMAP[ev.code];
    if (name) set(name, false);
  });
  window.addEventListener("blur", () => { for (const n of buttons.keys()) set(n, false); });
}
