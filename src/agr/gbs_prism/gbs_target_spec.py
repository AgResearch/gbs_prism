import logging
import os.path
import subprocess
import tempfile
from pydantic import BaseModel

from .exceptions import GbsPrismDataException
from .types import Cohort, flowcell_id

logger = logging.getLogger(__name__)


class GbsTargetSpec(BaseModel):
    """Cohorts and post-processing parameters which define the targets for stage 2."""

    libraries: dict[str, "LibraryTargetSpec"]

    @property
    def cohorts(self) -> dict[str, "CohortTargetSpec"]:
        return dict(
            [
                (cohort_name, cohort_target_spec)
                for library_target_spec in self.libraries.values()
                for (
                    cohort_name,
                    cohort_target_spec,
                ) in library_target_spec.cohorts.items()
            ]
        )


class LibraryTargetSpec(BaseModel):
    cohorts: dict[str, "CohortTargetSpec"]


class CohortTargetSpec(BaseModel):
    fastq_links: dict[str, str]  # link by basename
    genotyping_method: str
    alignment_references: dict[str, str]  # path by basename


def gquery_gbs_target_spec(run_name: str, fastq_link_farm: str) -> GbsTargetSpec:
    """Extract targets from database using gquery after Stage 1 processing."""
    library_target_specs = {}
    library_names = _gquery_libraries(run_name)
    for library_name in library_names:
        cohort_target_specs = {}
        cohort_names = _gquery_cohorts_for_library(run_name, library_name)
        for cohort_name in cohort_names:
            fastq_links = _gquery_cohort_fastq_links(
                run_name, cohort_name, fastq_link_farm
            )
            fastq_links_by_basename = dict(
                [(real_basename(fastq_link), fastq_link) for fastq_link in fastq_links]
            )
            assert len(fastq_links_by_basename) == len(
                fastq_links
            ), "non-unique fastq link basenames: %s" % ", ".join(fastq_links)
            genotyping_method = _gquery_cohort_genotyping_method(run_name, cohort_name)
            alignment_references = _gquery_cohort_alignment_references(
                run_name, cohort_name
            )

            cohort_target_specs[str(cohort_name)] = CohortTargetSpec(
                fastq_links=fastq_links_by_basename,
                genotyping_method=genotyping_method,
                alignment_references=alignment_references,
            )
        library_target_specs[library_name] = LibraryTargetSpec(
            cohorts=cohort_target_specs
        )

    return GbsTargetSpec(libraries=library_target_specs)


def write_gbs_target_spec(path: str, targets: GbsTargetSpec):
    """Write targets as JSON."""
    with open(path, "w", encoding="utf-8") as json_f:
        json_str = targets.model_dump_json(indent=2)
        _ = json_f.write(json_str)


def read_gbs_target_spec(path: str) -> GbsTargetSpec:
    """Read targets from JSON file."""
    with open(path, "r", encoding="utf-8") as json_f:
        json_str = json_f.read()
    return GbsTargetSpec.model_validate_json(json_str)


def _gquery_libraries(run_name: str) -> list[str]:
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        _ = subprocess.run(
            [
                "gquery",
                "-t",
                "lab_report",
                "-p",
                # Libraries are queried as samples 😩
                "name=illumina_run_details;samples",
                "--notfound_ok",
                run_name,
            ],
            stdout=tmp_f,
            text=True,
            check=True,
        )
        _ = tmp_f.seek(0)
        return [line.strip() for line in tmp_f.readlines()]


def _gquery_cohorts_for_library(run_name: str, library: str) -> list[Cohort]:
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        _ = subprocess.run(
            [
                "gquery",
                "-t",
                "lab_report",
                "-p",
                # Libraries are queried as samples 😩
                f"name=illumina_run_details;cohorts;sample_id={library}",
                "--notfound_ok",
                run_name,
            ],
            stdout=tmp_f,
            text=True,
            check=True,
        )
        _ = tmp_f.seek(0)
        return [
            Cohort.parse("%s.%s" % (library, cohort_substr.strip()))
            for cohort_substr in tmp_f.readlines()
        ]


def _gquery_cohort_fastq_links(
    run_name: str, cohort: Cohort, fastq_link_farm: str
) -> list[str]:
    fcid = flowcell_id(run_name)

    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        _ = subprocess.run(
            [
                "gquery",
                "-t",
                "gbs_keyfile",
                "-b",
                "library",
                "-p",
                f"flowcell={fcid};enzyme={cohort.enzyme};gbs_cohort={cohort.gbs_cohort};columns=fastq_link;noheading;distinct;fastq_path={fastq_link_farm}",
                "--notfound_ok",
                cohort.libname,
            ],
            stdout=tmp_f,
            text=True,
            check=True,
        )
        _ = tmp_f.seek(0)
        return [line.strip() for line in tmp_f.readlines()]


def _gquery_cohort_genotyping_method(run_name: str, cohort: Cohort) -> str:
    fcid = flowcell_id(run_name)
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        _ = subprocess.run(
            [
                "gquery",
                "-t",
                "gbs_keyfile",
                "-b",
                "library",
                "-p",
                f"flowcell={fcid};enzyme={cohort.enzyme};gbs_cohort={cohort.gbs_cohort};columns=geno_method;noheading;distinct;no_unpivot",
                cohort.libname,
            ],
            stdout=tmp_f,
            text=True,
            check=True,
        )
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
        _ = subprocess.run(
            [
                "gquery",
                "-t",
                "gbs_keyfile",
                "-b",
                "library",
                "-p",
                f"flowcell={fcid};enzyme={cohort.enzyme};gbs_cohort={cohort.gbs_cohort};columns=refgenome_bwa_indexes;noheading;distinct",
                cohort.libname,
            ],
            stdout=tmp_f,
            text=True,
            check=True,
        )
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


def real_basename(symlink: str) -> str:
    return os.path.basename(os.path.realpath(symlink))
