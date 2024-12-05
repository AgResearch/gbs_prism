import logging
import os.path
import tempfile
from pydantic import BaseModel, RootModel
from typing import List

from agr.util import StdioRedirect
from agr.gquery import GQuery, GQueryNotFoundException, Predicates

from .exceptions import GbsPrismDataException
from .types import Cohort, flowcell_id

logger = logging.getLogger(__name__)


class CohortSpec(BaseModel):
    name: str
    libname: str
    qc_cohort: str
    gbs_cohort: str
    enzyme: str
    fastq_links: List[str]
    genotyping_method: str
    alignment_references: List[str]


class CohortSpecs(RootModel):
    root: List[CohortSpec]


def _real_basename(symlink: str) -> str:
    return os.path.basename(os.path.realpath(symlink))


def _gquery_libraries(run_name: str) -> list[str]:
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            try:
                GQuery(
                    task="lab_report",
                    # Libraries are queried as samples 😩
                    predicates=Predicates(name="illumina_run_details", samples=True),
                    items=[run_name],
                ).run()
            except GQueryNotFoundException:
                return []
        _ = tmp_f.seek(0)
        return [line.strip() for line in tmp_f.readlines()]


def _gquery_cohorts_for_library(run_name: str, library: str) -> list[Cohort]:
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            try:
                GQuery(
                    task="lab_report",
                    # Libraries are queried as samples 😩
                    predicates=Predicates(
                        name="illumina_run_details", cohorts=True, sample_id=library
                    ),
                    items=[run_name],
                ).run()
            except GQueryNotFoundException:
                return []
        _ = tmp_f.seek(0)
        return [
            Cohort.parse("%s.%s" % (library, cohort_substr.strip()))
            for cohort_substr in tmp_f.readlines()
        ]


def _gquery_cohort_fastq_links(run_name: str, cohort: Cohort) -> list[str]:
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            try:
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        run=run_name,
                        enzyme=cohort.enzyme,
                        gbs_cohort=cohort.gbs_cohort,
                        columns="fastq_link",
                        noheading=True,
                        distinct=True,
                    ),
                    items=[cohort.libname],
                ).run()
            except GQueryNotFoundException:
                return []
        _ = tmp_f.seek(0)
        return [line.strip() for line in tmp_f.readlines()]


def _gquery_cohort_genotyping_method(run_name: str, cohort: Cohort) -> str:
    fcid = flowcell_id(run_name)
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            g = GQuery(
                task="gbs_keyfile",
                badge_type="library",
                predicates=Predicates(
                    flowcell=fcid,
                    enzyme=cohort.enzyme,
                    gbs_cohort=cohort.gbs_cohort,
                    columns="geno_method",
                    distinct=True,
                    noheading=True,
                    no_unpivot=True,
                ),
                items=[cohort.libname],
            )
            logger.info("%s" % g)
            g.run()
        _ = tmp_f.seek(0)
        methods = tmp_f.readlines()
        if (n_methods := len(methods)) != 1:
            raise GbsPrismDataException(
                "found %d distinct genotyping methods for cohort %s - should be exactly one. Has the keyfile for this cohort been imported ? If so check and change cohort defn or method geno_method col"
                % (n_methods, cohort)
            )
        method = methods[0].strip()
        logger.debug("cohort %s method %s" % (cohort, method))
        return method


# IMPORTANT NOTE: the SnakeMake targets are driven by target pathnames. A component of the path
# is the basename of the bwa reference, which means the full path to the bwa reference must be
# looked up from the basename, and must therefore be unique.  Non-uniqueness here is a fatal error,
# and will need to be addressed if in fact it turns out to be a problem.
def _gquery_cohort_alignment_references(
    run_name: str, cohort: Cohort
) -> dict[str, str]:
    fcid = flowcell_id(run_name)
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            GQuery(
                task="gbs_keyfile",
                badge_type="library",
                predicates=Predicates(
                    flowcell=fcid,
                    enzyme=cohort.enzyme,
                    gbs_cohort=cohort.gbs_cohort,
                    columns="refgenome_bwa_indexes",
                    noheading=True,
                    distinct=True,
                ),
                items=[cohort.libname],
            ).run()
        _ = tmp_f.seek(0)
        paths = list(
            # ensure uniqueness
            set(
                [
                    # gquery sometimes spits out empty paths, which we filter out here
                    path
                    for line in tmp_f.readlines()
                    if (path := line.strip())
                ]
            )
        )
        path_by_moniker = dict([(os.path.basename(path), path) for path in paths])
        assert len(path_by_moniker) == len(
            paths
        ), "uniqueness of basenames in bwa-references for cohort %s: %s" % (
            cohort,
            ", ".join(paths),
        )
        return path_by_moniker


def gquery_cohort_specs(run_name: str) -> List[CohortSpec]:
    """Extract cohort specs from database using gquery."""
    cohort_specs = []
    library_names = _gquery_libraries(run_name)
    for library_name in library_names:
        cohorts = _gquery_cohorts_for_library(run_name, library_name)
        for cohort in cohorts:
            fastq_links = _gquery_cohort_fastq_links(run_name, cohort)
            fastq_links_by_basename = dict(
                [(_real_basename(fastq_link), fastq_link) for fastq_link in fastq_links]
            )
            assert len(fastq_links_by_basename) == len(
                fastq_links
            ), "non-unique fastq link basenames: %s" % ", ".join(fastq_links)
            genotyping_method = _gquery_cohort_genotyping_method(run_name, cohort)
            alignment_references = _gquery_cohort_alignment_references(run_name, cohort)

            cohort_specs.append(
                CohortSpec(
                    name=cohort.name,
                    libname=cohort.libname,
                    qc_cohort=cohort.qc_cohort,
                    gbs_cohort=cohort.gbs_cohort,
                    enzyme=cohort.enzyme,
                    fastq_links=fastq_links,
                    genotyping_method=genotyping_method,
                    alignment_references=list(alignment_references.values()),
                )
            )

    return cohort_specs


def write_cohort_specs(path: str, specs: List[CohortSpec]):
    """Write targets as JSON."""
    cohort_specs = CohortSpecs(root=specs)
    with open(path, "w", encoding="utf-8") as json_f:
        json_str = cohort_specs.model_dump_json(indent=2)
        _ = json_f.write(json_str)


def read_cohort_specs(path: str) -> List[CohortSpec]:
    """Read targets from JSON file."""
    with open(path, "r", encoding="utf-8") as json_f:
        json_str = json_f.read()
    cohort_specs = CohortSpecs.model_validate_json(json_str)
    return cohort_specs.root
