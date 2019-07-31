#!/bin/sh
#
# this scripts sets up a run in the database   
# to use it - e.g.
# deleteRun.sh 150630_D00390_0232_AC6K0WANXX 
# jumps through various hoops due to idiosyncracies of 
# \copy and copy
# only intended for importing GBS runs at this stage
#
function get_opts() {

help_text="\n
      usage : deleteRun.sh -r run_name\n
      example (dry run) : ./deleteRun.sh -n -r 190506_D00390_0455_ACDNN7ANXX -F CDNN7ANXX\n
      example           : ./deleteRun.sh -r 190506_D00390_0455_ACDNN7ANXX -F CDNN7ANXX\n
"

DRY_RUN=no
RUN_NAME=""
FLOWCELL="?"
MACHINE=hiseq
RUN_BASE_PATH=/dataset/gseq_processing/scratch/gbs

while getopts ":nhr:m:d:F:" opt; do
  case $opt in
    n)
      DRY_RUN=yes
      ;;
    i)
      INTERACTIVE=yes
      ;;
    r)
      RUN_NAME=$OPTARG
      ;;
    F)
      FLOWCELL=$OPTARG
      ;;
    m)
      MACHINE=$OPTARG
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

function read_answer_with_default() {
   read answer
   if [ -z "$answer" ]; then
      answer=$@
   fi
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

echo $RUN_NAME | grep -q $FLOWCELL  > /dev/null 2>&1
if [ $? != 0 ]; then
   echo "mismatch between flowcell ( $FLOWCELL ) and run ( $RUN_NAME )"
   exit 1
fi

if [ $MACHINE == "miseq" ]; then
   echo "error , database import of miseq runs not currently supported"
   exit 1
fi

in_db=`$GBS_PRISM_BIN/is_run_in_database.sh $RUN_NAME`
if [ $in_db != "1" ]; then
   echo "$RUN_NAME is not in database - quitting"
   exit 1 
fi

# machine must be miseq or hiseq
if [[ ( $MACHINE != "hiseq" ) && ( $MACHINE != "miseq" ) ]]; then
    echo "machine must be miseq or hiseq"
    exit 1
fi

}

function echo_opts() {
    echo "deleteing $RUN_NAME"
    echo "DRY_RUN=$DRY_RUN"
}

get_opts $@

check_opts

echo_opts

## from here , process the import

rm -f /tmp/${RUN_NAME}.txt
if [ -f /tmp/${RUN_NAME}.txt ]; then
   echo "rm -f /tmp/${RUN_NAME}.txt failed - quitting"
   exit 1
fi
rm -f /tmp/${RUN_NAME}.psql
if [ -f /tmp/${RUN_NAME}.psql ]; then
   echo "rm -f /tmp/${RUN_NAME}.psql failed - quitting"
   exit 1
fi


echo "

--we need to delete biosampleob records, where the biosampleob is linked to this run, and is not linked to any others
--save these as need to delete links first ! 

create table delete_run_tmp as (
select obid from biosampleob where obid in (
select distinct biosampleob from biosamplelistmembershiplink
where biosamplelist = ( select
obid from biosamplelist where listname = :run_name)
except
select distinct biosampleob from biosamplelistmembershiplink
where biosamplelist != ( select
obid from biosamplelist where listname = :run_name)
));

-- delete from gbs yield table
delete from gbsyieldfact where  biosamplelist = (select
obid from biosamplelist where listname = :run_name ) and 
flowcell = :flowcell;

-- delete from keyfiletable 
delete from gbskeyfilefact where flowcell = :flowcell; 

-- delete the links
delete from biosamplelistmembershiplink 
where biosamplelist = (select
obid from biosamplelist where listname = :run_name );

-- delete the sampleobs
delete from biosampleob where obid in (select obid from delete_run_tmp);

-- clean and drop that tmp table
delete from delete_run_tmp;
drop table delete_run_tmp;

-- delete from hiseqsamplesheetfact
delete from hiseqsamplesheetfact where biosamplelist = (select
obid from biosamplelist where listname = :run_name );

--delete from biosamplelist
delete from biosamplelist where listname = :run_name;
" > /tmp/delete_${RUN_NAME}.psql

if [ $DRY_RUN == "no" ]; then
   echo "are you sure you want to completely delete ${RUN_NAME} from the database, using the SQL code 
in /tmp/delete_${RUN_NAME}.psql (y/n) ?"

   read_answer_with_default n

   if [ "$answer" != "y" ]; then
      echo "ok quitting"
   else
      psql -U agrbrdf -d agrbrdf -h invincible -v run_name=\'${RUN_NAME}\' -v flowcell=\'${FLOWCELL}\' -f /tmp/delete_${RUN_NAME}.psql
      echo "
finished deleting ${RUN_NAME}. ( Note that the processing folder itself has not been deleted).
      "
   fi
else
   echo " will run 
   psql -U agrbrdf -d agrbrdf -h invincible -v run_name=\'${RUN_NAME}\' -v flowcell=\'${FLOWCELL}\' -f /tmp/delete_${RUN_NAME}.psql"
fi
