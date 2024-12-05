process CREATE_GBS_KEYFILES {
	tag { "${meta.id}" }

	input:
	tuple val(meta), val(run_name), path(sample_sheet), path(reads)

	output:
	tuple val(meta), path("output/*_fastq.txt.gz"), emit: reads
	tuple val(meta), path("output/*.generated.txt"), emit: keyfiles
	tuple val(meta), path("output/*.dat"), emit: backups

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env python
import os

from agr.util import gunzip, StdioRedirect
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles

os.makedirs("output", exist_ok=True)

# TODO need to use a published directory here rather than the task workDir, because these get stored in the agrbrdf database
fastq_link_farm = os.path.join(os.getcwd(), "output")

# log_path = "output/create-gbs-keyfiles.log"
# with open(log_path, "w") as log_f:
# 	with StdioRedirect(stdout=log_f, stderr=log_f):
gbs_keyfiles = GbsKeyfiles(
	seq_root="${task.ext.seq_root}",
	run_name="${meta.run_name}",
	sample_sheet="${sample_sheet}",
	fastq_dir=os.getcwd(),
	out_dir="output",
	fastq_link_farm=fastq_link_farm,
	backup_dir="output")

gbs_keyfiles.create()
"""
}
