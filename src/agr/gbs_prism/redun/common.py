from redun import task, File
from agr.redun.cluster_executor import run_job_1
from agr.seq.fastq_sample import FastqSample


@task()
def sample_minsize_if_required(
    fastq_file: File, sample_spec: FastqSample, rate_sample: File, out_path: str
) -> File:
    if sample_spec.is_minsize_job_required(
        in_path=fastq_file.path, rate_sample_path=rate_sample.path
    ):
        return run_job_1(
            sample_spec.minsize_job_spec(in_path=fastq_file.path, out_path=out_path),
        )
    else:
        return rate_sample
