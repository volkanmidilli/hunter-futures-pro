import pytest

from hunter.config.loader import ConfigLoadError, _contains_secrets, validate_config
from hunter.config.models import HunterConfig


class TestValidateConfig:
    """validate_config must fail closed on unsafe configurations."""

    def test_safe_defaults_pass(self):
        config = HunterConfig()
        result = validate_config(config)
        assert result is config

    def test_trading_enabled_raises(self):
        config = HunterConfig()
        config.trading.enabled = True
        with pytest.raises(ConfigLoadError, match="trading.enabled must be False"):
            validate_config(config)

    def test_live_enabled_raises(self):
        config = HunterConfig()
        config.trading.live_enabled = True
        with pytest.raises(ConfigLoadError, match="trading.live_enabled must be False"):
            validate_config(config)

    def test_trading_and_live_enabled_raises(self):
        config = HunterConfig()
        config.trading.enabled = True
        config.trading.live_enabled = True
        with pytest.raises(ConfigLoadError):
            validate_config(config)

    def test_secret_api_key_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["trading"]["api_key"] = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)

    def test_secret_api_secret_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["trading"]["api_secret"] = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)

    def test_secret_secret_key_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["trading"]["secret_key"] = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)

    def test_secret_private_key_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["trading"]["private_key"] = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)

    def test_nested_secret_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["collection"]["extra"] = {"api_key": "secret123"}
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)

    def test_list_secret_raises(self):
        config = HunterConfig()
        config_dict = config.model_dump()
        config_dict["trading"]["extra_list"] = [{"api_key": "secret123"}]
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config, raw_dict=config_dict)


class TestContainsSecrets:
    """_contains_secrets detects secret keys in nested structures."""

    def test_detects_api_key_in_dict(self):
        assert _contains_secrets({"api_key": "secret"})

    def test_detects_api_secret_in_dict(self):
        assert _contains_secrets({"api_secret": "secret"})

    def test_detects_secret_key_in_dict(self):
        assert _contains_secrets({"secret_key": "secret"})

    def test_detects_private_key_in_dict(self):
        assert _contains_secrets({"private_key": "secret"})

    def test_detects_nested_secret(self):
        assert _contains_secrets({"nested": {"api_key": "secret"}})

    def test_detects_secret_in_list(self):
        assert _contains_secrets([{"api_key": "secret"}, {"safe": "ok"}])

    def test_no_secret_in_safe_dict(self):
        assert not _contains_secrets({"safe": "value", "level": "INFO"})

    def test_no_secret_in_empty_dict(self):
        assert not _contains_secrets({})


class TestLoadConfig:
    """load_config must load and validate safely."""

    def test_loads_default_config(self):
        from hunter.config.loader import load_config

        config = load_config()
        assert isinstance(config, HunterConfig)
        assert config.trading.enabled is False
        assert config.trading.live_enabled is False

    def test_loads_yaml_file_safely(self, tmp_path):
        from hunter.config.loader import load_config

        yaml_path = tmp_path / "safe.yaml"
        yaml_path.write_text(
            "logging:\n  level: DEBUG\n"
        )
        config = load_config(str(yaml_path))
        assert isinstance(config, HunterConfig)
        assert config.logging.level == "DEBUG"
        assert config.trading.enabled is False

    def test_rejects_yaml_with_trading_enabled(self, tmp_path):
        from hunter.config.loader import load_config

        yaml_path = tmp_path / "unsafe.yaml"
        yaml_path.write_text(
            "trading:\n  enabled: true\n"
        )
        with pytest.raises(ConfigLoadError, match="trading.enabled must be False"):
            load_config(str(yaml_path))

    def test_rejects_yaml_with_live_enabled(self, tmp_path):
        from hunter.config.loader import load_config

        yaml_path = tmp_path / "unsafe.yaml"
        yaml_path.write_text(
            "trading:\n  live_enabled: true\n"
        )
        with pytest.raises(ConfigLoadError, match="trading.live_enabled must be False"):
            load_config(str(yaml_path))

    def test_rejects_yaml_with_secrets(self, tmp_path):
        from hunter.config.loader import load_config

        yaml_path = tmp_path / "unsafe.yaml"
        yaml_path.write_text(
            "trading:\n  api_key: secret123\n"
        )
        with pytest.raises(ConfigLoadError, match="secret keys"):
            load_config(str(yaml_path))
