# README artwork

`work-notes.gif` is a 6.4-second looping illustration of recorded work producing two views. It is conceptual artwork, not a screenshot or a claim of complete automatic capture. Its text remains static; only record highlights and signals move.

`work-notes-poster.png` is the static alternative. The main README selects it for readers requesting reduced motion and also links to it explicitly.

Regenerate both assets from the repository root in a development environment with **Pillow 12 or later**:

```sh
python3 tools/render_readme.py
```

The generator uses locally available Arial/Menlo on macOS or DejaVu on Linux, falling back to Pillow's default font. Fonts are not bundled. Pass `--font`, `--bold-font`, and `--mono-font` to choose other local font files. Different fonts can alter layout; inspect both outputs after regenerating.

Pillow is only an optional artwork dependency. The installed skills still use Python's standard library alone.
