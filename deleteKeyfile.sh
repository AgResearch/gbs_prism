#!/bin/sh
#
# this scripts deletes a keyfile from the database
#
function get_opts() {

help_text="\n
 this scripts deletes a keyfile \n

 deleteKeyfile.sh -s sample_name -k keyfile_base -f flowcell\n
\n
 e.g.\n
 deleteKeyfile.sh -n  -s SQ0143 -k SQ0143 -f flowcell\n
"

DRY_RUN=no
FLOWCELL=""
while getopts ":nhs:k:f:" opt; do
  case $opt in
    n)
      DRY_RUN=yes
      ;;
    s)
      SAMPLE=$OPTARG
      ;;
    k)
      KEYFILE_BASE=$OPTARG
      ;;
    f)
      FLOWCELL=$OPTARG
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

KEY_DIR=/dataset/hiseq/active/key-files
}

function check_opts() {
   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "GBS_PRISM_BIN not set - quitting"
      exit 1
   fi

   if [ ! -f $KEY_DIR/$KEYFILE_BASE.txt ]; then
      echo $KEY_DIR/$KEYFILE_BASE.txt not found
      exit 1
   fi

   if [ -z $SAMPLE ]; then
      echo "must specify a sample name"
      exit 1
   fi

   if [ -z $FLOWCELL ]; then
      echo "must specify a flowcell name"
      exit 1
   fi

   # check if the keyfile is already in the database
   in_db=`$GBS_PRISM_BIN/is_keyfile_in_database.sh $KEYFILE_BASE`
   if [ $in_db == "0" ]; then
      echo "$KEYFILE_BASE not in database"
      exit 1
   fi
}

function echo_opts() {
    echo "deleting $KEY_DIR/$KEYFILE_BASE.txt for sample $SAMPLE"
    echo "DRY_RUN=$DRY_RUN"
}

get_opts $@

check_opts

echo_opts

########################### from here do delete #######################

set -x
echo "deleting the following data"

$GBS_PRISM_BIN/listDBKeyfile.sh -s $KEYFILE_BASE  

echo "deleting keyfile..."

if [ $DRY_RUN == "no" ]; then
   psql -q -U agrbrdf -d agrbrdf -h invincible -v keyfilename=\'$KEYFILE_BASE\' -v flowcell=\'$FLOWCELL\' -f $GBS_PRISM_BIN/deleteKeyfile.psql
else
   echo "*** dry run only *** will execute 
   psql -q -U agrbrdf -d agrbrdf -h invincible -v keyfilename=\'$KEYFILE_BASE\' -v flowcell=\'$FLOWCELL\' -f $GBS_PRISM_BIN/deleteKeyfile.psql
   "
fi
set +x
