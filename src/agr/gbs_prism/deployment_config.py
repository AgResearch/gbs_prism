import json
import os
import _jsonnet

from agr.util import singleton


@singleton
class DeploymentConfig:
    def __init__(self):
        DEPLOYMENT_CONFIG_PATH_ENV = "GBS_PRISM_DEPLOYMENT_CONFIG"
        assert (
            DEPLOYMENT_CONFIG_PATH_ENV in os.environ
        ), f"Missing environment variable {DEPLOYMENT_CONFIG_PATH_ENV}"
        config_path = os.environ[DEPLOYMENT_CONFIG_PATH_ENV]
        with open(config_path, "r") as config_f:
            raw_config = config_f.read()
            json_config = _jsonnet.evaluate_snippet(config_path, raw_config)
            self._config = json.loads(json_config)
            print(f"loaded deployment config {self._config}")

    @property
    def config(self):
        return self._config


def get_deployment_config() -> DeploymentConfig:
    return DeploymentConfig().config
