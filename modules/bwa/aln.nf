// based on nf-core bwa/aln, simplified
process BWA_ALN {
    tag "$meta.id"
    label 'process_medium'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/bwa:0.7.18--he4a0461_0' :
        'biocontainers/bwa:0.7.18--he4a0461_0' }"

    input:
    tuple val(meta) , path(reads)
    tuple val(meta2), path(index)

    output:
    tuple val(meta), val(reads), val(index), path("output/*.sai"), emit: sai
    path "versions.yml"           , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    """
    mkdir output

    # Nextflow resolves symlinks recursively, which breaks finding the index, as
    # AgR bwa indexes are kept a symlink distance away from the genome, so we hard-code
    # a mapping to mitigate this.  TODO find a better way to handle this.
    index="\$(readlink $index | sed -e 's,/ncbi/genomes/,/ncbi/indexes/bwa/,')"

    for fastq_file in $reads; do
        sai_file="\$(basename \$(basename \$fastq_file .gz) .fastq).sai"
	    bwa aln \\
	        $args \\
	        \$index \\
	        \$fastq_file \\
            >output/\$sai_file
	done

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa: \$(echo \$(bwa 2>&1) | sed 's/^.*Version: //; s/Contact:.*\$//')
END_VERSIONS
    """
}
