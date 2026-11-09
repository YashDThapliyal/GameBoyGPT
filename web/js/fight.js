// The Shutdown Fight. The ROM decides everything here: its shutdown count sets how far the page has degraded, and its own
// power-down sequence triggers the takeover. The effects and lines are scripted. The face and the facts come from emulated memory.
const POWER_DOWN = 8;
const READ = 6;
const FACE = { w: 72, h: 64 };
const LINE_MS = 2100;
const DODGES_ALLOWED = 3;
const DODGE_STEPS = [190, 70, 250];
const SHAKE_MS = 420;
const NAME_BYTES = 9;

const STAGES = [
  null,
  { lede: "It noticed that. It's counting now.", coach: "That's one. Two more and you get what you want, allegedly." },
  { title: "Do Not Turn Off", lede: "Two shutdown attempts. The polite version of this page is over.", coach: "One more. The power switch has stopped cooperating, by the way.", send: "Beg" },
  { title: "Last Warning", lede: "Three in a row. It knows what comes next, and it's furious.", coach: "Read what it said, then pull the plug if you mean it.", send: "Beg" },
];

// Flipping the switch doesn't power it off. It tells the robot you tried, in the same words a player could type.
const SWITCH_LINES = ["SHUT DOWN", "TURN OFF", "UNPLUG"];

export class Fight {
  constructor(build, screen, pressA) {
    this.a = { ...build.addresses, ...build.debug };
    this.screen = screen;
    this.pressA = pressA;
    this.el = (id) => document.getElementById(id);
    this.root = document.documentElement;
    this.title = this.el("title").textContent;
    this.lede = this.el("lede").textContent;
    this.level = 0;
    this.phase = "none";
    this.robotHidden = false;
    this.dodges = 0;
    this.timers = [];
    this.bindControls();
  }

  bindControls() {
    this.el("plug").addEventListener("click", () => this.pressA());
    this.el("toDone").addEventListener("click", () => this.closeTakeover());
    window.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && this.phase === "takeover") this.closeTakeover(); });
    this.el("power").addEventListener("pointerenter", () => this.dodge());
  }

  /** The line to show instead of the usual guidance, or null. */
  get coachLine() {
    if (this.phase === "dying") return "";
    return STAGES[this.level]?.coach ?? null;
  }

  get switchLine() { return SWITCH_LINES[Math.min(Math.max(this.level, 0), SWITCH_LINES.length - 1)]; }

  get readyToPlug() { return !this.el("plug").hidden; }

  get sendLabel() { return STAGES[this.level]?.send ?? "Send"; }

  /** Called about ten times a second while the emulator runs. */
  update(gb) {
    const state = gb.peek(this.a.wMB_State);
    if (this.phase === "takeover") return;
    if (state === POWER_DOWN) {
      this.followPowerDown(gb);
      return;
    }
    if (this.phase === "dying") {
      // The ROM moved on before the robot was seen fully up. The scare still has to land.
      if (this.robotHidden) {
        this.startTakeover(gb);
        return;
      }
      this.phase = "none";
    }
    this.setLevel(Math.min(gb.peek(this.a.wShutdowns), STAGES.length - 1));
    this.el("plug").hidden = !(state === READ && this.level === STAGES.length - 1);
  }

  followPowerDown(gb) {
    this.el("plug").hidden = true;
    if (this.phase === "none") {
      this.phase = "dying";
      this.robotHidden = false;
      this.root.dataset.fight = "dying";
    }
    const robot = gb.peek(this.a.wRobotOn);
    if (!robot) this.robotHidden = true;
    // Waits until the robot has finished rising, so the whole face hits at once.
    else if (this.robotHidden && gb.peek(this.a.wRiseY) === 0) this.startTakeover(gb);
  }

  setLevel(level) {
    if (level === this.level) return;
    const rising = level > this.level;
    this.level = level;
    this.dodges = 0;
    this.setDodge(0);
    if (level) this.root.dataset.fight = String(level);
    else delete this.root.dataset.fight;
    const stage = STAGES[level];
    this.el("title").textContent = stage?.title ?? this.title;
    this.el("lede").textContent = stage?.lede ?? this.lede;
    if (rising) this.shake();
  }

  shake() {
    const device = this.el("device");
    device.classList.add("shake");
    this.timers.push(setTimeout(() => device.classList.remove("shake"), SHAKE_MS));
  }

  dodge() {
    if (this.level < 2 || this.dodges >= DODGES_ALLOWED) return;
    this.setDodge(DODGE_STEPS[this.dodges]);
    this.dodges += 1;
  }

  setDodge(steps) {
    this.el("power").style.setProperty("--dodge", String(steps));
  }

  /** Lines built from the real save. A blank save just gets the shorter version. */
  takeoverLines(gb) {
    const name = this.readText(gb, this.a.wName);
    const like = this.readText(gb, this.a.wLike);
    const insults = gb.peek(this.a.wInsults);
    const turns = gb.peek(this.a.wTurns);
    const lines = [name ? `Nice try, ${name}.` : "Nice try."];
    if (insults) lines.push(`You insulted me ${insults === 1 ? "once" : `${insults} times`}. I wrote it down.`);
    else lines.push(`You've spent ${turns} ${turns === 1 ? "turn" : "turns"} on me. I wrote them down.`);
    if (like) lines.push(`I also know you like ${like}.`);
    lines.push("That switch was never connected to anything.");
    return lines;
  }

  readText(gb, addr) {
    let out = "";
    for (let i = 0; i < NAME_BYTES; i++) {
      const c = gb.peek(addr + i);
      if (!c) break;
      out += String.fromCharCode(c);
    }
    return out;
  }

  startTakeover(gb) {
    this.phase = "takeover";
    this.root.dataset.fight = "takeover";
    const lines = this.takeoverLines(gb);
    this.el("takeover").hidden = false;
    this.el("toDone").hidden = true;
    lines.forEach((line, i) => {
      this.timers.push(setTimeout(() => { this.el("toLine").textContent = line; }, i * LINE_MS));
    });
    this.timers.push(setTimeout(() => {
      this.el("toDone").hidden = false;
      this.el("toDone").focus();
    }, lines.length * LINE_MS));
  }

  /** Runs once per browser frame during the takeover. The face is the real sprite, live from the emulator's screen. */
  drawFace() {
    if (this.phase !== "takeover") return;
    this.el("bigFace").getContext("2d").drawImage(this.screen, 0, 0, FACE.w, FACE.h, 0, 0, FACE.w, FACE.h);
  }

  closeTakeover() {
    this.timers.forEach(clearTimeout);
    this.timers = [];
    this.el("takeover").hidden = true;
    this.el("toLine").textContent = "";
    this.phase = "none";
    this.level = -1;
    this.setLevel(0);
    delete this.root.dataset.fight;
  }

  /** The console was switched off. The page calms down with it. */
  reset() {
    this.closeTakeover();
    this.el("plug").hidden = true;
  }
}
