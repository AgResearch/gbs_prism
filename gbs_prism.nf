// Nextflow pipeline for gbs_prism

include { STANDARDISE_SAMPLESHEET } from './modules/standardise_samplesheet.nf'
// TODO use real bclconvert and consider how to include the fake bclconvert as a stub in the real one
include { BCLCONVERT              } from './modules.fake/bclconvert.nf'
// include { BCLCONVERT         } from './modules/bclconvert.nf'
include { FASTQC                  } from "${projectDir}/nf-core/fastqc"

workflow {
    def meta = [id: params.run_name]
    def run_dir = "${params.seq_root}/${params.run_name}"
    def raw_samplesheet = "${run_dir}/SampleSheet.csv"

    samplesheet = STANDARDISE_SAMPLESHEET([meta, raw_samplesheet])
    BCLCONVERT(samplesheet.map { v -> [v[0], v[1], run_dir] })
    FASTQC(BCLCONVERT.out.fastq)
}
