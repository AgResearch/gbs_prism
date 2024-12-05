process BCLCONVERT {
    tag { "${meta.lane}" ? "${meta.id}" + "." + "${meta.lane}" : "${meta.id}" }
    label 'process_medium'

    container "nf-core/bclconvert:4.3.6"

    input:
    tuple val(meta), path(samplesheet), path(run_dir)

    output:
    tuple val(meta), path("output/**_S[1-9]*_R?_00?.fastq.gz"), emit: fastq
    tuple val(meta), path("output/**_S[1-9]*_I?_00?.fastq.gz"), optional: true, emit: fastq_idx
    tuple val(meta), path("output/**Undetermined_S0*_R?_00?.fastq.gz"), optional: true, emit: undetermined
    tuple val(meta), path("output/**Undetermined_S0*_I?_00?.fastq.gz"), optional: true, emit: undetermined_idx
    tuple val(meta), path("output/Reports"), emit: reports
    tuple val(meta), path("output/Logs"), emit: logs
    tuple val(meta), path("**/InterOp/*.bin", includeInputs: true), emit: interop
    path ("versions.yml"), emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    #!/usr/bin/env python
    import os

    from agr.seq.sequencer_run import SequencerRun
    from agr.fake.bclconvert import bclconvert

    os.makedirs("output", exist_ok=True)
    bclconvert(in_dir="${run_dir}", sample_sheet_path="${samplesheet}", out_dir="output")

    with open("versions.yml", "w") as versions_f:
        _ = versions_f.write("${task.process}:\\n  fake_bclconvert: 0.1.0\\n")
    """
}
