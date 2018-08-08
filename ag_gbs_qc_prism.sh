#!/bin/bash
#
# this prism supports a basic q/c gbs analysis, of data that is assumed to be 
# generated and hosted by AgResearch  - i.e. there are dependencies on the 
# database etc. It assumes that the demultiplex prism has been run.
# 
#

declare -a files_array

function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_ROOT=""
   FORCE=no
   ENGINE=KGD_tassel3

   help_text=$(cat << 'EOF'
usage :\n 
./ag_gbs_qc_prism.sh  [-h] [-n] [-d] -O outdir cohort \n
example:\n
./ag_gbs_qc_prism.sh -n -O /dataset/hiseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI  SQ2745.all.PstI.PstI  SQ2746.all.PstI.PstI  SQ0756.all.DEER.PstI  SQ0756.all.GOAT.PstI  SQ2743.all.PstI-MspI.PstI-MspI \n
./ag_gbs_qc_prism.sh -n -f -O /dataset/hiseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI SQ2745.all.PstI.PstI SQ2746.all.PstI.PstI SQ0756.all.DEER.PstI SQ0756.all.GOAT.PstI SQ2743.all.PstI-MspI.PstI-MspI
EOF
)
   while getopts ":nhfO:C:r:" opt; do
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
       C)
         HPC_TYPE=$OPTARG
         ;;
       O)
         OUT_ROOT=$OPTARG
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

   COHORT_STRING=$@

   # this is needed because of the way we process args a "$@" - which
   # is needed in order to parse parameter sets to be passed to the
   # aligner (which are space-separated)
   declare -a cohorts="(${COHORT_STRING})";
   NUM_COHORTS=${#cohorts[*]}
   for ((i=0;$i<$NUM_COHORTS;i=$i+1)) do
      cohorts_array[$i]=${cohorts[$i]}
   done

}


function check_opts() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "please set SEQ_PRISMS_BIN environment variable"
      exit 1
   fi

   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "please set GBS_PRISM_BIN environment variable"
      exit 1
   fi

   if [ ! -d $OUT_ROOT ]; then
      echo "out_dir $OUT_ROOT not found"
      exit 1
   fi

   if [[ $HPC_TYPE != "local" && $HPC_TYPE != "slurm" ]]; then
      echo "HPC_TYPE must be one of local, slurm"
      exit 1
   fi

   if [[ ( $ENGINE != "KGD_tassel3" ) ]] ; then
      echo "gbs engines supported : KGD_tassel3 (not $ENGINE ) "
      exit 1
   fi

}

function echo_opts() {
  echo OUT_ROOT=$OUT_ROOT
  echo DRY_RUN=$DRY_RUN
  echo DEBUG=$DEBUG
  echo HPC_TYPE=$HPC_TYPE
  echo COHORTS=${cohorts_array[*]}
  echo ENGINE=$ENGINE
}


#
# edit this method to set required environment (or set up
# before running this script)
#
function configure_env() {
   cd $GBS_PRISM_BIN
   cp ag_gbs_qc_prism.sh $OUT_ROOT
   cp ag_gbs_qc_prism.mk $OUT_ROOT
   cp demultiplex_prism.sh $OUT_ROOT
   cp genotype_prism.sh $OUT_ROOT
   cp get_cohort_fastq_filenames.psql $OUT_ROOT


   echo "
max_tasks=50
" > $OUT_ROOT/tardis.toml
   cd $OUT_ROOT
}


function check_env() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "SEQ_PRISMS_BIN not set - exiting"
      exit 1
   fi
   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "GBS_PRISM_BIN not set - exiting"
      exit 1
   fi

}


function get_targets() {
   # for each cohort make a target moniker  and write associated
   # wrapper, which will be called by make

   rm -f $OUTPUT_ROOT/ag_gbs_qc_targets.txt

   for ((j=0;$j<$NUM_COHORTS;j=$j+1)) do
      cohort=${cohorts_array[$j]}
      cohort_moniker=${RUN}.$cohort
      echo $OUT_ROOT/$cohort_moniker.ag_gbs_qc_prism >> $OUT_ROOT/ag_gbs_qc_prism_targets.txt
      script=$OUT_ROOT/${cohort_moniker}.sh
      if [ -f $script ]; then
         if [ ! $FORCE == yes ]; then
            echo "found existing gbs script $script  - will re-use (use -f to force rebuild of scripts) "
            continue
         fi
      fi

      # extract keyfile and unblinding script for this cohort
      # cohort is like SQ0756.all.DEER.PstI
      libname=`echo $cohort | awk -F\. '{print $1}' -`        
      qc_cohort=`echo $cohort | awk -F\. '{print $2}' -` 
      gbs_cohort=`echo $cohort | awk -F\. '{print $3}' -` 
      enzyme=`echo $cohort | awk -F\. '{print $4}' -` 
      fcid=`echo $RUN | awk -F_ '{print substr($4,2)}' -`


      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t qc > $OUT_ROOT/${cohort_moniker}.key
      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t unblind_script  > $OUT_ROOT/${cohort_moniker}.unblind.sed
      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t files  > $OUT_ROOT/${cohort_moniker}.filenames

      echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort
# run demultiplexing
./demultiplex_prism.sh -C $HPC_TYPE -x tassel3_qc -l $OUT_ROOT/${cohort_moniker}.key  -e $enzyme -O $OUT_ROOT/$cohort \`cat $OUT_ROOT/${cohort_moniker}.filenames | awk '{print \$2}' -\` 
if [ $? != 0 ]; then
   echo \"demultiplex of $OUT_ROOT/${cohort_moniker}.key returned an error code - will not attempt genotyping\"
   exit 1
fi
# run genotyping
./genotype_prism.sh -C $HPC_TYPE -x KGD_tassel3 $OUT_ROOT/$cohort
if [ $? != 0 ]; then
   echo \"warning , genotyping of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
     " > $script
      chmod +x $script
   done
}


function fake_prism() {
   echo "dry run ! 

   "
   exit 0
}

function run_prism() {
   cd $OUT_ROOT
   make -f ag_gbs_qc_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_ROOT/ag_gbs_qc_prism_targets.txt` > $OUT_ROOT/ag_gbs_qc_prism.log 2>&1

   # run summaries
}

function html_prism() {
   echo "tba" > $OUT_ROOT/ag_gbs_qc_prism.html 2>&1
}

function clean() {
   echo "skipping clean for now"
   #rm -rf $OUT_ROOT/tardis_*
   #rm $OUT_ROOT/*.fastq
}


function main() {
   get_opts "$@"
   check_opts
   echo_opts
   check_env
   configure_env
   get_targets
   if [ $DRY_RUN != "no" ]; then
      fake_prism
   else
      run_prism
      if [ $? == 0 ] ; then
         html_prism
         clean
      else
         echo "error state from sample run - skipping html page generation and clean-up"
         exit 1
      fi
   fi
}


set -x
main "$@"
set +x
