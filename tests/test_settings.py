from pathlib import Path

import pytest

from llm_petrovaradinska_tvrdjava.settings import Settings


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FORTRESS_DEBUG", raising=False)
    (tmp_path / ".env").write_text("FORTRESS_DEBUG=true\n", encoding="utf-8")

    assert Settings.from_environment().debug is True
    monkeypatch.setenv("FORTRESS_DEBUG", "false")
    assert Settings.from_environment().debug is False
