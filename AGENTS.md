# Repository guidance

- Treat `SKILL.md` as the portable workflow contract and keep a single Agent Skills instruction format.
- Keep `agents/openai.yaml` limited to optional interface and invocation metadata.
- Keep subject-specific assets, pack orchestration, and one-off production logic out of this repository.
- Resolve scripts and references relative to the repository-root `SKILL.md`.
- Preserve transactional packaging, artifact fingerprints, and the separate `technical_validation` / `visual_validation` gates.
- Run `python -m py_compile scripts/*.py`, `python -m unittest discover -s tests -v`, and `git diff --check` before committing.
