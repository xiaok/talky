from pathlib import Path

from talky.config_store import AppConfigStore


def test_load_defaults_when_file_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = AppConfigStore(config_path)

    settings = store.load()

    assert settings.hotkey == "fn"
    assert settings.ollama_model == "qwen3.5:9b"
    assert settings.ollama_host == "http://127.0.0.1:11434"
    assert settings.custom_dictionary == []
    assert settings.llm_debug_stream is False


def test_save_and_reload_custom_dictionary(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = AppConfigStore(config_path)

    settings = store.load()
    settings.custom_dictionary = ["TensorRT", "Alice"]
    settings.hotkey = "right_option"
    settings.llm_debug_stream = True
    settings.ollama_host = "http://192.168.1.50:11434"
    store.save(settings)

    reloaded = store.load()

    assert reloaded.custom_dictionary == ["TensorRT", "Alice"]
    assert reloaded.hotkey == "right_option"
    assert reloaded.llm_debug_stream is True
    assert reloaded.ollama_host == "http://192.168.1.50:11434"
