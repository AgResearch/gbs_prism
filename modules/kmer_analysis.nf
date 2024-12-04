process KMER_ANALYSIS {
	tag { "${meta.id}" }

	input:
	tuple val(meta), path(reads)

	output:
	tuple val(meta), path("output/*.1"), emit: analysis
	tuple val(meta), path("output/*.log"), emit: log
	path "versions.yml", emit: versions

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env python
import os

from agr.gbs_prism.kmer_prism import KmerPrism
from agr.util import gunzip, StdioRedirect

os.makedirs("output", exist_ok=True)

# currently we don't expose the kmer prism parameters

kmer_prism = KmerPrism(
	input_filetype="fasta",
	kmer_size=6,
	# this causes it to crash: 😩
	#assemble_low_entropy_kmers=True
)

for fastq_file in "${reads}".split():
	if fastq_file.endswith(".gz"):
		remove = True
		in_path = gunzip(fastq_file)
	else:
		remove = False
		in_path = fastq_file

	out_path = os.path.join("output", "%s.%s.1" % (fastq_file, kmer_prism.moniker))
	log_path = "%s.log" % out_path.removesuffix(".1")
	with open(log_path, "w") as log_f:
		with StdioRedirect(stdout=log_f, stderr=log_f):
			kmer_prism.run([in_path], output_filename=out_path)

with open("versions.yml", "w") as versions_f:
	_ = versions_f.write("${task.process}:\\n  fake_bclconvert: 0.1.0\\n")
"""
}
