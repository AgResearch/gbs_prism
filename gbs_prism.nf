// Nextflow pipeline for gbs_prism

include { CLEAN_SAMPLESHEET } from './modules/clean_samplesheet.nf'
// TODO use real bclconvert and consider how to include the fake bclconvert as a stub in the real one
include { BCLCONVERT         } from './modules.fake/bclconvert.nf'
// include { BCLCONVERT         } from './modules/bclconvert.nf'

workflow {
    def meta = [:]
    def run_dir = "${params.seq_root}/${params.run_name}"
    def raw_samplesheet = "${run_dir}/SampleSheet.csv"

    clean_samplesheet = CLEAN_SAMPLESHEET(raw_samplesheet)
    BCLCONVERT(clean_samplesheet.map { v -> [meta, v, run_dir] })
}
