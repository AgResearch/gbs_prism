#!/bin/sh

if [ -z "$GBS_PRISM_BIN" ]; then
   echo "GBS_PRISM_BIN not set - quitting"
   exit 1
fi

#!/bin/sh

function get_opts() {

help_text="\n
      usage : import_hiseq_reads_tags_cv.sh -r run_name\n
      example           : ./import_hiseq_reads_tags_cv.sh -r 220407_A01439_0064_BHY3WWDRXY\n
"

DRY_RUN=no
RUN_NAME=""
BUILD_ROOT=/dataset/2024_illumina_sequencing_e/scratch/postprocessing/gbs

while getopts "hr:d:" opt; do
  case $opt in
    r)
      RUN_NAME=$OPTARG
      ;;
    d)
      BUILD_ROOT=$OPTARG
      ;;
    h)
      echo -e $help_text
      exit 0
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

RUN_PATH=$BUILD_ROOT/${RUN_NAME}

}

function check_opts() {
if [ -z "$GBS_PRISM_BIN" ]; then
   echo "GBS_PRISM_BIN not set - quitting"
   exit 1
fi

if [ -z "$RUN_NAME" ]; then
   echo -e $help_text
   exit 1
fi

if [ ! -d $RUN_PATH ]; then
   echo $RUN_PATH not found
   exit 1
fi

}

function echo_opts() {
    echo "importing $RUN_NAME from $RUN_PATH"
}

get_opts $@

check_opts

echo_opts

## from here , process the import


function collate_data() {
rm -f $RUN_PATH/html/gbs_yield_import_temp.dat
files=`ls $RUN_PATH/SQ*/TagCount.csv.blinded | egrep -v "\/OLD|_OLD"`
for file in $files; do
   # files contain 
   #sample,flowcell,lane,sq,tags,reads
   #total,C6JPMANXX,7,88,,211124459
   #good,C6JPMANXX,7,88,,202570647
   #998599,C6JPMANXX,7,88,231088,776567
   #998605,C6JPMANXX,7,88,419450,2148562

   cohort=`dirname $file`
   cohort=`basename $cohort`
   run=$RUN_NAME

   $GBS_PRISM_BIN/collate_tags_reads.py --run $run --cohort $cohort --machine novaseq $file >> $RUN_PATH/html/gbs_yield_import_temp.dat 

   #cat $file | awk -F, '{printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",run,cohort,$1,$2,$3,$4,$5,$6);}' run=$run cohort=$cohort - >> $RUN_PATH/html/gbs_yield_import_temp.dat
   # e.g.
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    sample  flowcell        lane    sq      tags    reads
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    total   CCVK0ANXX       1       SQ0788          298918641
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    good    CCVK0ANXX       1       SQ0788          268924508
   
done
}

function import_data() {
   cd $RUN_PATH/html
   gupdate --explain -t lab_report -p "name=import_gbs_read_tag_counts;file=gbs_yield_import_temp.dat" $RUN_NAME
}

set -x
collate_data
import_data
set +x
