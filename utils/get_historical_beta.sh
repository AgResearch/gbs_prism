#!/bin/bash

#for cohort_path in /dataset/2023_illumina_sequencing_a/scratch/postprocessing/gbs/22*/SQ*; do
for cohort_path in /dataset/2023_illumina_sequencing_a/scratch/postprocessing/gbs/23*/SQ*; do
   cohort=`basename $cohort_path`
   run=`dirname $cohort_path`
   run=`basename $run`
   if [ -f $cohort_path/${cohort}.KGD_tassel3.KGD.stdout ]; then
      cmd="gupdate  --explain -t lab_report -p \"name=import_gbs_kgd_cohort_stats;file=$cohort_path/${cohort}.KGD_tassel3.KGD.stdout\" $run"
      echo $cmd
      gupdate  --explain -t lab_report -p "name=import_gbs_kgd_cohort_stats;file=$cohort_path/${cohort}.KGD_tassel3.KGD.stdout" $run
   else
      echo "skipping  $cohort_path/${cohort}.KGD_tassel3.KGD.stdout - not found"
   fi
done
