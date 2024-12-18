//
// Alignment with bwa
//

include { BWA_LOCALISE_INDEX } from "../bwa/localise_index"
include { FASTQ_ALIGN_BWAALN } from "${NF_CORE}/subworkflows/nf-core/fastq_align_bwaaln"

workflow COHORT_ALIGN_BWA {

    take:
    ch_reads // channel (mandatory): [ val(meta), path(reads) ]. subworkImportant: meta REQUIRES single_end` entry!

    main:

    ch_versions = Channel.empty()

	ch_prepped_input = ch_reads.flatMap {
		v -> v[0].cohort.alignment_references.collect {
			index ->
				def id_index = file(index).getName()
				def id = "${v[0].id}.${id_index}"
				// TODO legacy pipeline only handles single-end reads AFAICT
				[v[0] + [id: id, single_end: true], v[1], index]
		}
	}.view(v -> "ch_prepped_input: ${v}")


    ch_preppedinput_for_bwaaln = ch_prepped_input
        .multiMap {
            meta, reads, index ->
                reads: [ meta, reads ]
                index: [ meta, index ]
        }

    ch_full_index = BWA_LOCALISE_INDEX(	ch_preppedinput_for_bwaaln.index )

	ch_full_index.view{ v -> "full_index: ${v}"}

	ch_preppedinput_for_bwaaln.reads.view(v -> "ch_preppedinput_for_bwaaln reads: ${v}")
	ch_preppedinput_for_bwaaln.index.view(v -> "ch_preppedinput_for_bwaaln index: ${v}")


	FASTQ_ALIGN_BWAALN ( ch_preppedinput_for_bwaaln.reads, ch_full_index.full_index )

 //    emit:
	// aligned = ch_output
}
