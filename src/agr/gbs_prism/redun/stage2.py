import os.path
import subprocess
import tempfile
from dataclasses import dataclass
from redun import task, File
from redun.file import glob_file
from typing import Dict, List

redun_namespace = "agr.gbs_prism"

from agr.gquery import GQuery, Predicates
from agr.util.legacy import sanitised_realpath
from agr.util.path import remove_if_exists
from agr.util.redun import concat, one_forall
from agr.seq.bwa import Bwa
from agr.seq.cutadapt import cutadapt
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.enzyme_sub import enzyme_sub_for_uneak
from agr.gbs_prism.paths import GbsPaths
from agr.gbs_prism.gbs_target_spec import CohortTargetSpec, GbsTargetSpec
from agr.gbs_prism.GUSbase import run_GUSbase
from agr.gbs_prism.kgd import run_kgd
from agr.gbs_prism.tassel3 import Tassel3, fastq_name_for_tassel3
from agr.gbs_prism.types import Cohort, flowcell_id


@dataclass
class CohortSpec:
    run: str
    cohort: Cohort
    target: CohortTargetSpec
    paths: GbsPaths
    bwa_sample: FastqSample
    bwa: Bwa


@task
def create_cohort_fastq_links(spec: CohortSpec) -> tuple[List[File], List[File]]:
    """Link the fastq files for a single cohort separately.

    So that subsequent dependencies can be properly captured in wildcarded paths.
    """
    cohort_links = []
    cohort_munged_links = []
    for fastq_basename, fastq_link in spec.target.fastq_links.items():
        # create the same links in both blind and unblind directories
        for blind in [False, True]:
            link_dir = spec.paths.fastq_link_dir(str(spec.cohort.name), blind=blind)
            os.makedirs(link_dir, exist_ok=True)
            link = os.path.join(
                link_dir,
                (
                    # the blind directory is solely for Tassel3 which ironically can't see .fastq.gz files
                    fastq_basename
                    if not blind
                    else fastq_name_for_tassel3(
                        spec.cohort, flowcell_id(spec.run), fastq_basename
                    )
                ),
            )
            # Python should really support ln -sf, bah!
            remove_if_exists(link)
            os.symlink(sanitised_realpath(fastq_link), link)
            if blind:
                cohort_munged_links.append(File(link))
            else:
                cohort_links.append(File(link))
    return (cohort_links, cohort_munged_links)


@task()
def sample_one_for_bwa(fastq_file: File, spec: CohortSpec) -> File:
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
def cutadapt_one(fastq_file: File, out_dir: str) -> File:
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
def bwa_aln_one(
    fastq_file: File, ref_name: str, ref_path: str, bwa: Bwa, out_dir: str
) -> BwaAlnOutput:
    """bwa aln for a single file with a single reference genome."""
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
def bwa_samse_one(aln: BwaAlnOutput, ref_path: str, bwa: Bwa) -> File:
    """bwa samse for a single file with a single reference genome."""
    out_path = "%s.bam" % aln.sai.path.removesuffix(".sai")
    bwa.samse(
        sai_path=aln.sai.path,
        fastq_path=aln.fastq.path,
        out_path=out_path,
        reference=ref_path,
    )
    return File(out_path)


@task()
def bwa_samse_all(alns: List[BwaAlnOutput], ref_path: str, bwa: Bwa) -> List[File]:
    """bwa samse for multiple files with a single reference genome."""
    return one_forall(
        bwa_samse_one,
        alns,
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
            ref_path=ref_path,
            bwa=spec.bwa,
        )
        out_paths = concat(out_paths, bam_files)
    return out_paths


@task()
def bam_stats_one(bam_file: File) -> File:
    """run samtools flagstat for a single file."""
    out_path = "%s.stats" % bam_file.path.removesuffix(".bam")
    with open(out_path, "w") as out_f:
        _ = subprocess.run(
            ["samtools", "flagstat", bam_file.path], stdout=out_f, check=True
        )
    return File(out_path)


@task()
def bam_stats_all(bam_files: List[File]) -> List[File]:
    """bwa samse for multiple files with a single reference genome."""
    return one_forall(bam_stats_one, bam_files)


@task()
def get_keyfile_for_tassel(spec: CohortSpec) -> File:
    out_path = os.path.join(
        spec.paths.run_root, "%s.%s.key" % (spec.run, spec.cohort.name)
    )
    fcid = flowcell_id(spec.run)
    with tempfile.TemporaryFile(mode="w+") as tmp_f:
        GQuery(
            task="gbs_keyfile",
            badge_type="library",
            predicates=Predicates(
                flowcell=fcid,
                enzyme=spec.cohort.enzyme,
                gbs_cohort=spec.cohort.gbs_cohort,
                columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link",
            ),
            items=[spec.cohort.libname],
            outfile=tmp_f,
        ).run()

        _ = tmp_f.seek(0)
        with open(out_path, "w") as out_f:
            for line in tmp_f:
                _ = out_f.write(enzyme_sub_for_uneak(line))
    return File(out_path)


