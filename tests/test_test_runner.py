from src import test_runner


def test_run_tests_forwards_arguments(monkeypatch):
    recorded = {}

    def fake_main(args):
        recorded["args"] = args
        return 0

    monkeypatch.setattr(test_runner.pytest, "main", fake_main)

    exit_code = test_runner.run_tests(["-k", "sample"])

    assert exit_code == 0
    assert recorded["args"] == ["-k", "sample"]


def test_run_default_uses_quiet_option(monkeypatch):
    captured = {}

    def fake_main(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(test_runner.pytest, "main", fake_main)

    exit_code = test_runner.run_default()

    assert exit_code == 0
    assert captured["args"] == list(test_runner.DEFAULT_PYTEST_ARGS)
