from functools import cached_property, lru_cache
from subprocess import PIPE

from agr.util import StdioRedirect
from agr.gquery import GQuery, GQueryNotFoundException, Predicates


class Stage1(object):
    def __init__(self, run_name: str):
        self._run_name = run_name

    @cached_property
    def libraries(self) -> list[str]:
        with StdioRedirect(stdout=PIPE) as lab_report:
            try:
                GQuery(
                    task="lab_report",
                    # Libraries are queried as samples 😩
                    predicates=Predicates(name="illumina_run_details", samples=True),
                    items=[self._run_name],
                ).run()
            except GQueryNotFoundException:
                return []
            assert lab_report.stdout is not None  # because PIPE
            return lab_report.stdout.readlines()

    @lru_cache
    def cohorts(self, library) -> list[str]:
        with StdioRedirect(stdout=PIPE) as lab_report:
            try:
                GQuery(
                    task="lab_report",
                    # Libraries are queried as samples 😩
                    predicates=Predicates(
                        name="illumina_run_details", cohorts=True, sample_id=library
                    ),
                    items=[self._run_name],
                ).run()
            except GQueryNotFoundException:
                return []
            assert lab_report.stdout is not None  # because PIPE
            return lab_report.stdout.readlines()


def _flowcell_id(run: str) -> str:
    return run.split("_")[3][1:]
