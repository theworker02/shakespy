from __future__ import annotations

import json

from shakespy import cli


def test_normalize_argv_preserves_legacy_direct_text_mode():
    assert cli.normalize_argv(["You", "are", "ready."]) == [
        "translate",
        "You",
        "are",
        "ready.",
    ]


def test_main_translates_direct_text_without_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(cli, "translate", lambda text: f"<{text}>")

    exit_code = cli.main(["You are ready."])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "<You are ready.>\n"


def test_glossary_json_output(capsys):
    exit_code = cli.main(["glossary", "--phrases", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert any(item["source"] == "good morning" for item in payload)


def test_batch_writes_translated_output(monkeypatch, tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    source_file = source_dir / "speech.txt"
    source_file.write_text("Hello there", encoding="utf-8")
    output_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "translate", lambda text: text.upper())

    exit_code = cli.main(
        [
            "batch",
            str(source_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    output_file = output_dir / "speech.eme.txt"
    assert exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "HELLO THERE"


def test_translate_can_write_json_to_file(monkeypatch, tmp_path):
    destination = tmp_path / "translated.json"
    monkeypatch.setattr(cli, "translate", lambda text: "bardic")

    exit_code = cli.main(
        [
            "translate",
            "plain text",
            "--json",
            "--output-file",
            str(destination),
        ]
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["translated"] == "bardic"
