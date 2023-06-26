#!/bin/bash
#
# script to redo genotpying for some historical flowcells using the latest KGD, which provides beta-binomial calibration
#
# method is to use the original genotpying call-back scripts that the q/c pipeline generated, and run them stand-alone, after editing
# to patch the output path  (we do the work in a redo folder, rather than overwrite the original q/c output folder)
#

export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms

#
# we will do the work here - i.e. don't over-write the original GBS processing
WORKDIR=/dataset/2023_illumina_sequencing_b/scratch/postprocessing/gbs_redo_with_latest_KGD_for_beta

# for this lot...
for cohort_path in /dataset/2023_illumina_sequencing_b/scratch/postprocessing/gbs/23*/SQ*; do
  
   # parse the cohort and run names from the path 
   cohort=`basename $cohort_path`
   run=`dirname $cohort_path`
   run=`basename $run`

   if [ ! -f $cohort_path/${cohort}.KGD_tassel3.KGD.stdout ]; then
      echo "skipping as $cohort_path/${cohort}.KGD_tassel3.KGD.stdout - not found"
      continue
   fi

   echo "processing $cohort_path"
 
   # patch the orignal callback - e.g. /dataset/2023_illumina_sequencing_b/scratch/postprocessing/gbs/230414_A01439_0164_AHW5YGDRX2/SQ2081.all.deer.PstI/SQ2081.all.deer.PstI.KGD_tassel3.genotype_prism.sh
   original_callback=$cohort_path/${cohort}.KGD_tassel3.genotype_prism.sh
   redo_callback=$WORKDIR/$run/$cohort/${cohort}.KGD_tassel3.genotype_prism.sh

   echo "writing $WORKDIR/$run/$cohort/${cohort}.KGD_tassel3.genotype_prism.sh"
   mkdir -p $WORKDIR/$run/$cohort/
   cat $original_callback | sed 's/\/hiseq\//\/2023_illumina_sequencing_b\//g' | sed 's/postprocessing\/gbs/postprocessing\/gbs_redo/g' > $redo_callback
   chmod +x $redo_callback

   # copy over or symlink some dependencies that will be needed 
   cp $cohort_path/R_env.src $WORKDIR/$run/$cohort
   cp $cohort_path/gusbase_env.src $WORKDIR/$run/$cohort
   cp $GBS_PRISM_BIN/run_kgd.sh $WORKDIR/$run/$cohort
   cp $GBS_PRISM_BIN/run_kgd.R $WORKDIR/$run/$cohort
   cp $GBS_PRISM_BIN/run_gusbase.sh $WORKDIR/$run/$cohort
   cp $GBS_PRISM_BIN/run_GUSbase.R $WORKDIR/$run/$cohort
   ln -s $cohort_path/hapMap $WORKDIR/$run/$cohort/hapMap
   ln -s $cohort_path/key $WORKDIR/$run/$cohort/key

   # run the genotyping
   echo "excuting  $redo_callback"
   $redo_callback > ${redo_callback}.log 2>&1

   # import the results to the database
   if [ $? != 0 ]; then
      echo "skipping import as genotype_prism returned error" > ${redo_callback}.import.error
      continue
   else
      "running import" 
      gupdate   --explain -t lab_report -p "name=import_gbs_kgd_cohort_stats;file=$WORKDIR/$run/$cohort/${cohort}.KGD_tassel3.KGD.stdout" $run > ${redo_callback}.import 2>&1
   fi
done
