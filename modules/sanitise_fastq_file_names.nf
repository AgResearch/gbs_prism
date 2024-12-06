process SANITISE_FASTQ_FILE_NAMES {
	tag { "${meta.id}" }

	input:
	tuple val(meta), path(reads)

	output:
	tuple val(meta), path("output/*.fastq.gz"), emit: reads

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env python
import os

os.makedirs("output", exist_ok=True)

for maybe_badly_named_file in "${reads}".split():
	bad_suffix = "_fastq.txt.gz"
	good_suffix = ".fastq.gz"
	if maybe_badly_named_file.endswith(bad_suffix):
		fastq_file = "%s%s" % (maybe_badly_named_file.removesuffix(bad_suffix), good_suffix)
	else:
		fastq_file = maybe_badly_named_file
	src = os.path.join("..", maybe_badly_named_file)
	dst = os.path.join("output", fastq_file)
	os.symlink(src, dst)
"""
}
