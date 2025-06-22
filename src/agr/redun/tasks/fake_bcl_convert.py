import gzip
import logging
import os.path
import shutil
from redun import task, File
from redun.context import get_context

from agr.seq.sample_sheet import SampleSheet
from agr.redun import JobContext

from .bcl_convert import (
    bcl_convert,
    BclConvertPaths,
    BclConvertOutput,
    BclConvertError,
)

logger = logging.getLogger(__name__)


@task()
def fake_bcl_convert(
    in_dir: str, sample_sheet_path: str, out_dir: str, n_reads
) -> BclConvertOutput:
    paths = BclConvertPaths(out_dir)

    # find the real run
    run_name = os.path.basename(in_dir)
    illumina_datasets = [
        "2024_illumina_sequencing_e",
        "2024_illumina_sequencing_d",
        "2023_illumina_sequencing_c",
        "2023_illumina_sequencing_b",
        "2023_illumina_sequencing_a",
    ]
    candidate_run_dir = "/not-found"
    for dataset in illumina_datasets:
        candidate_run_dir = "/dataset/%s/scratch/postprocessing/illumina/novaseq/%s" % (
            dataset,
            run_name,
        )
        if os.path.isdir(candidate_run_dir):
            break
    if not os.path.isdir(candidate_run_dir):
        raise BclConvertError(
            "failed to find run %s in any of %s"
            % (run_name, " ".join(illumina_datasets))
        )
    real_fastq_dir = os.path.join(candidate_run_dir, "SampleSheet", "bclconvert")
    real_reports_dir = os.path.join(real_fastq_dir, "Reports")

    logger.warning("FakeBclConvert with %d reads from %s" % (n_reads, real_fastq_dir))
    sample_sheet = SampleSheet(sample_sheet_path, impute_lanes=[1, 2])

    fastq_paths = []
    for fastq_file in sample_sheet.fastq_files:
        with gzip.open(os.path.join(real_fastq_dir, fastq_file), mode="r") as real_gz:
            fastq_paths.append(fastq_path := os.path.join(out_dir, fastq_file))
            with gzip.open(fastq_path, mode="w") as fake_gz:
                for _ in range(n_reads * 4):  # 4 lines per read
                    line = next(real_gz)
                    _ = fake_gz.write(line)

    # copy all the reports since they're now being returned as BclConvertOutput
    reports_dir = os.path.join(out_dir, "Reports")
    _ = shutil.copytree(
        real_reports_dir, reports_dir, symlinks=True, dirs_exist_ok=True
    )

    return BclConvertOutput(
        fastq_files=[File(fastq_path) for fastq_path in fastq_paths],
        adapter_metrics=File(paths.adapter_metrics_path),
        demultiplexing_metrics=File(paths.demultiplex_stats_path),
        quality_metrics=File(paths.quality_metrics_path),
        run_info_xml=File(paths.run_info_xml_path),
        top_unknown=File(paths.top_unknown_path),
    )


@task()
def real_or_fake_bcl_convert(
    in_dir: str,
    sample_sheet_path: str,
    expected_fastq: set[str],
    out_dir: str,
    job_context: JobContext,
    tool_context=get_context("tools.bcl_convert"),
) -> BclConvertOutput:
    if tool_context is not None and (fake := tool_context.get("fake")) is not None:
        return fake_bcl_convert(
            in_dir=in_dir,
            sample_sheet_path=sample_sheet_path,
            out_dir=out_dir,
            n_reads=fake.get("n_reads", 2000000),  # enough to keep KGD happy
        )
    else:
        return bcl_convert(
            in_dir=in_dir,
            sample_sheet_path=sample_sheet_path,
            expected_fastq=expected_fastq,
            out_dir=out_dir,
            job_context=job_context,
        )
