// Nextflow pipeline for gbs_prism
import groovy.json.JsonSlurper

include { STANDARDISE_SAMPLESHEET } from './modules/standardise_samplesheet.nf'
// TODO use real bclconvert and consider how to include the fake bclconvert as a stub in the real one
include { BCLCONVERT              } from './modules.fake/bclconvert.nf'
// include { BCLCONVERT         } from './modules/bclconvert.nf'
include { FASTQC                  } from "${projectDir}/nf-core/fastqc"
include { SEQTK_SAMPLE_RATE as SAMPLE_FOR_KMER_ANALYSIS } from "./modules/seqtk/sample_rate.nf"
include { SEQTK_SAMPLE_RATE as SAMPLE_FOR_BWA } from "./modules/seqtk/sample_rate.nf"
include { KMER_ANALYSIS } from "./modules/kmer_analysis.nf"
include { DEDUPE } from "./modules/dedupe.nf"
include { CREATE_GBS_KEYFILES } from "./modules/create_gbs_keyfiles.nf"
include { DETERMINE_COHORTS } from "./modules/determine_cohorts.nf"
include { SANITISE_FASTQ_FILE_NAMES } from "./modules/sanitise_fastq_file_names.nf"
include { CUTADAPT } from "./modules/cutadapt.nf"

def parse_cohorts(path) {
    new JsonSlurper().parse(path)
}

process COUNT_READS {
	debug true
	tag { "${meta.id}" }
	
	input:
	// each tuple is not supported, but without it we only get called once, for the first element
	// each tuple(val(meta), path(reads))
	tuple(val(meta), path(reads))

	output:
	tuple val(meta), path("output/*.count"), emit: count

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env bash
mkdir -p output
for fastq_file in ${reads}; do
	zcat \$fastq_file | wc -l > output/\$fastq_file.count
done
"""
}


workflow {
    def meta = [id: params.run_name, run_name: params.run_name]
    def run_dir = "${params.seq_root}/${params.run_name}"
    def raw_samplesheet = "${run_dir}/SampleSheet.csv"

    samplesheet = STANDARDISE_SAMPLESHEET([meta, raw_samplesheet])

    fastq = BCLCONVERT(samplesheet.map { v -> [v[0], v[1], run_dir] }).fastq

    FASTQC(fastq)

    sample_for_kmer_analysis = SAMPLE_FOR_KMER_ANALYSIS(fastq).reads

    KMER_ANALYSIS(sample_for_kmer_analysis)

    deduped = DEDUPE(fastq).reads

    // this is a nice way to see what we've got
    // samplesheet.merge(deduped).map(v -> [v[0], params.run_name, v[1], v[3]]).view(v -> "Merge of samplesheet and dedupe: ${v}")

    gbs_keyfiles_reads = CREATE_GBS_KEYFILES(samplesheet.merge(deduped).map(v -> [v[0], params.run_name, v[1], v[3]])).reads

    cohorts = DETERMINE_COHORTS(gbs_keyfiles_reads.map(v -> v[0])).cohorts_path.map(v -> parse_cohorts(v[1])) // .view(v -> "cohorts: ${v}")

    // TODO fold this into DETERMINE_COHORTS by making that a workflow not just a process:
    badly_named_cohort_reads = cohorts.map(cohorts ->
		cohorts.collect { cohort ->
			def fastq_links2 = cohort.remove('fastq_links')
			[
			    [
				    id: "${params.run_name}.${cohort.name}",
				    run_name: params.run_name,
					cohort: cohort
				],
				fastq_links2
			]
		}
	).flatMap() //.view(v -> "cohort_reads: ${v}")

    // TODO maybe also fold this one in, the bad names are so annoying
    // because they break the globbing that Nextflow does to determine process output
    cohort_reads = SANITISE_FASTQ_FILE_NAMES(badly_named_cohort_reads)

	COUNT_READS(cohort_reads)

    sample_for_bwa = SAMPLE_FOR_BWA(cohort_reads).reads

    trimmed = CUTADAPT(sample_for_bwa)
}
