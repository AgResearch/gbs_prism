// Nextflow pipeline for gbs_prism
import groovy.json.JsonSlurper

include { STANDARDISE_SAMPLESHEET } from './modules/standardise_samplesheet.nf'
// TODO use real bclconvert and consider how to include the fake bclconvert as a stub in the real one
include { BCLCONVERT              } from './modules.fake/bclconvert.nf'
// include { BCLCONVERT         } from './modules/bclconvert.nf'
include { FASTQC                  } from "${projectDir}/nf-core/fastqc"
include { SEQTK_SAMPLE_RATE } from "./modules/seqtk/sample_rate.nf"
include { KMER_ANALYSIS } from "./modules/kmer_analysis.nf"
include { DEDUPE } from "./modules/dedupe.nf"
include { CREATE_GBS_KEYFILES } from "./modules/create_gbs_keyfiles.nf"
include { DETERMINE_COHORTS } from "./modules/determine_cohorts.nf"

def parse_cohorts(path) {
    println "parsing cohorts from ${path}"
    cohorts = new JsonSlurper().parse(path)
    println "parsed ${cohorts}"
    return cohorts
}

workflow {
    def meta = [id: params.run_name, run_name: params.run_name]
    def run_dir = "${params.seq_root}/${params.run_name}"
    def raw_samplesheet = "${run_dir}/SampleSheet.csv"

    samplesheet = STANDARDISE_SAMPLESHEET([meta, raw_samplesheet])

    fastq = BCLCONVERT(samplesheet.map { v -> [v[0], v[1], run_dir] }).fastq

    FASTQC(fastq)

    kmer_sample = SEQTK_SAMPLE_RATE(fastq.map { v -> [v[0], v[1], 0.0002, 10000] }).reads

    KMER_ANALYSIS(kmer_sample)

    deduped = DEDUPE(fastq).reads

    // this is a nice way to see what we've got
    // samplesheet.merge(deduped).map(v -> [v[0], params.run_name, v[1], v[3]]).view(v -> "Merge of samplesheet and dedupe: ${v}")

    gbs_keyfiles_reads = CREATE_GBS_KEYFILES(samplesheet.merge(deduped).map(v -> [v[0], params.run_name, v[1], v[3]])).reads

    cohorts = DETERMINE_COHORTS(gbs_keyfiles_reads.map(v -> v[0])).cohorts.map(v -> parse_cohorts(v[1])).view(v -> "cohorts: ${v}")
    cohorts.view(v -> "ready with cohorts ${v}")
}
