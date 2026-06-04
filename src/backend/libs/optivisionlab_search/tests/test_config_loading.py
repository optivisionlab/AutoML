"""Tests for YAML config loading."""

import os

import pytest

from optivisionlab_search.strategy.base import SearchStrategy, _get_config_dir


class TestConfigDir:
    """Tests for config directory resolution."""

    def test_config_dir_exists(self):
        config_dir = _get_config_dir()
        assert os.path.isdir(config_dir), f"Config directory not found: {config_dir}"

    def test_base_config_exists(self):
        config_dir = _get_config_dir()
        assert os.path.isfile(os.path.join(config_dir, 'base_config.yml'))

    def test_grid_search_config_exists(self):
        config_dir = _get_config_dir()
        assert os.path.isfile(os.path.join(config_dir, 'grid_search_config.yml'))

    def test_bayesian_search_config_exists(self):
        config_dir = _get_config_dir()
        assert os.path.isfile(os.path.join(config_dir, 'bayesian_search_config.yml'))

    def test_genetic_algorithm_config_exists(self):
        config_dir = _get_config_dir()
        assert os.path.isfile(os.path.join(config_dir, 'genetic_algorithm_config.yml'))


class TestLoadYamlConfig:
    """Tests for SearchStrategy._load_yaml_config."""

    def test_load_base_config(self):
        config = SearchStrategy._load_yaml_config('base')
        assert isinstance(config, dict)
        assert len(config) > 0

    def test_load_grid_search_config(self):
        config = SearchStrategy._load_yaml_config('grid_search')
        assert isinstance(config, dict)
        assert 'parallel_evaluation' in config

    def test_load_bayesian_search_config(self):
        config = SearchStrategy._load_yaml_config('bayesian_search')
        assert isinstance(config, dict)
        assert 'n_calls' in config

    def test_load_genetic_algorithm_config(self):
        config = SearchStrategy._load_yaml_config('genetic_algorithm')
        assert isinstance(config, dict)
        assert 'population_size' in config

    def test_nonexistent_config_returns_empty(self):
        config = SearchStrategy._load_yaml_config('nonexistent_strategy')
        assert isinstance(config, dict)
        assert len(config) == 0

    def test_base_config_values(self):
        config = SearchStrategy._load_yaml_config('base')
        assert config.get('cv_n_splits') == 5
        assert config.get('cv_shuffle') is True
        assert config.get('n_jobs') == -1

    def test_default_config_fallback(self):
        """Test that default config files are used as fallback."""
        config_dir = _get_config_dir()
        # All strategies should have both config and default_config files
        for name in ['base', 'grid_search', 'bayesian_search', 'genetic_algorithm']:
            default_path = os.path.join(config_dir, f'{name}_default_config.yml')
            assert os.path.isfile(default_path), f"Missing default config: {default_path}"
