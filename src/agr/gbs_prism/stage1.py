from functools import cached_property, lru_cache
from subprocess import PIPE
from dataclasses import dataclass
from typing import Self

from agr.util import StdioRedirect, eprint
from agr.gquery import GQuery, GQueryNotFoundException, Predicates


def _flowcell_id(run: str) -> str:
    return run.split("_")[3][1:]


@dataclass(frozen=True)
class Cohort:
    libname: str
    qc_cohort: str
    gbs_cohort: str
    enzyme: str

    def __str__(self):
        return "%s.%s.%s.%s" % (
            self.libname,
            self.qc_cohort,
            self.gbs_cohort,
            self.enzyme,
        )

    @classmethod
    def parse(cls, cohort_str: str) -> Self:
        fields = cohort_str.split(".")
        assert len(fields) == 4, (
            "expected four dot-separated fields in cohort %s" % cohort_str
        )
        (libname, qc_cohort, gbs_cohort, enzyme) = tuple(fields)
        return cls(
            libname=libname, qc_cohort=qc_cohort, gbs_cohort=gbs_cohort, enzyme=enzyme
        )


class Stage1(object):
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

    @lru_cache
    def fastq_files(self, cohort: Cohort) -> list[str]:
        fcid = _flowcell_id(self._run_name)

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
