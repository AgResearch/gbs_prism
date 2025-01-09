import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Dict, List

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import remove_if_exists
from agr.util.redun import one_forall

from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.types import Cohort
from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import CohortTargetSpec, GbsTargetSpec


@dataclass
class CohortSpec:
    cohort: Cohort
    target: CohortTargetSpec
    paths: GbsPaths
    bwa_sample: FastqSample


@task
def create_cohort_fastq_links(spec: CohortSpec) -> List[File]:
    """Link the fastq files for a single cohort separately.

    So that subsequent dependencies can be properly captured in wildcarded paths.
    """
    cohort_links = []
    for fastq_basename, fastq_link in spec.target.fastq_links.items():
        # create the same links in both blind and unblind directories
        for blind in [False, True]:
            link_dir = spec.paths.fastq_link_dir(str(spec.cohort.name), blind=blind)
            os.makedirs(link_dir, exist_ok=True)
            link = os.path.join(
                link_dir,
                fastq_basename,
            )
            # Python should really support ln -sf, bah!
            remove_if_exists(link)
            os.symlink(sanitised_realpath(fastq_link), link)
            # we only need one for each, the blind case is purely for Tassel3
            if not blind:
                cohort_links.append(File(link))
    return cohort_links


@task()
def sample_one_for_bwa(fastq_file: File, kwargs) -> File:
    spec = kwargs["spec"]
    out_dir = spec.paths.bwa_mapping_dir(spec.cohort.name)
    # the ugly name is copied from legacy gbs_prism
    out_path = os.path.join(
        out_dir,
        "%s.fastq.%s.fastq"
        % (os.path.basename(fastq_file.path), spec.bwa_sample.moniker),
    )
    os.makedirs(out_dir, exist_ok=True)
    spec.bwa_sample.run(in_path=fastq_file.path, out_path=out_path)
    return File(out_path)


@task()
def sample_all_for_bwa(fastq_files: List[File], spec: CohortSpec) -> List[File]:
    return one_forall(sample_one_for_bwa, fastq_files, spec=spec)


@dataclass
class CohortOutput:
    fastq_links: List[File]
    bwa_sampled: List[File]


@task()
def run_cohort(spec: CohortSpec) -> CohortOutput:
    fastq_links = create_cohort_fastq_links(spec)
    bwa_sampled = sample_all_for_bwa(fastq_links, spec)

    output = CohortOutput(fastq_links=fastq_links, bwa_sampled=bwa_sampled)
    return output


@dataclass
class Stage2Output:
    dummy: bool
    cohorts: Dict[str, CohortOutput]


@task()
def run_stage2(spec: GbsTargetSpec, gbs_paths: GbsPaths) -> Stage2Output:
    cohort_outputs = {}

    bwa_sample = FastqSample(
        sample_rate=0.00005,
        minimum_sample_size=150000,
    )

    for name, target in spec.cohorts.items():
        cohort = Cohort.parse(name)
        target = CohortSpec(
            cohort=cohort, target=target, paths=gbs_paths, bwa_sample=bwa_sample
        )

        cohort_outputs[name] = run_cohort(target)

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage2Output(
        dummy=True,
        cohorts=cohort_outputs,
    )
