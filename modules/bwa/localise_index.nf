// Nextflow nf-core bwa modules assume we have a directory with one set of bwa indexes.
// This process makes such a directory by following the symlink to the .amb file and linking in the rest.
process BWA_LOCALISE_INDEX {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(index)

    output:
    tuple val(meta), path("output/bwa"), emit: full_index

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    mkdir -p output/bwa

	index_dir=\$(dirname \$(readlink $index))
	basename=\$(basename $index .amb)

	ln -s \$index_dir/\$basename* output/bwa
    """
}
