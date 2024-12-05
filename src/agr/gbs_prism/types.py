from dataclasses import dataclass
from typing import Self


def flowcell_id(run: str) -> str:
    return run.split("_")[3][1:]


@dataclass(frozen=True)
class Cohort:
    libname: str
    qc_cohort: str
    gbs_cohort: str
    enzyme: str

    def __str__(self) -> str:
        return "%s.%s.%s.%s" % (
            self.libname,
            self.qc_cohort,
            self.gbs_cohort,
            self.enzyme,
        )

    @property
    def name(self) -> str:
        return str(self)

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
