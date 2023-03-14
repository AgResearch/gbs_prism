#!/bin/bash
#
# Simple demo of custom multi-library keyfile GBS processing support
#
# The script below extracts multi-library keyfiles containing all GBS samples for two species (takahe and kakapo), for each enzyme they were GBS’d with,
# and does a demultiplexing and KGD run for each
#
set -x
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism


# set up
WORKDIR=/dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo
mkdir $WORKDIR
echo 'MergeTaxaTagCount -t n' > $WORKDIR/demultiplexing_parameters.txt # this tassel option will be passed to the MergeTaxaTagCount plugin - keeps lanes distinct which we do for novaseq, as part of KGD normalisation


# for each distinct enzyme, get keyfile, and set up and run demultiplex and KGD
for enzyme in `gquery -t gbs_keyfile -b taxname -p "columns=enzyme;distinct;noheading" takahe kakapo`; do
   mkdir -p $WORKDIR/$enzyme

   # get keyfile for this enzyme. Note that we need to use the "qc_sampleid" safe-sample-names, as the supplied sample names for these birds have embedded spaces and other features
   # which cause processing problems downstream. (See below where an "unblinding" script is extracted, that can be used to edit the text output files to map back to the original sampleid)
   # (for other cases, such as deer or goats, with less feral sample names, you could probably just used the original sampleid, so the gquery extract command would then be
   # gquery -t gbs_keyfile -b taxname -p "enzyme=$enzyme;columns=flowcell,lane,barcode,sample,platename,...
   gquery -t gbs_keyfile -b taxname -p "enzyme=$enzyme;columns=flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link" takahe kakapo  > $WORKDIR/$enzyme/sample_info.key

   #run demultiplex – this handles launching demultiplex of each library separately, so we don’t confuse tassel3
   $GBS_PRISM_BIN/demultiplex_prism.sh -C slurm -x tassel3_qc -l $WORKDIR/$enzyme/sample_info.key -p $WORKDIR/demultiplexing_parameters.txt -e $enzyme -O $WORKDIR/$enzyme `gquery -t gbs_keyfile -b taxname -p "columns=fastq_link;distinct;noheading" takahe kakapo`

   #run KGD
   $GBS_PRISM_BIN/genotype_prism.sh -C slurm  -x KGD_tassel3 -p default $WORKDIR/$enzyme

   # get a "sed" script that can be used to unblind the results – i.e. map the safe-sampleids back to the sampleid’s that were supplied
   gquery -t gbs_keyfile -b taxname -p "enzyme=$enzyme;unblinding;columns=qc_sampleid,sample;noheading" takahe kakapo  > $WORKDIR/$enzyme/unblinding_script.sed

   # examples of using the sed script:
   #cat /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/TagCount.csv | sed -f /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/unblinding_script.sed
   #cat /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/KGD/GHW05.vcf | sed -f /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/unblinding_script.sed
   #cat /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/KGD/GHW05-PC.csv | sed -f /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/takahe_kakapo/PstI-MspI/unblinding_script.sed

done
