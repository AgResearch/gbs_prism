// based on nf-core/seqtk/sample
process SEQTK_SAMPLE_RATE {
	tag "${meta.id}"
	label 'process_single'

	conda "${moduleDir}/environment.yml"
	container "${workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container
		? 'https://depot.galaxyproject.org/singularity/seqtk:1.4--he4a0461_1'
		: 'biocontainers/seqtk:1.4--he4a0461_1'}"

	input:
	tuple val(meta), path(reads)

	output:
	tuple val(meta), path("output/*.fastq.gz"), emit: reads
	path "versions.yml", emit: versions

	when:
	task.ext.when == null || task.ext.when

	script:
	def args = task.ext.args ?: ''
	def prefix = task.ext.prefix ?: "${meta.id}"
	if (!(args ==~ /.*-s[0-9]+.*/)) {
		args += " -s100"
	}
	if (!task.ext.sample_rate) {
		error("SEQTK/SAMPLE_RATE must have a sample_rate value included")
	}
	if (!task.ext.minimum_sample_size) {
		error("SEQTK/SAMPLE_RATE must have a minimum_sample_size value included")
	}
	"""
#!/usr/bin/env python
import os.path
from agr.seq.fastq_sample import FastqSample
from agr.util import gzip
from agr.nextflow import write_version

os.makedirs("output", exist_ok=True)

fastq_sample = FastqSample(sample_rate=${task.ext.sample_rate}, minimum_sample_size=${task.ext.minimum_sample_size})
for fastq_file in "${reads}".split():
	out_path="output/${prefix}_%s" % os.path.basename(fastq_file).removesuffix(".gz")
	fastq_sample.run(in_path=fastq_file, out_path=out_path)
	gzip(out_path)

write_version(
	process_name="${task.process}",
	program_name="seqtk",
	program_version_command=["seqtk"],
	program_version_capture_regex=r"(?ms).*^Version:\\s*(\\S+)",
	from_stderr=True,
)
	"""

	stub:
	def prefix = task.ext.prefix ?: "${meta.id}"

	"""
    echo "" | gzip > ${prefix}.fastq.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        seqtk: \$(echo \$(seqtk 2>&1) | sed 's/^.*Version: //; s/ .*\$//')
    END_VERSIONS
    """
}
