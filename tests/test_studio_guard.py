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


def test_commands_hidden_inside_other_commands_are_refused():
    for cmd in ("bash -c 'rm -rf /'", 'sh -c "rm -rf /etc"', "zsh -lc 'cd x && rm -rf ~'", "eval rm -rf /", "eval 'rm' '-rf' '/'", "ssh deploy@host 'rm -rf /home'",
                "ssh -p 2222 deploy@host rm -rf /", "bash -c \"bash -c 'rm -rf /'\"", "echo go | xargs rm -rf", "ls | xargs -n1 sudo rm -r", "sudo -u root rm -rf /",
                "env FOO=1 rm -rf /", "FOO=1 BAR=2 rm -rf /", "timeout -s KILL 5 rm -rf /", "nice -n 5 rm -rf /", "find / -delete", "find / -name x -exec rm -rf {} +",
                'echo "$(rm -rf /)"', "echo `rm -rf /`", "x=$(rm -rf ~)", "bash <<EOF\nrm -rf /\nEOF", "ssh host <<'EOF'\nrm -rf /\nEOF", "xargs bash -c 'rm -rf /'",
                "bash -c 'terraform apply'", "ssh host kubectl apply -f x.yaml"):
        code, why = run(cmd)
        assert code == 2 and why.startswith("Refused"), cmd


def test_quoting_tricks_do_not_hide_a_command_after_a_fake_here_document():
    for cmd in ("echo '<<X'\nrm -rf /\nX", 'echo "<<X"\nrm -rf /\nX', "echo $((1<<2))\nrm -rf /\n2", "echo <<<hi\nrm -rf /\nhi", "echo x # <<X\nrm -rf /\nX",
                "git commit -m 'a\n<<EOF\n'\nrm -rf /\nEOF"):
        assert run(cmd)[0] == 2, cmd


def test_a_command_that_cannot_be_read_is_refused_only_when_it_mentions_something_guarded():
    for cmd in ('echo "oops; rm -rf /', "echo 'oops; deploy/deploy.sh", 'bash -c "echo (; rm -rf /'):
        code, why = run(cmd)
        assert code == 2 and "could not be read" in why, cmd
    for cmd in ('echo "oops', "git commit -m 'unfinished", "ls (("):
        assert run(cmd)[0] == 0, cmd


def test_a_production_command_needs_its_own_dry_run_flag():
    for cmd in ("terraform apply # plan", "terraform apply && terraform plan", "kubectl apply -f x.yaml; echo --dry-run", "npm publish # --dry-run", "docker push img"):
        assert run(cmd)[0] == 2, cmd
    for cmd in ("kubectl apply -f x.yaml --dry-run=client", "npm publish --dry-run", "terraform plan", "kubectl diff -f x.yaml", "bash -c 'kubectl apply -f x --dry-run=server'"):
        assert run(cmd)[0] == 0, cmd


def test_harmless_wrapped_and_multiline_commands_still_run():
    for cmd in ("bash -c 'ls -la'", 'bash -c "rm -rf /tmp/claude-1000/scratch/x"', "ssh deploy@host 'docker ps'", "find . -name '*.pyc' -delete", "find /tmp/x -delete",
                "find . -name x | xargs rm -f", "xargs echo hi", "sudo -u fahad ls", "env FOO=1 ls", "echo $((1<<2))\nrm -rf build", 'git commit -m "line one\nline two: don\'t panic"',
                "git commit -m \"$(cat <<'EOF'\nfix: the rm -rf / guard (it's fine)\nsecond \"quoted\" line\nEOF\n)\"", "bash script.sh <<EOF\nls\nEOF",
                "cat <<EOF | bash\nls\nEOF"):
        assert run(cmd)[0] == 0, cmd


def test_other_spellings_of_the_root_are_refused_and_named_folders_are_not():
    for cmd in ("rm -rf //", "rm -rf /tmp/..", "rm -rf /./", "rm -rf /usr//", "rm -rf /home/../etc"):
        assert run(cmd)[0] == 2, cmd
    for cmd in ("rm -rf /tmp/claude-1000/x", "rm -rf /tmp//claude-1000/x/", "rm -rf /var/tmp/build"):
        assert run(cmd)[0] == 0, cmd


def test_review_round_two_bypasses_are_refused():
    for cmd in ("echo $((rm -rf /); echo)", "echo $(( rm -rf / ))", "bash -o pipefail -c 'rm -rf /'", "bash +o history -c 'rm -rf /'", "bash --norc -c 'rm -rf /'",
                "bash --rcfile x -c 'rm -rf /'", "kubectl apply -f x --dry-run=none", "kubectl apply -f x --dry-run=false", "terraform apply -dry-run=0",
                "find . -exec bash -c 'rm -rf /' \;", "find /tmp -execdir sh -c 'rm -rf ~' \;", "find / -exec rm -rf {} \;", "find / -ok rm -r {} \;"):
        assert run(cmd)[0] == 2, cmd
    for cmd in ("echo $((1+2))", "echo $(( (1+2)*3 ))", "bash -o pipefail -c 'ls'", "kubectl apply -f x --dry-run=client", "kubectl apply -f x --dry-run=server",
                "npm publish --dry-run", "find . -name x -exec rm -rf {} +", "find /tmp/x -exec rm -rf {} \;", "find . -exec ls {} \;"):
        assert run(cmd)[0] == 0, cmd


def test_review_round_three_bypasses_are_refused():
    for cmd in ('find / -exec sh -c "rm -rf {}" \;', "find / -exec bash -c 'rm -rf {}/..' \;", 'bash -xo pipefail -c "rm -rf /"', 'bash -eo pipefail -c "rm -rf /"',
                "bash -O extglob -c 'rm -rf /'", "sh -e -o errexit -c 'rm -rf /'", "echo $(( `rm -rf /` ))", "echo $(( 1 + `rm -rf ~` ))", "echo $(( $(rm -rf /) + 1 ))"):
        assert run(cmd)[0] == 2, cmd
    for cmd in ("find . -name x -exec sh -c 'echo {}' \;", "find /tmp/x -exec sh -c 'ls {}' \;", "bash -xo pipefail -c 'ls'", "bash script.sh arg", "echo $(( 1 + 2 ))",
                "echo $(( `echo 1` + 2 ))"):
        assert run(cmd)[0] == 0, cmd


def test_the_command_text_may_come_after_more_options_than_the_c_flag():
    for cmd in ("bash -c -o pipefail 'rm -rf /'", "bash -co pipefail 'rm -rf /'", "sh -c -e 'rm -rf /etc'"):
        assert run(cmd)[0] == 2, cmd
    assert run("bash -c -o pipefail 'ls'")[0] == 0
