#!/bin/sh

function get_opts() {

help_text="\n
      usage : import_kgd_stats.sh -r run_name\n
      example (dry run) : ./import_kgd_stats.sh -n -r 170224_D00390_0285_ACA62JANXX\n
      example           : ./import_kgd_stats.sh -r 170224_D00390_0285_ACA62JANXX\n
"

DRY_RUN=no
RUN_NAME=""
BUILD_ROOT=/dataset/gseq_processing/scratch/gbs 

while getopts ":nhr:d:" opt; do
  case $opt in
    n)
      DRY_RUN=yes
      ;;
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
    echo "DRY_RUN=$DRY_RUN"
}

get_opts $@

check_opts

echo_opts

## from here , process the import



function collate_data() {
rm -f $RUN_PATH/html/kgd_import_temp.dat
files=`ls $RUN_PATH/*/KGD/SampleStats.csv.blinded | egrep -v "\/OLD|_OLD"`
for file in $files; do
   # e.g. 
   #"seqID","callrate","sampdepth"
   #"C26128-01_C9B0MANXX_7_2562_X4",0.6222982902613,6.32146313487939
   #"C26128-02_C9B0MANXX_7_2562_X4",0.603175741065988,7.21642352772501
   #"C26128-03_C9B0MANXX_7_2562_X4",0.601939137603498,9.28047600272411
   #"C26128-22_C9B0MANXX_7_2562_X4",0.630183877558335,7.77328936521022
   # ...
   #"C26128-23_C9B0MANXX_7_2562_X4",0.596347539338328,7.91736262948493
   # ( cf the tag count file : 
   #sample,flowcell,lane,sq,tags,reads
   # total,C9B0MANXX,7,SQ2562,,236560795
   # good,C9B0MANXX,7,SQ2562,,227493728
   # C26128-23,C9B0MANXX,7,2562,321892,2866438
   # C26128-94,C9B0MANXX,7,2562,323125,2770861
   # C26128-07,C9B0MANXX,7,2562,307216,2209878
   # C26128-84,C9B0MANXX,7,2562,295120,2300256
   # C26128-17,C9B0MANXX,7,2562,297249,2072236
   # C26128-33,C9B0MANXX,7,2562,299478,2660275
   cohort=`dirname $file`
   cohort=`dirname $cohort`
   cohort=`basename $cohort`
   run=$RUN_NAME
   cat $file | sed 's/"//g' - | awk -F, '{printf("%s\t%s\t%s\t%s\t%s\n",run,cohort,$1,$2,$3);}' run=$run cohort=$cohort - >> $RUN_PATH/html/kgd_import_temp.dat
# e.g.
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    seqID   callrate        sampdepth
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    qc302484-1_CCVK0ANXX_1_788_X4   0.856633390168031       3.53962593224089
#180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    qc302485-1_CCVK0ANXX_1_788_X4   0.814684176959821       2.70259400502401


done
}

function import_data() {
   cd $RUN_PATH/html
   if [ $DRY_RUN == "yes" ]; then
      echo " dry run 
      psql -U agrbrdf -d agrbrdf -h postgres  -f $GBS_PRISM_BIN/import_kgd_stats.psql"
   else 
      psql -U agrbrdf -d agrbrdf -h postgres  -f $GBS_PRISM_BIN/import_kgd_stats.psql
   fi
}

function update_data() {
   if [ $DRY_RUN == "yes" ]; then
      echo " dry run
      psql -U agrbrdf -d agrbrdf -h postgres  -v run_name=\'${RUN_NAME}\' -f $GBS_PRISM_BIN/update_kgd_stats.psql"
   else
      psql -U agrbrdf -d agrbrdf -h postgres  -v run_name=\'${RUN_NAME}\' -f $GBS_PRISM_BIN/update_kgd_stats.psql
   fi
}

collate_data
import_data
update_data
