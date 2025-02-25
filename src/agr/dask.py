from dask_jobqueue.slurm import SLURMCluster
from distributed import Client
import logging

from agr.util import singleton

logger = logging.getLogger(__name__)


@singleton
class ClusterClientRegistry:
    def __init__(self, config):
        self._config = config
        self._clusters = {}
        self._clients = {}
        logger.info("ClusterClientRegistry.create")

    def get_client(self, tool_name: str) -> Client:
        tools_config = self._config.get("tools", {})
        tool_config = tools_config.get("default", {}) | (
            tools_config.get(tool_name, {})
        )
        cluster_name = tool_config["cluster"]
        if (client := self._clients.get(cluster_name)) is None:
            clusters_config = self._config.get("clusters", {})
            spec = clusters_config.get("default", {}).get("slurm", {}) | (
                clusters_config.get(cluster_name, {}).get("slurm", {})
            )
            adapt = clusters_config.get("default", {}).get("adapt", {}) | (
                clusters_config.get(cluster_name, {}).get("adapt", {})
            )
            print(
                f"get_client({tool_name}) cluster_name={cluster_name} spec={spec} adapt={adapt}"
            )
            cluster = SLURMCluster(**spec)
            _ = cluster.adapt(**adapt)
            client = Client(cluster)
            self._clusters[cluster_name] = cluster
            self._clients[cluster_name] = client
        return client

    def _tool_config(self, tool_name: str) -> dict:
        return self._config.get("tools", {}).get(tool_name, {})

    def _cluster_config(self, cluster_name: str) -> dict:
        clusters = self._config.get("clusters", {})
        return clusters.get("default", {}) | clusters.get(cluster_name, {})
