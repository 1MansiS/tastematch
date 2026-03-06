import json
import os

import pytest

from llm.factory import get_provider
from llm.ollama import OllamaProvider
from llm.groq import GroqProvider
from llm.gemini import GeminiProvider


# --- ollama ---

def test_get_provider_ollama(tmp_path):
    config = {
        "llm": {
            "provider": "ollama",
            "text_model": "llama3.1:8b",
            "vision_model": "llama3.2-vision:11b",
            "base_url": "http://localhost:11434",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    provider = get_provider(str(config_file))
    assert isinstance(provider, OllamaProvider)


def test_get_provider_ollama_correct_models(tmp_path):
    config = {
        "llm": {
            "provider": "ollama",
            "text_model": "llama3.1:8b",
            "vision_model": "llama3.2-vision:11b",
            "base_url": "http://myhost:11434",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    provider = get_provider(str(config_file))
    assert provider.text_model == "llama3.1:8b"
    assert provider.vision_model == "llama3.2-vision:11b"
    assert provider.base_url == "http://myhost:11434"


def test_get_provider_vision_defaults_to_text_model(tmp_path):
    config = {
        "llm": {
            "provider": "ollama",
            "text_model": "llama3.1:8b",
            "base_url": "http://localhost:11434",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    provider = get_provider(str(config_file))
    assert provider.vision_model == "llama3.1:8b"


# --- groq ---

def test_get_provider_groq(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    config = {
        "llm": {
            "provider": "groq",
            "text_model": "llama-3.1-8b-instant",
            "vision_model": "llama-3.2-11b-vision-preview",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    provider = get_provider(str(config_file))
    assert isinstance(provider, GroqProvider)
    assert provider.text_model == "llama-3.1-8b-instant"
    assert provider.vision_model == "llama-3.2-11b-vision-preview"


def test_get_provider_groq_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config = {"llm": {"provider": "groq", "text_model": "llama-3.1-8b-instant"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
        get_provider(str(config_file))


# --- gemini ---

def test_get_provider_gemini(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    config = {
        "llm": {
            "provider": "gemini",
            "text_model": "gemini-1.5-flash",
            "vision_model": "gemini-1.5-flash",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    provider = get_provider(str(config_file))
    assert isinstance(provider, GeminiProvider)
    assert provider.text_model == "gemini-1.5-flash"


def test_get_provider_gemini_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = {"llm": {"provider": "gemini", "text_model": "gemini-1.5-flash"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
        get_provider(str(config_file))


# --- unknown ---

def test_get_provider_unknown_raises(tmp_path):
    config = {"llm": {"provider": "nonexistent", "text_model": "foo"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    with pytest.raises(ValueError, match="Unsupported provider"):
        get_provider(str(config_file))