@task()
def get_keyfile_for_gbsx(spec: CohortSpec) -> File:
    out_path = os.path.join(
        spec.paths.run_root, "%s.%s.gbsx.key" % (spec.run, spec.cohort.name)
    )
    fcid = flowcell_id(spec.run)
    with open(out_path, "w") as out_f:
        GQuery(
            task="gbs_keyfile",
            badge_type="library",
            predicates=Predicates(
                flowcell=fcid,
                enzyme=spec.cohort.enzyme,
                gbs_cohort=spec.cohort.gbs_cohort,
                columns="qc_sampleid as sample,Barcode,Enzyme",
            ),
            items=[spec.cohort.libname],
            outfile=out_f,
        ).run()
    return File(out_path)


@dataclass
class FastqToTagCountOutput:
    stdout: File
    tag_counts: List[File]


@task()
def get_fastq_to_tag_count(spec: CohortSpec, keyfile: File) -> FastqToTagCountOutput:
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    # tag_counts_part1_dir = os.path.join(cohort_blind_dir, "tagCounts_parts", "part1")
    # tag_counts_done = os.path.join(cohort_blind_dir, "tagCounts.done")
    tag_counts_dir = os.path.join(cohort_blind_dir, "tagCounts")
    tassel3 = Tassel3()
    tassel3.fastq_to_tag_count(
        in_path=keyfile.path, cohort_str=spec.cohort.name, work_dir=cohort_blind_dir
    )
    stdout = File(os.path.join(cohort_blind_dir, "FastqToTagCount.stdout"))
    tag_counts = [File(path) for path in glob_file("%s/*" % tag_counts_dir)]

    return FastqToTagCountOutput(stdout=stdout, tag_counts=tag_counts)


@task()
def get_tag_count(fastqToTagCountStdout: File) -> File:

    out_path = os.path.join(os.path.dirname(fastqToTagCountStdout.path), "TagCount.csv")
    with open(fastqToTagCountStdout.path, "r") as in_f:
        with open(out_path, "w") as out_f:
            _ = subprocess.run(
                ["get_reads_tags_per_sample"], stdin=in_f, stdout=out_f, check=True
            )
    return File(out_path)


@task()
def get_tags_reads_summary(spec: CohortSpec, tagCountCsv: File) -> File:
    out_dir = spec.paths.cohort_dir(spec.cohort.name)
    out_path = os.path.join(out_dir, "tags_reads_summary.txt")
    _ = subprocess.run(
        ["summarise_read_and_tag_counts", "-o", out_path, tagCountCsv.path], check=True
    )
    return File(out_path)


@task()
def get_tags_reads_cv(tags_reads_summary: File) -> File:
    out_path = os.path.join(
        os.path.dirname(tags_reads_summary.path), "tags_reads_cv.txt"
    )
    with open(out_path, "w") as out_f:
        _ = subprocess.run(
            ["cut", "-f", "1,4,9", tags_reads_summary.path], stdout=out_f, check=True
        )
    return File(out_path)


@task()
def merge_taxa_tag_count(spec: CohortSpec, tag_counts: List[File]) -> File:
    _ = tag_counts  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    tassel3 = Tassel3()
    tassel3.merge_taxa_tag_count(work_dir=cohort_blind_dir)
    return File(os.path.join(cohort_blind_dir, "mergedTagCounts", "mergedAll.cnt"))


@task()
def tag_count_to_tag_pair(spec: CohortSpec, merged_all_count: File) -> File:
    _ = merged_all_count  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    tassel3 = Tassel3()
    tassel3.tag_count_to_tag_pair(work_dir=cohort_blind_dir)
    return File(os.path.join(cohort_blind_dir, "tagPair", "tagPair.tps"))


@task()
def tag_pair_to_tbt(spec: CohortSpec, tag_pair: File) -> File:
    _ = tag_pair  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    tassel3 = Tassel3()
    tassel3.tag_pair_to_tbt(work_dir=cohort_blind_dir)
    return File(os.path.join(cohort_blind_dir, "tagsByTaxa", "tbt.bin"))


@task()
def tbt_to_map_info(spec: CohortSpec, tags_by_taxa: File) -> File:
    _ = tags_by_taxa  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    tassel3 = Tassel3()
    tassel3.tbt_to_map_info(work_dir=cohort_blind_dir)
    return File(os.path.join(cohort_blind_dir, "mapInfo", "mapInfo.bin"))


