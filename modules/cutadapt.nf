process CUTADAPT {
	tag { "${meta.id}" }

	input:
	tuple val(meta), path(reads)

	output:
	tuple val(meta), path("output/*.fastq.gz"), emit: reads
	path "versions.yml", emit: versions

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env bash

mkdir -p output

for fastq_file in ${reads}; do
	# adapter phrase taken from
	# https://github.com/AgResearch/gbs_prism/blob/dc5a71a6a2c554cd8952614d151a46ddce6892d1/ag_gbs_qc_prism.sh#L292
	#
	# the first 6 from an empirical assembly of recent data which matched
	# Illumina NlaIII Gex Adapter 2.02 1885 TCGTATGCCGTCTTCTGCTTG
	# Illumina DpnII Gex Adapter 2.01 1885 TCGTATGCCGTCTTCTGCTTG
	# Illumina Small RNA 3p Adapter 1 1869 ATCTCGTATGCCGTCTTCTGCTTG
	# Illumina Multiplexing Adapter 1 1426 GATCGGAAGAGCACACGTCT
	# Illumina Universal Adapter 1423 AGATCGGAAGAG
	# Illumina Multiplexing Index Sequencing Primer 1337 GATCGGAAGAGCACACGTCTGAACTCCAGTCAC

	out_file=output/\$(echo \$fastq_file | sed -e 's/\\.fastq/.trimmed.fastq/')
	cutadapt \\
	    -a "TCGTATGCCGTCTTCTGCTTG" \\
	    -a "TCGTATGCCGTCTTCTGCTTG" \\
	    -a "ATCTCGTATGCCGTCTTCTGCTTG" \\
	    -a "GATCGGAAGAGCACACGTCT" \\
	    -a "GATCGGAAGAGCACACGTCT" \\
	    -a "AGATCGGAAGAG" \\
	    -a "GATCGGAAGAGCACACGTCTGAACTCCAGTCAC" \\
	    -a "AGATCGGAAGAGCGGTTCAGCAGGAATGCCGAGACCGATCTCGTATGCCGTCTTCTGCTT" \\
	    -a "AGATCGGAAGAG" \\
	    -a "GATCGGAAGAGCACACGTCT" \\
	    -a "GATCGGAAGAGCACACGTCTGAACTCCAGTCAC" \\
		-o \$out_file \$fastq_file
done

cat <<-END_VERSIONS > versions.yml
"${task.process}":
    cutadapt: \$(cutadapt --version)
END_VERSIONS
"""
}
