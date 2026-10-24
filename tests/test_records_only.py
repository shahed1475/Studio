"""R7: no module writes a video's record (`meta.json`) by hand. Everything goes through records.py (docs/architecture/05-target-design.md)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"records.py"}
# one line in the code that writes some OTHER json file under a variable that happens to be called meta, data or d
OTHER_FILES = ("SETTINGS.write_text", "SECRET.write_text", "_meta_file().write_text", "TOPICS_FILE.write_text", "REF_FILE.write_text", "PENDING_DOC.write_text",
               "STATE_FILE.write_text", "CONFIG_FILE.write_text", "_rejected_file().write_text", "FILE.write_text(json.dumps(d", "tmp.write_text(json.dumps(d", "STATE.write_text", "path.write_text(json.dumps(data", "(out / \"metadata.json\")")
PATTERNS = [re.compile(r'\(\s*\w*\s*/\s*"meta\.json"\s*\)\.write_text'), re.compile(r"\bmeta_path\.write_text"),
            re.compile(r"\.write_text\(\s*json\.dumps\(\s*(meta|data|d|fresh|r)\b")]


def test_no_module_writes_a_video_record_by_hand():
    offenders = []
    for f in sorted([*ROOT.glob("*.py"), *ROOT.glob("dashboard/*.py")]):
        if f.name in SKIP:
            continue
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if any(p.search(line) for p in PATTERNS) and not any(o in line for o in OTHER_FILES):
                offenders.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
    assert not offenders, "write records through records.py:\n" + "\n".join(offenders)


def test_the_patterns_catch_the_old_ways():
    for line in ['(folder / "meta.json").write_text(json.dumps(meta))', "meta_path.write_text(x)", "p.write_text(json.dumps(meta, indent=2))", "m.write_text(json.dumps(d))"]:
        assert any(p.search(line) for p in PATTERNS), line
