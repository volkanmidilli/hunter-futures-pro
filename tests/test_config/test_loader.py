import pytest

from hunter.config.loader import ConfigLoadError, validate_config
from hunter.config.models import HunterConfig, TradingConfig


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
        config.trading.api_key = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)

    def test_secret_api_secret_raises(self):
        config = HunterConfig()
        config.trading.api_secret = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)

    def test_secret_secret_key_raises(self):
        config = HunterConfig()
        config.trading.secret_key = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)

    def test_secret_private_key_raises(self):
        config = HunterConfig()
        config.trading.private_key = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)

    def test_nested_secret_raises(self):
        config = HunterConfig()
        config.collection.api_key = "secret123"
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)

    def test_list_secret_raises(self):
        config = HunterConfig()
        config.trading.secrets = ["api_key", "secret_value"]
        with pytest.raises(ConfigLoadError, match="secret keys"):
            validate_config(config)


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
