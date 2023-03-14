#!/bin/bash
#
# Demo of custom multi-library keyfile GBS processing support
#
# The script below extracts multi-library keyfiles containing all GBS samples for libraries SQ2999, SQ3000, SQ3001, SQ3002, SQ3003, SQ3004  for each enzyme they were GBS’d with,
# and does a demultiplexing and KGD run for each
#
set -x
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism


# set up
WORKDIR=/dataset/hiseq/scratch/postprocessing/gbs/ryegrass_check 
mkdir $WORKDIR
echo 'MergeTaxaTagCount -t n' > $WORKDIR/demultiplexing_parameters.txt # this tassel option will be passed to the MergeTaxaTagCount plugin - keeps lanes distinct which we do for novaseq, as part of KGD normalisation


function demultiplex_kgd() {

   # for each distinct enzyme, get keyfile, and set up and run demultiplex and KGD
   for enzyme in `gquery -t gbs_keyfile -b library -p "columns=enzyme;distinct;noheading" SQ2999 SQ3000 SQ3001 SQ3002 SQ3003 SQ3004`; do
      mkdir -p $WORKDIR/$enzyme

      # get keyfile for this enzyme. Note that to be safe we elect to use the "qc_sampleid" safe-sample-names, in case the supplied sample names have features like embedded spaces etc. 
      # which cause processing problems downstream. (See below where an "unblinding" script is extracted, that can be used to edit the text output files to map back to the original sampleid)
      # (if you want to use the original sampleid - usually OK - the gquery extract command would then be
      # gquery -t gbs_keyfile -b library -p "enzyme=$enzyme;columns=flowcell,lane,barcode,sample,platename,...
      gquery -t gbs_keyfile -b library -p "enzyme=$enzyme;columns=flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link" SQ2999 SQ3000 SQ3001 SQ3002 SQ3003 SQ3004  > $WORKDIR/$enzyme/sample_info.key

      #run demultiplex – this handles launching demultiplex of each library separately, so we don’t confuse tassel3 ! 
      $GBS_PRISM_BIN/demultiplex_prism.sh -C slurm -x tassel3_qc -l $WORKDIR/$enzyme/sample_info.key -p $WORKDIR/demultiplexing_parameters.txt -e $enzyme -O $WORKDIR/$enzyme `gquery -t gbs_keyfile -b library -p "columns=fastq_link;distinct;noheading"  SQ2999 SQ3000 SQ3001 SQ3002 SQ3003 SQ3004`

      #run KGD
      $GBS_PRISM_BIN/genotype_prism.sh -C slurm  -x KGD_tassel3 -p default $WORKDIR/$enzyme

      # get a "sed" script that can be used to unblind the results – i.e. map the safe-sampleids back to the sampleid’s that were supplied
      gquery -t gbs_keyfile -b library -p "enzyme=$enzyme;unblinding;columns=qc_sampleid,sample;noheading" SQ2999 SQ3000 SQ3001 SQ3002 SQ3003 SQ3004 > $WORKDIR/$enzyme/unblinding_script.sed

      # examples of using the sed script:
      #cat $WORKDIR/$enzyme/TagCount.csv | sed -f $WORKDIR/$enzyme/unblinding_script.sed
      #cat $WORKDIR/$enzyme/GHW05.vcf | sed -f $WORKDIR/$enzyme/unblinding_script.sed
      #cat $WORKDIR/$enzyme/GHW05-PC.csv | sed -f $WORKDIR/$enzyme/unblinding_script.sed

   done
}


function unblind() {
   for enzyme in `gquery -t gbs_keyfile -b library -p "columns=enzyme;distinct;noheading" SQ2999 SQ3000 SQ3001 SQ3002 SQ3003 SQ3004`; do
      for file in  $WORKDIR/$enzyme/TagCount.csv $WORKDIR/$enzyme/*.KGD_tassel3.KGD.stdout $WORKDIR/$enzyme/KGD/*.csv $WORKDIR/$enzyme/KGD/*.tsv $WORKDIR/$enzyme/KGD/*.vcf $WORKDIR/$enzyme/hapMap/HapMap.hmc.txt $WORKDIR/$enzyme/hapMap/HapMap.hmp.txt ; do
         if [ -f $file ]; then
            if [ ! -f $file.blinded ]; then
               cp -p $file $file.blinded
            fi
            cat $file.blinded | sed -f $WORKDIR/$enzyme/unblinding_script.sed  > $file
         fi
      done
   done
}

demultiplex_kgd
unblind
