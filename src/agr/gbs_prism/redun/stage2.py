import os.path
import tempfile
from dataclasses import dataclass
from redun import task, File
from typing import Dict, List

redun_namespace = "agr.gbs_prism"

from agr.util.legacy import sanitised_realpath
from agr.util.path import remove_if_exists
from agr.util.redun import lazy_concat, one_forall

from agr.seq.bwa import Bwa
from agr.seq.cutadapt import cutadapt
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.types import Cohort, flowcell_id
from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import CohortTargetSpec, GbsTargetSpec


@dataclass
class CohortSpec:
    run: str
    cohort: Cohort
    target: CohortTargetSpec
    paths: GbsPaths
    bwa_sample: FastqSample
    bwa: Bwa


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
    os.makedirs(out_dir, exist_ok=True)
    # the ugly name is copied from legacy gbs_prism
    out_path = os.path.join(
        out_dir,
        "%s.fastq.%s.fastq"
        % (os.path.basename(fastq_file.path), spec.bwa_sample.moniker),
    )
    spec.bwa_sample.run(in_path=fastq_file.path, out_path=out_path)
    return File(out_path)


@task()
def sample_all_for_bwa(fastq_files: List[File], spec: CohortSpec) -> List[File]:
    return one_forall(sample_one_for_bwa, fastq_files, spec=spec)


@task
def cutadapt_one(fastq_file: File, kwargs) -> File:
    out_dir = kwargs["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir,
        "%s.trimmed.fastq" % os.path.basename(fastq_file.path).removesuffix(".fastq"),
    )
    cutadapt(in_path=fastq_file.path, out_path=out_path)
    return File(out_path)


@task()
def cutadapt_all(fastq_files: List[File], out_dir: str) -> List[File]:
    return one_forall(cutadapt_one, fastq_files, out_dir=out_dir)


@dataclass
class BwaAlnOutput:
    fastq: File
    sai: File


@task()
def bwa_aln_one(fastq_file: File, kwargs) -> BwaAlnOutput:
    """bwa aln for a single file with a single reference genome."""
    ref_name = kwargs["ref_name"]
    ref_path = kwargs["ref_path"]
    bwa = kwargs["bwa"]
    out_dir = kwargs["out_dir"]
    out_path = os.path.join(
        out_dir,
        "%s.bwa.%s.%s.sai" % (os.path.basename(fastq_file.path), ref_name, bwa.moniker),
    )
    bwa.aln(in_path=fastq_file.path, out_path=out_path, reference=ref_path)
    return BwaAlnOutput(fastq=fastq_file, sai=File(out_path))


@task()
def bwa_aln_all(
    fastq_files: List[File], ref_name: str, ref_path: str, bwa: Bwa, out_dir: str
) -> List[BwaAlnOutput]:
    """bwa aln for multiple files with a single reference genome."""
    return one_forall(
        bwa_aln_one,
        fastq_files,
        ref_name=ref_name,
        ref_path=ref_path,
        bwa=bwa,
        out_dir=out_dir,
    )


@task()
def bwa_samse_one(aln: BwaAlnOutput, kwargs) -> File:
    """bwa samse for a single file with a single reference genome."""
    ref_path = kwargs["ref_path"]
    bwa = kwargs["bwa"]
    out_path = "%s.bam" % aln.sai.path.removesuffix(".sai")
    bwa.samse(
        sai_path=aln.sai.path,
        fastq_path=aln.fastq.path,
        out_path=out_path,
        reference=ref_path,
    )
    return File(out_path)


@task()
def bwa_samse_all(
    alns: List[BwaAlnOutput], ref_name: str, ref_path: str, bwa: Bwa
) -> List[File]:
    """bwa samse for multiple files with a single reference genome."""
    return one_forall(
        bwa_samse_one,
        alns,
        ref_name=ref_name,
        ref_path=ref_path,
        bwa=bwa,
    )


@task()
def bwa_all_reference_genomes(fastq_files: List[File], spec: CohortSpec) -> List[File]:
    """bwa_aln and bwa_samse for each file for each of the reference genomes."""
    out_dir = spec.paths.bwa_mapping_dir(spec.cohort.name)
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    for ref_name, ref_path in spec.target.alignment_references.items():
        alns = bwa_aln_all(
            fastq_files,
            ref_name=ref_name,
            ref_path=ref_path,
            bwa=spec.bwa,
            out_dir=out_dir,
        )
        bam_files = bwa_samse_all(
            alns,
            ref_name=ref_name,
            ref_path=ref_path,
            bwa=spec.bwa,
        )
        out_paths = lazy_concat(out_paths, bam_files)
    return out_paths