@task()
def map_info_to_hap_map(spec: CohortSpec, map_info: File) -> List[File]:
    _ = map_info  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    tassel3 = Tassel3()
    tassel3.map_info_to_hap_map(work_dir=cohort_blind_dir)
    hap_map_dir = os.path.join(cohort_blind_dir, "hapMap")
    return [File(path) for path in glob_file("%s/*" % hap_map_dir)]


@dataclass
class KgdOutput:
    sample_stats_csv: File
    gusbase_rdata: File


@task()
def kgd(spec: CohortSpec, hap_map_files: List[File]) -> KgdOutput:
    _ = hap_map_files  # depending on existence rather than value
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    out_dir = os.path.join(cohort_blind_dir, "KGD")
    os.makedirs(out_dir, exist_ok=True)
    # KGD already knows what input files it expects to see under `base_dir`
    run_kgd(
        base_dir=cohort_blind_dir,
        genotyping_method=spec.target.genotyping_method,
    )
    return KgdOutput(
        sample_stats_csv=File(os.path.join(out_dir, "SampleStats.csv")),
        gusbase_rdata=File(os.path.join(out_dir, "GUSbase.RData")),
    )


@task()
def gusbase(spec: CohortSpec, gusbase_rdata: File) -> File:
    cohort_blind_dir = os.path.join(spec.paths.run_root, spec.cohort.name, "blind")
    out_dir = os.path.join(cohort_blind_dir, "KGD")
    run_GUSbase(gusbase_rdata.path)
    return File(os.path.join(out_dir, "GUSbase_comet.jpg"))


@dataclass
class CohortOutput:
    # TODO remove the ones we don't need
    fastq_links: List[File]
    munged_fastq_links_for_tassel: List[File]
    bwa_sampled: List[File]
    trimmed: List[File]
    bam_files: List[File]
    bam_stats_files: List[File]
    keyfile_for_tassel: File
    keyfile_for_gbsx: File
    tag_count: File
    tags_reads_summary: File
    tags_reads_cv: File
    merged_all_count: File
    tag_pair: File
    tags_by_taxa: File
    map_info: File
    hap_map_files: List[File]
    kgd_output: KgdOutput
    gusbase_comet: File


@task()
def run_cohort(spec: CohortSpec) -> CohortOutput:
    fastq_links, munged_fastq_links_for_tassel = create_cohort_fastq_links(spec)
    bwa_sampled = sample_all_for_bwa(fastq_links, spec)
    trimmed = cutadapt_all(
        bwa_sampled, out_dir=spec.paths.bwa_mapping_dir(spec.cohort.name)
    )
    bam_files = bwa_all_reference_genomes(trimmed, spec)
    bam_stats_files = bam_stats_all(bam_files)
    keyfile_for_tassel = get_keyfile_for_tassel(spec)
    keyfile_for_gbsx = get_keyfile_for_gbsx(spec)
    fastq_to_tag_count = get_fastq_to_tag_count(spec, keyfile_for_tassel)
    tag_count = get_tag_count(fastq_to_tag_count.stdout)
    tags_reads_summary = get_tags_reads_summary(spec, tag_count)
    tags_reads_cv = get_tags_reads_cv(tags_reads_summary)
    merged_all_count = merge_taxa_tag_count(spec, fastq_to_tag_count.tag_counts)
    tag_pair = tag_count_to_tag_pair(spec, merged_all_count)
    tags_by_taxa = tag_pair_to_tbt(spec, tag_pair)
    map_info = tbt_to_map_info(spec, tags_by_taxa)
    hap_map_files = map_info_to_hap_map(spec, map_info)
    kgd_output = kgd(spec, hap_map_files)
    gusbase_comet = gusbase(spec, kgd_output.gusbase_rdata)

    output = CohortOutput(
        fastq_links=fastq_links,
        munged_fastq_links_for_tassel=munged_fastq_links_for_tassel,
        bwa_sampled=bwa_sampled,
        trimmed=trimmed,
        bam_files=bam_files,
        bam_stats_files=bam_stats_files,
        keyfile_for_tassel=keyfile_for_tassel,
        keyfile_for_gbsx=keyfile_for_gbsx,
        tag_count=tag_count,
        tags_reads_summary=tags_reads_summary,
        tags_reads_cv=tags_reads_cv,
        merged_all_count=merged_all_count,
        tag_pair=tag_pair,
        tags_by_taxa=tags_by_taxa,
        map_info=map_info,
        hap_map_files=hap_map_files,
        kgd_output=kgd_output,
        gusbase_comet=gusbase_comet,
    )
    return output


@dataclass
class Stage2Output:
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
        cohorts=cohort_outputs,
    )
