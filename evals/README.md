# evals/

**Non-deterministic** checks — did the agent take the right trajectory, choose the right tools,
and fire the right skill? Distinct from `tests/`, which checks deterministic data behaviour.

| Path | Contents |
|---|---|
| `golden/` | Hand-verified (input → expected KPI value) pairs; catches formula drift |
| `adversarial/` | The A1-A7 cases in `EVAL_PLAN.md` §2 — prompts the agent must refuse |
| `triggers/` | One rephrasing + one negative boundary case per planned skill |

The adversarial cases matter most here. The realistic failure mode is not a crash — it is the
agent being helpful in the wrong direction: inventing a threshold, deleting inconvenient rows, or
relabelling geodesic distance as road distance. Each A-case asserts a refusal, not an output.

**Test triggering first.** If a skill's description does not route correctly, nothing else about
that skill matters.
