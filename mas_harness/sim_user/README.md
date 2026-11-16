# Simulated user

A simulated daycare manager answers the MAS's questions in headless runs instead of fixed answers:
accepting or re-planning, whether to run another optimisation round, the optional feedback, and
whether to retry once with a rewritten request.

* `SKILL.md`: the persona, a manager who knows the daycare domain but not optimisation technology.
  It is used unchanged as the persona's instructions.
* The harness adds what the manager is shown at each point (the MAS's messages and printed program
  output, never code) and the answer format.
