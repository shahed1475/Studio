import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).parent.parent / ".claude" / "hooks" / "studio_guard.py"


def run(command):
    p = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}), capture_output=True, text=True)
    return p.returncode, p.stderr


def test_destructive_commands_are_refused_with_a_reason():
    for cmd in ("rm -rf /", "sudo rm -rf ~", "rm -rf $HOME/*", "cd x && rm -rf /", "rm -r -f /etc", "ls; rm -rf /*", "rm -rf *", "DROP DATABASE prod",
                "psql -c 'TRUNCATE TABLE users'", "psql -c 'DELETE FROM users'", ":(){ :|:& };:", "rm --recursive --force /home"):
        code, why = run(cmd)
        assert code == 2 and why.startswith("Refused"), cmd


def test_named_folders_quoted_text_and_heredoc_bodies_are_not_mistaken_for_the_command():
    for cmd in ("rm -rf /tmp/claude-1000/scratch/clean", "rm -r build", "rm file.txt", "echo 'never run rm -rf /'", 'grep "rm -rf /" notes.txt', "git log --oneline",
                'psql -c "DELETE FROM users WHERE id = 1"', "cat > note.md <<'EOF'\nrm -rf /\nDROP DATABASE x\nTRUNCATE TABLE y\nEOF\necho done",
                "python3 - <<EOF\nprint('rm -rf /')\nEOF"):
        assert run(cmd)[0] == 0, cmd


def test_a_production_deploy_must_preview_first_and_the_documented_forms_pass():
    assert run("STUDIO_VPS=deploy@vps-ai deploy/deploy.sh")[0] == 2
    assert run("STUDIO_VPS=deploy@vps-ai timeout 250 deploy/deploy.sh 2>&1 | tail -3")[0] == 2
    for cmd in ("STUDIO_VPS=deploy@vps-ai deploy/deploy.sh dry-run-first  # dry-run preview first", "deploy/deploy.sh safe", "deploy/deploy.sh dry", "deploy/deploy.sh dry && deploy/deploy.sh",
                "deploy/deploy.sh first", "bash -n deploy/deploy.sh", "git add deploy/deploy.sh", "cat deploy/deploy.sh | head -3", "grep -n dry deploy/deploy.sh"):
        assert run(cmd)[0] == 0, cmd
    assert run("kubectl apply -f x.yaml")[0] == 2 and run("kubectl apply -f x.yaml --dry-run=server")[0] == 0 and run("npm publish")[0] == 2 and run("terraform plan")[0] == 0


def test_an_unreadable_input_is_never_a_reason_to_block():
    p = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True)
    assert p.returncode == 0
    assert run("")[0] == 0
