#!/bin/sh
#
# this does a GBS Q/C run on the (GBS related) hiseq output.
# it is run after process_hiseq.sh 
# 

function read_answer_with_default() {
   read answer
   if [ -z "$answer" ]; then
      answer=$@
   fi
}


function get_opts() {

help_text="
 examples : \n
 ./database_prism.sh -i -t import_new_run -r 180921_D00390_0400_BCCVDJANXX  -s SQ0788\n
 ./database_prism.sh -i -t import_results -r 180921_D00390_0400_BCCVDJANXX  -s SQ0799\n
 ./database_prism.sh -i -t reimport_library -r 180921_D00390_0400_BCCVDJANXX  -s SQ0799\n
"

DRY_RUN=no
INTERACTIVE=no
TASK=import_new_run
RUN=all
MACHINE=hiseq
SAMPLE=""
REUSE_TARGETS="no"
RUN_BASE_PATH=/dataset/gseq_processing/scratch/gbs

while getopts ":nikht:r:m:s:e:d:" opt; do
  case $opt in
    n)
      DRY_RUN=yes
      ;;
    k)
      REUSE_TARGETS=yes
      ;;
    i)
      INTERACTIVE=yes
      ;;
    t)
      TASK=$OPTARG
      ;;
    m)
      MACHINE=$OPTARG
      ;;
    r)
      RUN=$OPTARG
      ;;
    d)
      RUN_BASE_PATH=$OPTARG
      ;;
    s)
      SAMPLE=$OPTARG
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

}


function check_opts() {
if [ -z "$GBS_PRISM_BIN" ]; then
   echo "GBS_PRISM_BIN not set - quitting"
   exit 1
fi

# check args
if [[ ( $TASK != "import_new_run" ) && ( $TASK != "import_results" ) && ( $TASK != "reimport_library" ) ]]; then
    echo "Invalid task name - must be import_new_run, import_results, reimport_library" 
    exit 1
fi

# machine must be miseq or hiseq 
if [[ ( $MACHINE != "hiseq" ) && ( $MACHINE != "miseq" ) ]]; then
    echo "machine must be miseq or hiseq"
    exit 1
fi

# check RUN_BASE_PATH
if [ ! -d $RUN_BASE_PATH ]; then
   echo "$RUN_BASE_PATH not found"
   exit 1
fi

}


function echo_opts() {
    echo "run to process : $RUN"
    echo "task requested : $TASK"
    echo "dry run : $DRY_RUN"
    echo "interactive : $INTERACTIVE"
    echo "machine : $MACHINE"
}

function get_samples() {
   set -x
   if [ -z $SAMPLE ]; then
      sample_monikers=`psql -U agrbrdf -d agrbrdf -h postgres -v run=\'$RUN\' -f $GBS_PRISM_BIN/get_run_samples.psql -q`
   else
      sample_monikers=$SAMPLE
   fi
   set +x
}

function import_new_run() {
   add_run
   get_samples 
   import_keyfiles
   update_fastq_locations
   update_bwa_blast_refs
}

function reimport_library() {
   psql -U agrbrdf -d agrbrdf -h postgres -f $GBS_PRISM_BIN/dump_gbs_tables.psql
   flowcell=`$GBS_PRISM_BIN/get_flowcellid_from_database.sh $RUN  $SAMPLE`
   sample_monikers=$SAMPLE
   delete_keyfiles
   import_keyfiles
   update_all_fastq_locations     
   update_bwa_blast_refs
}


function add_run() {
   # add the run 
   echo "** adding Run **"
   set -x
   if [ $DRY_RUN == "no" ]; then
      $GBS_PRISM_BIN/addRun.sh -d $RUN_BASE_PATH -r $RUN -m $MACHINE
   else
      $GBS_PRISM_BIN/addRun.sh -d $RUN_BASE_PATH -n -r $RUN -m $MACHINE
   fi
}

function import_keyfiles() {
   # import the keyfiles
   echo "** importing keyfiles **"
   set -x
   for sample_moniker in $sample_monikers; do
      if [ $DRY_RUN == "no" ]; then
         $GBS_PRISM_BIN/importOrUpdateKeyfile.sh -k $sample_moniker -s $sample_moniker -D /dataset/${MACHINE}/active/key-files
      else
         $GBS_PRISM_BIN/importOrUpdateKeyfile.sh -n -k $sample_moniker -s $sample_moniker -D /dataset/${MACHINE}/active/key-files
      fi
      if [ $? != "0" ]; then
          echo "warning  - importOrUpdateKeyfile.sh  exited with $? for $sample_moniker - do you want to continue ? (y/n default y)"
          read_answer_with_default y
          if [ $answer != "y" ]; then
             exit 1
          fi
      fi
   done
}

