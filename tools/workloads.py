"""Fixed prompts used by the self-test ROM and the benchmarks. Same prompts for every variant."""
from reference.conversation import Situation

WORKLOADS = {
    "GREET": Situation("SMUG", "PEST", "NEW", "ONCE", "NONE", "GREET", "NONE"),
    "INSULT": Situation("ANGRY", "ENEMY", "RUDE", "ONCE", "NONE", "INSULT", "NONE"),
    "TECH": Situation("SMUG", "RIVAL", "NICE", "ONCE", "NAME", "TECH", "CPU"),
    "SHUTDOWN": Situation("WARY", "PEST", "MIXED", "AGAIN", "BOTH", "SHUTDOWN", "NONE"),
}
