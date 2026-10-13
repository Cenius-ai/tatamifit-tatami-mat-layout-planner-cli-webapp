"""The unattended-terminal fallback: an idle first prompt must not hang forever."""

import io

import tatamifit


def test_idle_first_prompt_prints_the_usage_summary_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(tatamifit, "is_tty", lambda stream: True)
    monkeypatch.setattr(tatamifit, "wait_for_input", lambda stream, timeout: False)
    monkeypatch.setattr(tatamifit.sys, "stdin", io.StringIO(""))
    assert tatamifit.main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("TatamiFit")
    assert "Usage:" in out and "--help" in out and "demo.sh" in out


def test_wait_for_input_never_blocks_a_pipe():
    assert tatamifit.wait_for_input(io.StringIO("3.64\n"), 0.01) is True


def test_empty_piped_input_still_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(tatamifit.sys, "stdin", io.StringIO(""))
    assert tatamifit.main([]) == 1
    assert capsys.readouterr().err.strip() == "no plan produced"
