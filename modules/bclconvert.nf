process BCLCONVERT {
    tag {"$meta.lane" ? "$meta.id"+"."+"$meta.lane" : "$meta.id" }
    label 'process_high'

    container "nf-core/bclconvert:4.3.6"

    input:
    tuple val(meta), path(samplesheet), path(run_dir)

    output:
    tuple val(meta), path("output/**_S[1-9]*_R?_00?.fastq.gz")           , emit: fastq
    tuple val(meta), path("output/**_S[1-9]*_I?_00?.fastq.gz")           , optional:true, emit: fastq_idx
    tuple val(meta), path("output/**Undetermined_S0*_R?_00?.fastq.gz")   , optional:true, emit: undetermined
    tuple val(meta), path("output/**Undetermined_S0*_I?_00?.fastq.gz")   , optional:true, emit: undetermined_idx
    tuple val(meta), path("output/Reports")                              , emit: reports
    tuple val(meta), path("output/Logs")                                 , emit: logs
    tuple val(meta), path("**/InterOp/*.bin", includeInputs: true), emit: interop
    path("versions.yml")                                          , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    bcl-convert \\
        ${args} \\
        --output-directory output \\
        --bcl-input-directory ${run_dir} \\
        --sample-sheet ${samplesheet}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bclconvert: \$(bcl-convert -V 2>&1 | head -n 1 | sed 's/^.*Version //')
    END_VERSIONS
    """
}
