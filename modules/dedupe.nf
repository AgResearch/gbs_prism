process DEDUPE {
	tag { "${meta.id}" }

	input:
	tuple val(meta), path(reads)

	output:
	tuple val(meta), path("output/*.fastq.gz"), emit: reads
	tuple val(meta), path("output/*.log"), emit: log
	path "versions.yml", emit: versions

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env python
import os

from agr.seq.dedupe import dedupe
from agr.util import gunzip, StdioRedirect
from agr.nextflow import write_version

os.makedirs("output", exist_ok=True)

for fastq_file in "${reads}".split():
	out_path = os.path.join("output", fastq_file)
	dedupe(
		in_path=fastq_file,
		out_path=out_path,
		tmp_dir="/tmp", # TODO maybe need tmp_dir on large scratch partition
		jvm_args=[]) # TODO fallback to default of 80g which Dedupe uses if we don't override it here

write_version(
	process_name="${task.process}",
	program_name="BBTools",
	program_version_command=["clumpify.sh", "--version"],
	program_version_capture_regex=r"(?ms).*BBTools version\\s*(\\S+)",
	from_stderr=True,
)
"""
}
