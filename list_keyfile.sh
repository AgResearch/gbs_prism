#!/bin/sh
#
# this script lists a keyfile from the database   
function get_opts() {

help_text="\n
 this script extracts a (custom) keyfile from the database \n

 Usage: \n

 list_keyfile.sh [-s sample_name]  [-v client version (e.g. 5 for tassel 5 etc)] [-g gbs_cohort ] [-e enzyme [-t default|all|gbsx|qc|gbsx_qc|files|unblind|unblind_script|bwa_index_paths|blast_index_paths] [ -f flowcell ]\n
\n
e.g.\n
list_keyfile.sh  -s SQ0566                  # extract everything for SQ0566, default tassel 3 format\n
list_keyfile.sh  -s SQ0566 -v 5             # extract everything for SQ0566, default tassel 5 format\n
list_keyfile.sh  -s SQ0566 -v 5 -t all      # extract everything for SQ0566, extended tassel 5 format (also include subject name)\n
list_keyfile.sh  -s SQ0566 -t gbsx          # extract everything for SQ0566, GBSX format (only include sample, barcode, enzyme)\n
list_keyfile.sh  -s SQ0566 -t qc            # internal primary key used instead of sampleid\n
list_keyfile.sh  -s SQ0566 -t unblind       # dump a mapping between qc_sampleid and lab sampleid \n
list_keyfile.sh  -s SQ0566 -t unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid. Save output to a file and then run as sed -f script_file raw_file > patched_file \n
list_keyfile.sh  -s SQ0566 -t files         # extract distinct lane + fastq file name for SQ0566 (e.g. to help build GBSX command)\n
list_keyfile.sh  -s SQ0566 -t bwa_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566\n
list_keyfile.sh  -s SQ0566 -t blast_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566\n
list_keyfile.sh  -g deer                    # extract everything that has gbs_cohort = deer (across all runs)\n
list_keyfile.sh  -g deer -e PstI            # extract everything that has gbs_cohort = deer , and enzyme = PstI (across all runs)\n
list_keyfile.sh  -t gbsx -g deer -e PstI    # as above, GBSX format \n
list_keyfile.sh  -t files -g deer -e PstI   # as above, report lane + file\n
list_keyfile.sh  -g deer  -f CA95UANXX      # all deer , but only in flowcell CA95UANXX\n
list_keyfile.sh  -f CA95UANXX               # extract everything on flowcell CA95UANXX\n
list_keyfile.sh  -s SQ2701 -q uncontaminated      # all the samples flagged as uncontaminated in SQ2701 \n
list_keyfile.sh -s SQ2701 -f CC5V9ANXX -e ApeKI -g Ryegrass -q contaminated_xanthomonas_translucens \n
list_keyfile.sh                             # don't be greedy ! (extract entire keyfile database, ~ 200,000 records)\n
"

CLIENT_VERSION=3
FLOWCELL=""
TEMPLATE="default"  # tassel
ENZYME=""
GBS_COHORT=""
SAMPLE=""
QC_COHORT="all"

while getopts ":nhv:s:k:c:f:t:e:g:q:" opt; do
  case $opt in
    s)
      SAMPLE=$OPTARG
      ;;
    v)
      CLIENT_VERSION=$OPTARG
      ;;
    f)
      FLOWCELL=$OPTARG
      ;;
    e)
      ENZYME=$OPTARG
      ;;
    g)
      GBS_COHORT=$OPTARG
      ;;
    q)
      QC_COHORT=$OPTARG
      ;;
    t)
      TEMPLATE=$OPTARG
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


   if [[ $CLIENT_VERSION != 3 && $CLIENT_VERSION != 5 ]]; then
      echo "Tassel version should be 3 or 5"
      exit 1
   fi
   if [[ $TEMPLATE != "default" && $TEMPLATE != "all" && $TEMPLATE != "gbsx" && $TEMPLATE != "files" && $TEMPLATE != "qc" && $TEMPLATE != "gbsx_qc" && $TEMPLATE != "unblind"  && $TEMPLATE != "unblind_script" && $TEMPLATE != "bwa_index_paths" && $TEMPLATE != "blast_index_paths" ]]; then
      echo "template should be one of default, all, gbsx, gbsx_qc, unblind, unblind_script, files, bwa_index_paths, blast_index_paths  (default and all are both tassel templates)"
      exit 1
   fi

   if [[ ( -z $SAMPLE ) && ( -z "$GBS_COHORT" ) && ( -z "$ENZYME" ) && ( -z "$FLOWCELL" ) ]]; then
      answer="n"
      echo "this will extract the whole keyfile database - are you sure ( list_keyfile.sh  -h to see options and examples ) ? (y/n)"
      read answer
      if [ "$answer" != "y" ]; then
         exit 1
      fi
   fi

}

