//
// Alignment with bwa aln and sort
//

include { BWA_ALN            } from "${projectDir}/nf-core/bwa/aln/main"
include { BWA_SAMSE          } from "${projectDir}/nf-core/bwa/samse/main"
include { BWA_SAMPE          } from "${projectDir}/nf-core/bwa/sampe/main"
include { SAMTOOLS_INDEX     } from "${projectDir}/nf-core/samtools/index/main"

// based on nf-core fastq_align_bwaaln
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
				[v[0] + [id: id], v[1], index]
		}
	}.view(v -> "ch_prepped_input: ${v}")

    ch_preppedinput_for_bwaaln = ch_prepped_input
        .multiMap {
            meta, reads, index ->
                reads: [ meta, reads ]
                index: [ meta, index ]
        }
	// ch_preppedinput_for_bwaaln.reads.view(v -> "ch_preppedinput_for_bwaaln reads: ${v}")
	// ch_preppedinput_for_bwaaln.index.view(v -> "ch_preppedinput_for_bwaaln index: ${v}")


    // Set as independent channel to allow repeated joining but _with_ sample specific metadata
    // to ensure right reference goes with right sample
    // ch_reads_newid = ch_prepped_input.map{ meta, reads, index -> [ meta, reads ] }
    // ch_index_newid = ch_prepped_input.map{ meta, reads, index -> [ meta, index ] }

    // Alignment and conversion to bam
    BWA_ALN ( ch_preppedinput_for_bwaaln.reads, ch_preppedinput_for_bwaaln.index )
    // ch_versions = ch_versions.mix( BWA_ALN.out.versions.first() )

    // ch_sai_for_bam = ch_reads_newid
    //                     .join ( BWA_ALN.out.sai )
    //                     .branch {
    //                         meta, reads, sai ->
    //                             pe: !meta.single_end
    //                             se: meta.single_end
    //                     }

    // Split as PE/SE have different SAI -> BAM commands
    // ch_sai_for_bam_pe =  ch_sai_for_bam.pe
    //                         .join ( ch_index_newid )
    //                         .multiMap {
    //                             meta, reads, sai, index ->
    //                                 reads: [ meta, reads, sai ]
    //                                 index: [ meta, index      ]
    //                         }

    // ch_sai_for_bam_se =  ch_sai_for_bam.se
    //                         .join ( ch_index_newid )
    //                         .multiMap {
    //                             meta, reads, sai, index ->
    //                                 reads: [ meta, reads, sai ]
    //                                 index: [ meta, index      ]
    //                         }


    // BWA_SAMPE ( ch_sai_for_bam_pe.reads, ch_sai_for_bam_pe.index )
    // ch_versions = ch_versions.mix( BWA_SAMPE.out.versions.first() )

    // BWA_SAMSE ( ch_sai_for_bam_se.reads, ch_sai_for_bam_se.index )
    // ch_versions = ch_versions.mix( BWA_SAMSE.out.versions.first() )

    // ch_bam_for_index = BWA_SAMPE.out.bam.mix( BWA_SAMSE.out.bam )

    // Index all
    // SAMTOOLS_INDEX ( ch_bam_for_index )
    // ch_versions = ch_versions.mix(SAMTOOLS_INDEX.out.versions.first())

    // Remove superfluous internal maps to minimise clutter as much as possible
    // ch_bam_for_emit = ch_bam_for_index.map{ meta, bam -> [meta - meta.subMap('key_read_ref'), bam] }
    // ch_bai_for_emit = SAMTOOLS_INDEX.out.bai.map{ meta, bai -> [meta - meta.subMap('key_read_ref'), bai] }
    // ch_csi_for_emit = SAMTOOLS_INDEX.out.csi.map{ meta, csi -> [meta - meta.subMap('key_read_ref'), csi] }

    // emit:
    // Note: output channels will contain meta with additional 'id_index' meta
    // value to allow association of BAM file with the meta.id of input indicies
    // bam      = ch_bam_for_emit     // channel: [ val(meta), path(bam) ]
    // bai      = ch_bai_for_emit     // channel: [ val(meta), path(bai) ]
    // csi      = ch_csi_for_emit     // channel: [ val(meta), path(csi) ]

    // versions = ch_versions         // channel: [ path(versions.yml) ]
}
