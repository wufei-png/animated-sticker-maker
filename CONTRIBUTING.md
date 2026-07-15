# Contributing

Thanks for helping improve Animated Sticker Maker.

## Scope

Changes should strengthen the generic one-reference, one-prompt, one-sticker workflow. Keep character-specific assets, pack orchestration, account setup, and platform campaign decisions in their owning projects.

The repository intentionally maintains one Agent Skills instruction format. Put portable workflow rules in `SKILL.md`; keep `agents/openai.yaml` limited to optional interface metadata.

## Development setup

```bash
python -m pip install -r requirements.txt
python -m py_compile scripts/*.py
python -m unittest discover -s tests -v
```

## Pull requests

- Explain the production problem being solved and why it belongs in the generic Skill.
- Add or update focused tests for behavior changes.
- Preserve transactional packaging and artifact-fingerprint invalidation.
- Do not weaken `technical_validation`, `visual_validation`, or `deliverable_ready` gates.
- Keep platform limits out of the generic defaults; current limits must be verified from official sources at export time.
- Avoid adding a dependency when the standard library or existing Pillow/NumPy stack is sufficient.

Run the full test suite and `git diff --check` before submitting a pull request.
