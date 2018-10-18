#!/bin/sh
#
# batch  script for reprocessing a hiseq run through GBS analysis (i.e. after the initial run, which 
# did database import - e.g. to apply a later version of KGD). This script requeries the database, reruns tassel as 
# well as reruns kgd. (Use batch_re_kgd.sh to just rerun kgd)
#

export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms 
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
BCL2FASTQ_NODE=invbfopp10.agresearch.co.nz   # iramohio-01

gbs_version=$1


function get_processing_parameters() {
   PARAMETERS_FILE=$OUTPUT_ROOT/SampleProcessing.json
   tardis -d $OUTPUT_ROOT --hpctype local $GBS_PRISM_BIN/get_processing_parameters.py --json_out_file $OUTPUT_ROOT/SampleProcessing.json --parameter_file $SAMPLE_SHEET --species_references_file  /dataset/hiseq/active/sample-sheets/reference_genomes.csv
}



function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_ROOT=""
   SNP_ENGINE=tassel        # the only one supported at this point
   RUN=""

   HISEQ_ROOT=/dataset/hiseq/active
   MISEQ_ROOT=/dataset/miseq/active

   HISEQ_PROCESSING_ROOT=/dataset/gseq_processing/scratch/gbs
   # there is no MISEQ version of that as processing miseq using this script not supported currently 
  
   HISEQ_BCL2FASTQ_ROOT=/dataset/gseq_processing/scratch/illumina/hiseq
   # there is no MISEQ version of that as processing miseq using this script not supported currently 

   help_text="
examples:\n
\n
   ./reprocess_gbs_qc.sh -n -r 170609_D00390_0305_BCA93MANXX -O /dataset/gseq_processing/scratch/gbs/170609_D00390_0305_BCA93MANXX  /dataset/hiseq_archive_1/archive/run_archives/170609_D00390_0305_BCA93MANXX/SampleSheet.csv\n
   ./reprocess_gbs_qc.sh -n -r 160829_D00390_0263_BC9NR8ANXX -O /dataset/gseq_processing/scratch/gbs/160829_D00390_0263_BC9NR8ANXX /dataset/hiseq_archive_1/archive/run_archives/160829_D00390_0263_BC9NR8ANXX/SampleSheet.csv\n
\n
"


   while getopts ":nhfO:C:r:a:" opt; do
   case $opt in
       n)
         DRY_RUN=yes
         ;;
       d)
         DEBUG=yes
         ;;
       f)
         FORCE=yes
         ;;
       h)
         echo -e $help_text
         exit 0
         ;;
       r)
         RUN=$OPTARG
         ;;
       a)
         ANALYSIS=$OPTARG
         ;;
       C)
         HPC_TYPE=$OPTARG
         ;;
       \?)
         echo "Invalid option: -$OPTARG" >&2
         exit 1
         ;;
       :)
         echo "Option -$OPTARG requires an argument." >&2
         exit 1
         ;;
     esac
   done

   shift $((OPTIND-1))

   SAMPLE_SHEET=$@

   gbs_ROOT=$HISEQ_ROOT
   PROCESSING_ROOT=$HISEQ_PROCESSING_ROOT
   BCL2FASTQ_ROOT=$HISEQ_BCL2FASTQ_ROOT
}


function check_opts() {
   if [ -z "$RUN" ]; then
      echo "please specify a run (-r ) "
      exit 1
   fi

   if [ ! -f "$SAMPLE_SHEET" ]; then
      echo "no such sample sheet , $SAMPLE_SHEET"
      exit 1
   fi
}


function run_gbs() {

   OUTPUT_ROOT=$PROCESSING_ROOT/$RUN

   if [ -d $OUTPUT_ROOT ]; then
      echo "*** $OUTPUT_ROOT already exists - please rename or delete. Quitting ***"
      exit 1
   fi
   mkdir -p $OUTPUT_ROOT
   if [ ! -d $OUTPUT_ROOT ]; then
      echo "*** could not create $OUTPUT_ROOT - quitting ***"
      exit 1
   fi

   # need to sanitise sample sheet
   cat $SAMPLE_SHEET | $GBS_PRISM_BIN/sanitiseSampleSheet.py --supply_missing -r $RUN > $OUTPUT_ROOT/SampleSheet.csv
   SAMPLE_SHEET=$OUTPUT_ROOT/SampleSheet.csv

   in_db=`$GBS_PRISM_BIN/is_run_in_database.sh $RUN | sed 's/\s//g' -`
   if [ $in_db == "0" ]; then
      echo "$RUN is not in the database - can't run GBS"
      exit 1
   fi

   ANALYSIS=kgd

   get_processing_parameters  

   LIBRARY_MONIKERS=`psql -U agrbrdf -d agrbrdf -h invincible -v run=\'$RUN\' -f $GBS_PRISM_BIN/get_run_samples.psql -q`
   gbs_cohorts=""
   for library_moniker in $LIBRARY_MONIKERS; do
       library_cohorts=`tardis -q -d $OUTPUT_ROOT --hpctype local $GBS_PRISM_BIN/get_processing_parameters.py --parameter_file $PARAMETERS_FILE --parameter_name cohorts  --sample $library_moniker`
       for library_cohort in $library_cohorts; do
          gbs_cohorts="$gbs_cohorts ${library_moniker}.${library_cohort} "
       done
   done
   GBS_COHORTS=$gbs_cohorts

   if [ $DRY_RUN != "no" ]; then
      echo "will execute 

      $GBS_PRISM_BIN/ag_gbs_qc_prism.sh -f -C $HPC_TYPE -a $ANALYSIS -O $OUTPUT_ROOT -r $RUN $GBS_COHORTS 

      (dry run only) 
      "
   else
      $GBS_PRISM_BIN/ag_gbs_qc_prism.sh -f -C $HPC_TYPE -a $ANALYSIS -O $OUTPUT_ROOT -r $RUN $GBS_COHORTS  > $OUTPUT_ROOT/reprocess_gbs_qc.log 2>&1
   fi

}


get_opts "$@"
check_opts
run_gbs 

