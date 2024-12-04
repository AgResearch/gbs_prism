// Nextflow pipeline for gbs_prism

include { STANDARDISE_SAMPLESHEET } from './modules/standardise_samplesheet.nf'
// TODO use real bclconvert and consider how to include the fake bclconvert as a stub in the real one
include { BCLCONVERT              } from './modules.fake/bclconvert.nf'
// include { BCLCONVERT         } from './modules/bclconvert.nf'
include { FASTQC                  } from "${projectDir}/nf-core/fastqc"
include { SEQTK_SAMPLE_RATE } from "./modules/seqtk/sample_rate.nf"
include { KMER_ANALYSIS } from "./modules/kmer_analysis.nf"
include { DEDUPE } from "./modules/dedupe.nf"

workflow {
    def meta = [id: params.run_name]
    def run_dir = "${params.seq_root}/${params.run_name}"
    def raw_samplesheet = "${run_dir}/SampleSheet.csv"

    samplesheet = STANDARDISE_SAMPLESHEET([meta, raw_samplesheet])
    fastq = BCLCONVERT(samplesheet.map { v -> [v[0], v[1], run_dir] }).fastq
    FASTQC(fastq)
    kmer_sample = SEQTK_SAMPLE_RATE(fastq.map { v -> [v[0], v[1], 0.0002, 10000] }).reads
    KMER_ANALYSIS(kmer_sample)
    DEDUPE(fastq)
}
