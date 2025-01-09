import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Dict, List

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import remove_if_exists

from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import GbsTargetSpec


@task
def create_cohort_fastq_links(
    spec: GbsTargetSpec, gbs_paths: GbsPaths
) -> Dict[str, List[File]]:
    """Link the fastq files for each cohort separately.

    So that subsequent dependencies can be properly captured in wildcarded paths.
    """
    links_by_cohort = {}
    for cohort_name, cohort_spec in spec.cohorts.items():
        cohort_links = []
        for fastq_basename, fastq_link in cohort_spec.fastq_links.items():
            # create the same links in both blind and unblind directories
            for blind in [False, True]:
                link_dir = gbs_paths.fastq_link_dir(str(cohort_name), blind=blind)
                os.makedirs(link_dir, exist_ok=True)
                link = os.path.join(
                    link_dir,
                    fastq_basename,
                )
                # Python should really support ln -sf, bah!
                remove_if_exists(link)
                os.symlink(sanitised_realpath(fastq_link), link)
                cohort_links.append(File(link))
        links_by_cohort[cohort_name] = cohort_links
    return links_by_cohort


@task(script=True)
def create_dedupe_summary_one_cohort(fastq_links: List[str], out_path: str):
    return f"""
        #!/usr/bin/env bash
        get_dedupe_summary {fastq_links} >{out_path}
    """


@task()
def create_dedupe_summary_all_cohorts(
    spec: GbsTargetSpec, gbs_paths: GbsPaths, fastq_links: Dict[str, List[File]]
) -> Dict[str, File]:
    summary_by_cohort = {}
    for cohort_name in spec.cohorts.keys():
        summary_by_cohort[cohort_name] = create_dedupe_summary_one_cohort(
            fastq_links=[file.path for file in fastq_links[cohort_name]],
            out_path=os.path.join(
                gbs_paths.cohort_dir(str(cohort_name)), "dedupe_summary.txt"
            ),
        )
    return summary_by_cohort


@dataclass
class Stage2Output:
    dummy: bool
    # dedupe_summary: Dict[str, File], TODO, not working yet


@task()
def run_stage2(spec: GbsTargetSpec, gbs_paths: GbsPaths) -> Stage2Output:

    fastq_links = create_cohort_fastq_links(spec=spec, gbs_paths=gbs_paths)

    dedupe_summary = create_dedupe_summary_all_cohorts(
        spec=spec, gbs_paths=gbs_paths, fastq_links=fastq_links
    )

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage2Output(
        dummy=True,
        # dedupe_summary=dedupe_summary - TODO not working yet
    )
