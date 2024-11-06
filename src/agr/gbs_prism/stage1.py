from functools import cached_property, lru_cache
from subprocess import PIPE

from agr.util import StdioRedirect
from agr.gquery import GQuery, GQueryNotFoundException, Predicates

from .types import flowcell_id, Cohort


class Stage1Outputs(object):
    def __init__(self, run_name: str, fastq_link_farm: str):
        self._run_name = run_name
        self._fastq_link_farm = fastq_link_farm

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
            return [line.strip() for line in lab_report.stdout.readlines()]

    @lru_cache
    def cohorts(self, library) -> list[Cohort]:
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
            return [
                Cohort.parse("%s.%s" % (library, cohort_substr.strip()))
                for cohort_substr in lab_report.stdout.readlines()
            ]

    @cached_property
    def all_cohorts(self) -> list[Cohort]:
        return [
            cohort for library in self.libraries for cohort in self.cohorts(library)
        ]

    @lru_cache
    def fastq_links(self, cohort: Cohort) -> list[str]:
        fcid = flowcell_id(self._run_name)

        with StdioRedirect(stdout=PIPE) as gbs_keyfile:
            try:
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=cohort.enzyme,
                        gbs_cohort=cohort.gbs_cohort,
                        columns="lane,fastq_link",
                        noheading=True,
                        distinct=True,
                        fastq_path=self._fastq_link_farm,
                    ),
                    items=[cohort.libname],
                ).run()
            except GQueryNotFoundException:
                return []
            assert gbs_keyfile.stdout is not None  # because PIPE
            return [
                line.strip().split("\t")[1] for line in gbs_keyfile.stdout.readlines()
            ]

    @cached_property
    def all_fastq_links(self) -> set[str]:
        return set(
            [
                fastq_link
                for cohort in self.all_cohorts
                for fastq_link in self.fastq_links(cohort)
            ]
        )
