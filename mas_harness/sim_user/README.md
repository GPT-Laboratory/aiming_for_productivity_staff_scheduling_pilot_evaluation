# Simulated user

A simulated daycare manager answers the MAS's questions in headless runs instead of fixed answers:
accepting or re-planning, whether to run another optimisation round, the optional feedback, and
whether to retry once with a rewritten request.

* `SKILL.md`: the persona, a manager who knows the daycare domain but not optimisation technology.
  It is used unchanged as the persona's instructions.
* `sim_user.py`: the persona client. It adds a scenario block to SKILL.md. The block fixes the
  facts to the request and the files, and allows no new requirements or complications. It also
  says the persona cannot read code, and that it gets one chat plus one retry. Only the MAS's
  messages (code removed) and the program's printed output are shown to the persona, never code
  or the checkers. Its conversation is saved as `sim_user.json`.
* `../sim_trial.py`: one trial of the MAS, with a first chat and at most one retry, decided by the
  persona. Free-text feedback reaches the MAS only with the evaluation patch applied.
* `direct_llm.py --sim-user`: the persona reviews each format-valid answer and accepts it or asks
  for a revision (at most 3).

```bash
MAS_DIR=$PWD/mas2024 uv run --no-project --python 3.11 --with-requirements requirements.txt \
    mas_harness/sim_trial.py datasets/C_reconstructed C_mas_sim_r01
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py C 3 --sim-user --tag _sim
```

The persona model is `SIM_USER_MODEL` (default `openai/gpt-6.1-terra-pro`).