@task(script=True)
def bam_stats_one(bam_file: File, _kwargs) -> str:
    """run samtools flagstat for a single file."""
    in_path = bam_file.path
    out_path = "%s.stats" % bam_file.path.removesuffix(".bam")
    return f"""
        samtools flagstat {in_path} >{out_path}
    """


@task()
def bam_stats_all(bam_files: List[File]) -> List[File]:
    """bwa samse for multiple files with a single reference genome."""
    return one_forall(bam_stats_one, bam_files)


# this is a script because StdioRedirect causes trouble in redun
# TODO tidy this up a bit
@task(script=True)
def get_keyfile_content_for_tassel(spec: CohortSpec) -> str:
    return f"""
    #!/usr/bin/env python
    import sys
    import tempfile

    from agr.util import StdioRedirect
    from agr.gbs_prism.enzyme_sub import enzyme_sub_for_uneak
    from agr.gquery import GQuery, Predicates

    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        with StdioRedirect(stdout=tmp_f):
            g = GQuery(
                task="gbs_keyfile",
                badge_type="library",
                predicates=Predicates(
                    flowcell="{flowcell_id(spec.run)}",
                    enzyme="{spec.cohort.enzyme}",
                    gbs_cohort="{spec.cohort.gbs_cohort}",
                    columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link",
                ),
                items=["{spec.cohort.libname}"],
            )
            # logger.info(g)
            g.run()

        _ = tmp_f.seek(0)
        for line in tmp_f:
            _ = sys.stdout.write(enzyme_sub_for_uneak(line))
    """


@task
def save_keyfile_content_for_tassel(content: str, out_path: str) -> File:
    with open(out_path, "wb") as out_f:
        _ = out_f.write(content)
    return File(out_path)


@task()
def get_keyfile_for_tassel(spec: CohortSpec) -> File:
    out_path = os.path.join(
        spec.paths.run_root, "%s.%s.key" % (spec.run, spec.cohort.name)
    )
    content = get_keyfile_content_for_tassel(spec)
    return save_keyfile_content_for_tassel(content, out_path)


@dataclass
class CohortOutput:
    fastq_links: List[File]
    bwa_sampled: List[File]
    trimmed: List[File]
    bam_files: List[File]
    bam_stats_files: List[File]
    keyfile_for_tassel: File


@task()
def run_cohort(spec: CohortSpec) -> CohortOutput:
    fastq_links = create_cohort_fastq_links(spec)
    bwa_sampled = sample_all_for_bwa(fastq_links, spec)
    trimmed = cutadapt_all(
        bwa_sampled, out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name)
    )
    bam_files = bwa_all_reference_genomes(trimmed, spec)
    bam_stats_files = bam_stats_all(bam_files)
    keyfile_for_tassel = get_keyfile_for_tassel(spec)

    output = CohortOutput(
        fastq_links=fastq_links,
        bwa_sampled=bwa_sampled,
        trimmed=trimmed,
        bam_files=bam_files,
        bam_stats_files=bam_stats_files,
        keyfile_for_tassel=keyfile_for_tassel,
    )
    return output


@dataclass
class Stage2Output:
    dummy: bool
    cohorts: Dict[str, CohortOutput]


@task()
def run_stage2(run: str, spec: GbsTargetSpec, gbs_paths: GbsPaths) -> Stage2Output:
    cohort_outputs = {}

    bwa_sample = FastqSample(
        sample_rate=0.00005,
        minimum_sample_size=150000,
    )

    bwa = Bwa(barcode_len=10)

    for name, target in spec.cohorts.items():
        cohort = Cohort.parse(name)
        target = CohortSpec(
            run=run,
            cohort=cohort,
            target=target,
            paths=gbs_paths,
            bwa_sample=bwa_sample,
            bwa=bwa,
        )

        cohort_outputs[name] = run_cohort(target)

    # the return value forces evaluation of the lazy expressions, otherwise nothing happens
    return Stage2Output(
        dummy=True,
        cohorts=cohort_outputs,
    )