function build_extract_script() {
   sample_phrase1=" 1 = 1 "
   sample_phrase2=" sample "
   gbs_cohort_phrase=""
   qc_cohort_phrase=""
   enzyme_phrase=""
   extra_fields_phrase=""


   script_name=`mktemp --tmpdir listDBKeyfileXXXXX.psql`

   if [ ! -z "$SAMPLE" ]; then
      sample_phrase1=" s.samplename = :keyfilename "
   fi

   if [ ! -z "$GBS_COHORT" ]; then
      gbs_cohort_phrase=" and lower(g.gbs_cohort) = lower(:gbs_cohort) "
   fi

   if [ "$QC_COHORT" != "all" ]; then
      qc_cohort_phrase=" and lower(g.qc_cohort) = lower(:qc_cohort) "
   fi

   if [ ! -z "$ENZYME" ]; then
      enzyme_phrase=" and lower(g.enzyme) = lower(:enzyme) "
   fi
  
   if [ $TEMPLATE == "all" ] ; then
      extra_fields_phrase=", subjectname"
   fi    

   if [[ ( $TEMPLATE == "qc" ) || ( $TEMPLATE == "gbsx_qc" ) ]] ; then
      sample_phrase2=" qc_sampleid "
   fi    
   
   if [[ ( $TEMPLATE == "all" ) || ( $TEMPLATE == "default" ) || ( $TEMPLATE == "qc" ) ]]; then
      if [ $CLIENT_VERSION == "5" ]; then 
code="
select 
   Flowcell,
   Lane,
   Barcode,
   $sample_phrase2 as sample,
   PlateName,
   PlateRow as Row,
   PlateColumn as Column,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   Control,
   Fastq_link,
   Sample||':'||LibraryPrepID as FullSampleName $extra_fields_phrase
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by 
   factid;
"
      elif [ $CLIENT_VERSION == "3" ]; then 
code="
select 
   Flowcell,
   Lane,
   Barcode,
   $sample_phrase2 as sample,
   PlateName,
   PlateRow as Row,
   PlateColumn as Column,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   Control,
   Fastq_link $extra_fields_phrase
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by 
   factid;
"
      fi 
   elif [[ ( $TEMPLATE == "gbsx" ) || ( $TEMPLATE == "gbsx_qc" ) ]]; then
code="
select distinct 
   $sample_phrase2 as sample,
   Barcode,
   Enzyme
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by 
   1,2,3;
"
   elif [[ ( $TEMPLATE == "files" ) ]]; then
code="
select distinct 
   lane,
   fastq_link
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by 
   1;
"
   elif [[ ( $TEMPLATE == "bwa_index_paths" ) ]]; then
code="
select distinct
   gbs_cohort,
   refgenome_bwa_indexes
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by
   1;
"
   elif [[ ( $TEMPLATE == "blast_index_paths" ) ]]; then
code="
select distinct
   gbs_cohort,
   refgenome_blast_indexes
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by
   1;
"
   elif [[ ( $TEMPLATE == "unblind" ) ]]; then
code="
select 
   qc_sampleid,
   sample
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by 
   1;
"
   elif [[ ( $TEMPLATE == "unblind_script" ) ]]; then
code="
select
   's/' || replace(qc_sampleid,'-','.') || '/' || sample || '/g'
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $qc_cohort_phrase
order by
   1;
"
   fi 

   echo "\a" > $script_name
   echo "\f '\t'" >> $script_name
   echo "\pset footer off " >> $script_name
   if [  $TEMPLATE == "unblind_script"  ]; then
      echo "\t" >> $script_name
   fi
   echo $code >> $script_name
}

function run_extract() {
   if [[ ( -z $FLOWCELL ) || ( $TEMPLATE == "unblind" ) || ( $TEMPLATE == "unblind_script" ) || ( $TEMPLATE == "gbsx" ) || ( $TEMPLATE == "gbsx_qc" ) ]]; then
      psql -q -U gbs -d agrbrdf -h invincible -v keyfilename=\'$SAMPLE\' -v enzyme=\'$ENZYME\' -v gbs_cohort=\'$GBS_COHORT\' -v qc_cohort=\'$QC_COHORT\' -f $script_name
   else
      psql -q -U gbs -d agrbrdf -h invincible -v keyfilename=\'$SAMPLE\' -v enzyme=\'$ENZYME\' -v gbs_cohort=\'$GBS_COHORT\' -v qc_cohort=\'$QC_COHORT\' -f $script_name | egrep -i \($FLOWCELL\|flowcell\)  
   fi

   if [ $? != 0 ]; then
      echo " looks like extract failed - you might need to set up a .pgpass file in your home folder "
      exit 1
   fi 
}


get_opts $@

check_opts

build_extract_script 

run_extract 





