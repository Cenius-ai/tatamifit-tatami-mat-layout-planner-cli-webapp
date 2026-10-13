"""T1 / T2 / T7: the end-to-end CLI contract, exit codes and piped stdin."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tatamifit.py")


def run(stdin="", args=()):
    return subprocess.run([sys.executable, SCRIPT, *list(args)],
                          input=stdin, capture_output=True, text=True)


def test_piped_room_prints_the_whole_page_and_exits_zero():
    proc = run("3.64\n2.73\n\n")
    assert proc.returncode == 0
    assert proc.stderr == ""
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("TatamiFit") and "0.455" in lines[0]
    assert "Width (m) 0.91-17.745, e.g. 3.64: " in proc.stdout
    assert "Depth (m) 0.91-7.28, e.g. 2.73: " in proc.stdout
    assert "Room: 3.64 m x 2.73 m -> usable grid 8 x 6 half-units" in proc.stdout
    assert "H = long-along-width, V = long-along-depth" in proc.stdout
    assert "Ranked options" in proc.stdout
    assert any(line.startswith("+---") for line in lines)


def test_two_runs_are_byte_identical():
    first = run("3.70\n2.90\n\n").stdout
    second = run("3.70\n2.90\n\n").stdout
    assert first == second and first != ""
    for _ in range(3):
        assert run("3.70\n2.90\n\n").stdout == first


def test_invalid_width_is_reasked_once_and_only_that_field():
    proc = run("abc\n3.64\n2.73\n\n")
    assert proc.returncode == 0
    assert proc.stdout.count("Try again: ") == 1
    assert "'abc' is not a number of metres" in proc.stdout
    assert proc.stdout.count("Width (m)") == 2
    assert "Room: 3.64 m x 2.73 m" in proc.stdout


def test_negative_width_is_rejected():
    proc = run("-3.64\n3.64\n2.73\n\n")
    assert proc.returncode == 0
    assert "Try again: enter a positive number of metres" in proc.stdout


def test_confirm_reask_echoes_the_retained_depth():
    proc = run("3.64\n2.73\nd\n\n\n")
    assert proc.returncode == 0
    assert "Depth (m) [2.73]: " in proc.stdout
    assert "3.64 m x 2.73 m" in proc.stdout


def test_confirm_reask_can_change_the_width_and_keep_the_depth():
    proc = run("3.64\n2.73\nw\n3.70\n\n")
    assert proc.returncode == 0
    assert "Width (m) [3.64]: " in proc.stdout
    assert "3.70 m x 2.73 m" in proc.stdout


def test_empty_first_depth_answer_is_invalid_and_not_bracketed():
    proc = run("3.64\n\n2.73\n\n")
    assert proc.returncode == 0
    assert proc.stdout.count("Try again: enter a number of metres, e.g. 2.73") == 1
    assert proc.stdout.count("Depth (m) 0.91-7.28, e.g. 2.73: ") == 2
    assert "Depth (m) [" not in proc.stdout


def test_empty_stdin_banners_then_exits_one():
    proc = run("")
    assert proc.returncode == 1
    assert proc.stdout.splitlines()[0].startswith("TatamiFit")
    assert proc.stderr.strip() == "no plan produced"
    assert "+---" not in proc.stdout


def test_eof_at_the_depth_prompt_exits_one_without_a_diagram():
    proc = run("3.64\n")
    assert proc.returncode == 1
    assert proc.stderr.strip() == "no plan produced"
    assert "+---" not in proc.stdout


def test_too_small_room_is_refused_with_exit_two():
    proc = run("1.20\n0.80\n\n")
    assert proc.returncode == 2
    assert "1.20 m x 0.80 m is too small for a single 0.91 m x 1.82 m tatami." in proc.stdout
    assert "+---" not in proc.stdout
    assert proc.stdout.count("Try again") == 0


def test_too_large_room_is_refused_with_exit_two():
    proc = run("20.00\n20.00\n\n")
    assert proc.returncode == 2
    assert "39 x 16" in proc.stdout and "17.745" in proc.stdout
    assert "+---" not in proc.stdout


def test_no_output_line_exceeds_eighty_columns():
    for stdin_text in ("3.70\n2.90\n\n", "17.745\n7.28\n\n", "20.00\n20.00\n\n", "1.20\n0.80\n\n"):
        proc = run(stdin_text)
        for line in proc.stdout.splitlines():
            assert len(line) <= 80, (stdin_text, line)


def test_boundary_room_renders_one_labelled_mat():
    proc = run("1.00\n1.90\n\n")
    assert proc.returncode == 0
    assert "usable grid 2 x 4 half-units" in proc.stdout
    body = [line for line in proc.stdout.splitlines() if line.startswith("|")]
    assert len(body) == 4
    assert sum(line.count("V") for line in body) == 1
    assert body[0] == "|V1..|"


def test_help_and_version():
    helped = run(args=("--help",))
    assert helped.returncode == 0
    assert "Usage:" in helped.stdout and "--version" in helped.stdout
    assert "0.455" in helped.stdout
    version = run(args=("--version",))
    assert version.returncode == 0
    assert version.stdout.strip() == "TatamiFit 1.0.0"


def test_unknown_option_exits_two_with_usage_on_stderr():
    proc = run(args=("--width=3.64",))
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "unknown option" in proc.stderr and "--help" in proc.stderr
