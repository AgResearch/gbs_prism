from functools import cached_property, lru_cache
import logging
import tempfile

from agr.util import StdioRedirect, Singleton
from agr.gquery import GQuery, GQueryNotFoundException, Predicates

from .cohort import Cohort, TargetConfig
from .paths import GbsPaths

logger = logging.getLogger(__name__)


# This class wants to be a singleton, but SnakeMake apparently won't allow it
class Cohorts(metaclass=Singleton):
    """All cohorts for the run"""

    def __init__(self, run_name: str):
        self._run_name = run_name
        logger.debug("Cohorts(%s) object created" % self._run_name)

    @property
    def run_name(self) -> str:
        return self._run_name

    @cached_property
    def all_names(self) -> list[str]:
        return list(self.by_name.keys())

    @cached_property
    def all(self) -> list[Cohort]:
        return list(self.by_name.values())

    @cached_property
    def by_name(self) -> dict[str, Cohort]:
        return dict(
            [
                (cohort.name, cohort)
                for library in self.libraries
                for cohort in self._cohorts_for_library(library)
            ]
        )

    @cached_property
    def libraries(self) -> list[str]:
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                try:
                    GQuery(
                        task="lab_report",
                        # Libraries are queried as samples 😩
                        predicates=Predicates(
                            name="illumina_run_details", samples=True
                        ),
                        items=[self._run_name],
                    ).run()
                except GQueryNotFoundException:
                    return []
            _ = tmp_f.seek(0)
            return [line.strip() for line in tmp_f.readlines()]

    def _cohorts_for_library(self, library: str) -> list[Cohort]:
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
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
            _ = tmp_f.seek(0)
            return [
                Cohort(
                    "%s.%s" % (library, cohort_substr.strip()), run_name=self._run_name
                )
                for cohort_substr in tmp_f.readlines()
            ]

    def create_local_fastq_links(self, c: "TargetConfig"):
        for cohort in self.all:
            cohort.create_local_fastq_links(c)

    @lru_cache
    def targets(self, c: TargetConfig):
        # note that some targets which were previsouly dumped into the filesystem are now simply
        # returned as lists, namely: method, bwa_references
        return [target for cohort in self.all for target in cohort.targets(c)]

    @lru_cache
    def local_fastq_links(self, c: TargetConfig):
        return [target for cohort in self.all for target in cohort.local_fastq_links(c)]

    def make_dirs(self, gbs_paths: GbsPaths):
        for cohort_name in self.all_names:
            gbs_paths.make_cohort_dirs(cohort_name)