function delete_keyfiles() {
   echo "** deleting keyfiles **"
   set -x
   for sample_moniker in $sample_monikers; do
      if [ $DRY_RUN == "no" ]; then
         $GBS_PRISM_BIN/deleteKeyfile.sh -k $sample_moniker -s $sample_moniker -f $flowcell
      else
         $GBS_PRISM_BIN/deleteKeyfile.sh -n -k $sample_moniker -s $sample_moniker -f $flowcell
      fi
      if [ $? != "0" ]; then
          echo "deleteKeyfile.sh  exited with $? - quitting"
          exit 1
      fi
   done
}


function update_fastq_locations() {
   # update the fastq locations 
   echo "** updating fastq locations **"
   set -x
   for sample_moniker in $sample_monikers; do
      # to do : add a check that there is only one fcid - process not tested for 
      # a sample spread over different flowcells
      flowcell_moniker=`$GBS_PRISM_BIN/get_flowcellid_from_database.sh $RUN $sample_moniker`
      flowcell_lanes=`$GBS_PRISM_BIN/get_lane_from_database.sh $RUN $sample_moniker`
      for flowcell_lane in $flowcell_lanes; do
         echo "processing lane '${flowcell_lane}'"
         if [ $DRY_RUN == "no" ]; then
            $GBS_PRISM_BIN/updateFastqLocations.sh -s $sample_moniker -k $sample_moniker -r $RUN -f $flowcell_moniker -l $flowcell_lane 
         else
            $GBS_PRISM_BIN/updateFastqLocations.sh -n -s $sample_moniker -k $sample_moniker -r $RUN -f $flowcell_moniker -l $flowcell_lane 
         fi
         if [ $? != "0" ]; then
            echo "error !! updateFastqLocations.sh  exited with $? for $sample_moniker - do you want to continue ? (y/n default y)"
            read_answer_with_default y
            if [ $answer != "y" ]; then
               exit 1
            fi
         fi
      done
   done
}


function update_all_fastq_locations() {
   # update the fastq locations
   code_to_return=0
   echo "** updating all fastq locations **"
   set -x
   for sample_moniker in $sample_monikers; do
      # generate code to update fastq locations for all flowcells the sample was on - i.e. generate
      #$GBS_PRISM_BIN/updateFastqLocations.sh -s $sample_moniker -k $sample_moniker -r $RUN -f $flowcell_moniker -l $flowcell_lane
      generator_script=`mktemp --tmpdir tmp.data_prismXXXXX`
      update_script=`mktemp --tmpdir tmp.data_prismXXXXX`
      echo "\a
\f '\t'
\t
\pset footer off 
\o $update_script
select distinct
   '$GBS_PRISM_BIN/updateFastqLocations.sh -s $sample_moniker -k $sample_moniker -r ' || b.listname || ' -f ' || g.flowcell || ' -l ' ||g.lane 
from 
   hiseqsamplesheetfact h join biosamplelist b on h.biosamplelist = b.obid  join
   biosamplelistmembershiplink as l on l.biosamplelist = b.obid join
   gbskeyfilefact as g on g.biosampleob = l.biosampleob
where 
   h.sampleid = :sample_name and
   h.lane = g.lane and 
   to_number(replace(:sample_name, 'SQ',''),'99999') =  g.libraryprepid ;
" >> $generator_script 
      psql -U agrbrdf -d agrbrdf -h postgres -v sample_name="'${sample_moniker}'" -f $generator_script  
      if [ $DRY_RUN == "no" ]; then
         source $update_script
      else
         echo "would run $update_script"
      fi
   done
}

function update_bwa_blast_refs() {
   # this fills in blast and bwa refs for newly imported records based on previous 
   # records with matching species. Where new record is a nre species , a seperate update is needed 
   psql -U agrbrdf -d agrbrdf -h postgres  -f $GBS_PRISM_BIN/fill_in_ref_indexes.psql
}



function import_results() {
   set -x
   # clear existing yields for this run 
   psql -U agrbrdf -d agrbrdf -h postgres -v run_name=\'${RUN}\' -f $GBS_PRISM_BIN/delete_run_yields.psql 
   set +x

   # import yield stats
   $GBS_PRISM_BIN/import_hiseq_reads_tags_cv.sh -r $RUN

   $GBS_PRISM_BIN/import_kgd_stats.sh -r $RUN
}


get_opts $@

check_opts

echo_opts

if [ $TASK == "import_new_run" ]; then
   import_new_run  
   if [ $? == 0 ]; then 
      echo "

*** import looks OK :-) *** 

You can browse the run at http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=${RUN}&context=default 

      "
   else
      echo "

*** looks like the import had a problem :-( ***  

You may be able to browse the run at http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=${RUN}&context=default

common problems:

* missing keyfile 
* typo in keyfile  - e.g. wrong flowcell or library number - this means the import can't set up the correct fastq links
* wrong species for GBS negatives, can lead to a spurious negatives-only cohort being set up 

You can manually complete the import using $GBS_PRISM/database_prism.sh (-h for help)
      "
      exit 1
   fi
elif [ $TASK == "import_results" ]; then
   import_results
elif [ $TASK == "reimport_library" ]; then
   reimport_library
else
   echo "unknown task $TASK"
   exit 1
fi
