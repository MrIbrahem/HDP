
# CLI

## Goal
Single entry point replacing `run.py` and `update.py`.

## Target files
- `src/hdp/cli.py`
- `src/hdp/__main__.py`  → calls `cli.main()`

## Commands

```text
python -m hdp generate [--sections ...] [--no-recent] [--last-edits] [--output PATH]
python -m hdp update   [--page TITLE] [--sections ...] [--no-recent] [--output PATH] [--test]
```

### Behaviour mapping

| Old | New |
|-----|-----|
| `run.py` | `generate` – build section tables from categories/sections, write `data/table.wiki` |
| `update.py` | `update` – load target page (`User:Mr. Ibrahem/hdp` or test page), refresh table cells, write output file |

## Suggested implementation
- Use `argparse` (stdlib only; keep the project light).
- Load dotenv + credentials once.
- Call `setup_logging` from `logging_setup`.
- Delegate all real work to `services.generate_tables` / `services.update_page_tables`.
- Default section list remains the three categories currently used in `run.py` / `update.py`.

Example skeleton:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hdp")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Build tables from categories/sections")
    gen.add_argument("--output", type=Path, default=Path("data/table.wiki"))
    # ... flags

    upd = sub.add_parser("update", help="Update tables inside a wiki page")
    upd.add_argument("--page", default="User:Mr. Ibrahem/hdp")
    upd.add_argument("--test", action="store_true")
    # ...

    args = parser.parse_args(argv)
    ...
    return 0
```

## Migration steps
1. Implement CLI against the new services while old scripts still work.
2. Document the new commands in the project README.
3. Delete or thin-wrap `run.py` / `update.py` once stable.
