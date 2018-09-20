#!/bin/sh

if [ -z "$GBS_PRISM_BIN" ]; then
   echo "GBS_PRISM_BIN not set - quitting"
   exit 1
fi

#!/bin/sh

function get_opts() {

help_text="\n
      usage : import_hiseq_reads_tags_cv.sh -r run_name\n
      example (dry run) : ./import_hiseq_reads_tags_cv.sh -n -r 170224_D00390_0285_ACA62JANXX\n
      example           : ./import_hiseq_reads_tags_cv.sh -r 170224_D00390_0285_ACA62JANXX\n
"

DRY_RUN=no
RUN_NAME=""

while getopts ":nhr:" opt; do
  case $opt in
    n)
      DRY_RUN=yes
      ;;
    r)
      RUN_NAME=$OPTARG
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

BUILD_ROOT=/dataset/gseq_processing/scratch/gbs
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
    echo "DRY_RUN=$DRY_RUN"
}

get_opts $@

check_opts

echo_opts

## from here , process the import


function collate_data() {
rm -f $RUN_PATH/html/gbs_yield_import_temp.dat
for file in $RUN_PATH/*/TagCount.csv.blinded; do
   # files contain 
   #sample,flowcell,lane,sq,tags,reads
   #total,C6JPMANXX,7,88,,211124459
   #good,C6JPMANXX,7,88,,202570647
   #998599,C6JPMANXX,7,88,231088,776567
   #998605,C6JPMANXX,7,88,419450,2148562

   cohort=`dirname $file`
   cohort=`basename $cohort`
   run=$RUN_NAME
   cat $file | awk -F, '{printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",run,cohort,$1,$2,$3,$4,$5,$6);}' run=$run cohort=$cohort - >> $RUN_PATH/html/gbs_yield_import_temp.dat
   # e.g.
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    sample  flowcell        lane    sq      tags    reads
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    total   CCVK0ANXX       1       SQ0788          298918641
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    good    CCVK0ANXX       1       SQ0788          268924508
done
}

function import_data() {
   cd $RUN_PATH/html
   psql -U agrbrdf -d agrbrdf -h invincible -f $GBS_PRISM_BIN/import_hiseq_reads_tags_cv.psql
}

function update_data() {
   psql -U agrbrdf -d agrbrdf -h invincible -v run_name=\'${RUN_NAME}\' -f $GBS_PRISM_BIN/update_hiseq_reads_tags_cv.psql 
}

set -x
collate_data
import_data
update_data
set +x
