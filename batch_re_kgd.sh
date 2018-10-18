#!/bin/bash
#
# this does a batrch rerun of kgd, for example after an update to the output manifest
# - it does not rerun tassel, or re-qury the database for cohort info
#

if [ -z "$1" ]; then
   echo "

usage : batch_re_kgd.sh  file_of_run_names

example : batch_re_kgd.sh xaf  "
   exit 1
fi

export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms

for RUN in `cat $1`; do
   OUT_ROOT=/dataset/gseq_processing/scratch/gbs/$RUN
   cohorts=""
   for cohort in $OUT_ROOT/SQ*; do
      if [ ! -d $cohort ]; then
         continue
      fi

      base=`basename $cohort`
      if [ ! -f $OUT_ROOT/${RUN}.${base}.demultiplex ]; then
         echo "skipping ${cohort} - did not see $OUT_ROOT/${RUN}.${base}.demultiplex, and I don't want to do demultiplexing here"
         continue
      fi

      if [ ! -d $cohort/KGD ]; then
         echo "skipping $cohort , no KGD folder"
         continue
      fi

      # here we look for a landmark that the re_kgd has been done 
      # - in general this should be commented out , and control 
      # over which run is processed is done as part of creating the 
      # file of run names
      if [ -f $cohort/KGD/GHW05.vcf ]; then
         echo "skipping $cohort , already done (saw $cohort/KGD/GHW05.vcf)"
         continue
      fi

      if [ ! -f $cohort/KGD/GHW05.RData ]; then
         echo "warning - could not find $cohort/KGD/GHW05.RData (skipping)"
         continue
      fi

      if [ -d $cohort/KGD.orig ]; then
         echo "skipping $RUN as there is already $cohort/KGD.orig - backup or rename $cohort/KGD.orig first"
         continue 
      else
         mv $cohort/KGD $cohort/KGD.orig
      fi 

      base=`basename $cohort`

      cohorts="$base $cohorts"
      rm -f $OUT_ROOT/${RUN}.${base}.kgd
      rm -f $cohort/*.genotype_prism
   done

   echo "running $GBS_PRISM_BIN/ag_gbs_qc_prism.sh -f -C local -a kgd -O $OUT_ROOT -r $RUN $cohorts > $OUT_ROOT/rerun_kgd.log 2>&1"
   $GBS_PRISM_BIN/ag_gbs_qc_prism.sh -f -C local -a kgd -O $OUT_ROOT -r $RUN $cohorts > $OUT_ROOT/rerun_kgd.log 2>&1
   if [ $? != 0 ]; then
      echo "looks like there was a problem (non zero return code) - check $OUT_ROOT/rerun_kgd.log"
   else
      echo "** run looks good **"
   fi
done

echo "** finished **"

