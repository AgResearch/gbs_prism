#!/bin/sh
#
# this script lists a keyfile from the database   
DEBUG=0
function get_opts() {

help_text="\n
 this script extracts a (custom) keyfile from the database \n

 Usage: \n

 list_keyfile.sh [-s sample_name]  [-v client version (e.g. 5 for tassel 5 etc)] [-g gbs_cohort ] [-e enzyme] [-m species_moniker] [-t default|all|gbsx|qc|gbsx_qc|files|method|missing_files|unblind|unblind_script|historical_unblind_script|bwa_index_paths|blast_index_paths|list_species] [ -f flowcell ]\n
\n
e.g.\n
list_keyfile.sh  -s SQ0566                  # extract everything for SQ0566, default tassel 3 format\n
list_keyfile.sh  -s SQ0566 -v 5             # extract everything for SQ0566, default tassel 5 format\n
list_keyfile.sh  -s SQ0566 -v 5 -t all      # extract everything for SQ0566, extended tassel 5 format (also include subject name)\n
list_keyfile.sh  -s SQ0566 -t gbsx          # extract everything for SQ0566, GBSX format (only include sample, barcode, enzyme)\n
list_keyfile.sh  -s SQ0566 -t qc            # internal primary key used instead of sampleid\n
list_keyfile.sh  -s SQ0566 -t unblind       # dump a mapping between qc_sampleid and lab sampleid \n
list_keyfile.sh  -s SQ0566 -t unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid. Save output to a file and then run as sed -f script_file raw_file > patched_file \n
list_keyfile.sh  -s SQ1131 -t historical_unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid - including historical qc_sampleids (e.g. if keyfile was reloaded) . Save output to a file and then run as sed -f script_file raw_file > patched_file \n
list_keyfile.sh  -s SQ0566 -t files         # extract distinct lane + fastq file name for SQ0566 (e.g. to help build GBSX command)\n
list_keyfile.sh  -s SQ1014 -t method         # extract distinct geno_method for SQ1014\n
list_keyfile.sh  -s SQ0566 -t bwa_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566\n
list_keyfile.sh  -s SQ0566 -t blast_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566\n
list_keyfile.sh  -s SQ0566 -t list_species  # extract distinct cohort + path to bwa index for cohort species for SQ0566\n
list_keyfile.sh  -g deer                    # extract everything that has gbs_cohort = deer (across all runs, not case sensitive e.g. will include DEER)\n
list_keyfile.sh  -m bee                     # extract everything that has species field deer (across all runs , not case sensitive e.g. will include BEE)\n
list_keyfile.sh  -m goat -x                     # extract everything that has species field goat , that has been excluded \n
list_keyfile.sh  -m bee -t gbsx             # as above, GBSX format \n
list_keyfile.sh  -g deer -e PstI            # extract everything that has gbs_cohort = deer , and enzyme = PstI (across all runs)\n
list_keyfile.sh  -t gbsx -g deer -e PstI    # as above, GBSX format \n
list_keyfile.sh  -t files -g deer -e PstI   # as above, report lane + file\n
list_keyfile.sh  -t missing_files -g deer -e PstI   # as above, but report lane and any samples where the fastq file is missing\n
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
SPECIES_MONIKER=""
TAXID=""
SAMPLE=""
QC_COHORT="all"
exclusions_phrase=" and coalesce(qc_cohort,'included') != 'excluded'  "

while getopts ":ndhv:s:k:c:f:t:e:g:q:m:xT:" opt; do
  case $opt in
    d)
      DEBUG=1
      ;;
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
    x)
      exclusions_phrase=" and qc_cohort = 'excluded' "
      ;;
    g)
      GBS_COHORT=$OPTARG
      ;;
    m)
      SPECIES_MONIKER=$OPTARG
      ;;
    T)
      TAXID=$OPTARG
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
   if [ $DEBUG == 1 ]; then
      echo "debug : species_moniker=$SPECIES_MONIKER"
   fi 
   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "GBS_PRISM_BIN not set - quitting"
      exit 1
   fi


   if [[ $CLIENT_VERSION != 3 && $CLIENT_VERSION != 5 ]]; then
      echo "Tassel version should be 3 or 5"
      exit 1
   fi
   if [[ $TEMPLATE != "default" && $TEMPLATE != "all" && $TEMPLATE != "gbsx" && $TEMPLATE != "files" && $TEMPLATE != "method" && $TEMPLATE != "missing_files" && $TEMPLATE != "qc" && $TEMPLATE != "qc1" && $TEMPLATE != "gbsx_qc" && $TEMPLATE != "unblind"  && $TEMPLATE != "unblind_script" && $TEMPLATE != "historical_unblind_script" && $TEMPLATE != "bwa_index_paths" && $TEMPLATE != "blast_index_paths" && $TEMPLATE != "list_species" ]]; then
      echo "template should be one of default, all, gbsx, qc, gbsx_qc, unblind, unblind_script, historical_unblind_script, files, method, missing_files, bwa_index_paths, blast_index_paths list_species (default and all are both tassel templates)"
      exit 1
   fi

   if [[ ( -z $SAMPLE ) && ( -z "$GBS_COHORT" ) && ( -z "$ENZYME" ) && ( -z "$FLOWCELL" ) && ( -z "$SPECIES_MONIKER" ) && ( -z "$TAXID" ) ]]; then
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
   species_moniker_phrase=""
   taxid_phrase=""
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

   if [ ! -z "$SPECIES_MONIKER" ]; then
      # use design time binding here as there could be embedded blanks, and 
      # seems difficult to handle using the run time binding method
      species_moniker_phrase=" and lower(g.species) = lower('$SPECIES_MONIKER') "
   fi

   if [ ! -z "$TAXID" ]; then
      taxid_phrase=" and taxid = $TAXID "
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

   if [[ ( $TEMPLATE == "qc" ) || ( $TEMPLATE == "gbsx_qc" ) || ( $TEMPLATE == "qc1" ) ]] ; then
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by 
   factid;
"
      fi 
   elif [ $TEMPLATE == "qc1"  ]; then
      if [ $CLIENT_VERSION == "5" ]; then
code="
select
   Flowcell,
   Lane,
   Barcode,
   PlateRow||PlateColumn as sample,
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by
   factid;
"
      elif [ $CLIENT_VERSION == "3" ]; then
code="
select
   Flowcell,
   Lane,
   Barcode,
   PlateRow||PlateColumn as sample,
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by 
   1;
"
   elif [[ ( $TEMPLATE == "method" ) ]]; then
code="
select distinct
   flowcell,
   lane,
   coalesce( geno_method , 'default') 
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by
   1;
"
   elif [[ ( $TEMPLATE == "missing_files" ) ]]; then
code="
select distinct
   flowcell,
   lane,
   case
   when fastq_link is null then '** warning , fastq_link missing **'
   else fastq_link
   end  
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
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
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by
   1;
"
   elif [[ ( $TEMPLATE == "list_species" ) ]]; then
code="
select 
   species,
   count(*) as count
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
group by 
   species
order by
   1;
"
   elif [[ ( $TEMPLATE == "unblind" ) ]]; then
code="
select distinct
   qc_sampleid,
   sample
from 
   biosampleob s join gbsKeyFileFact g on 
   g.biosampleob = s.obid
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by 
   1;
"
   elif [[ ( $TEMPLATE == "unblind_script" ) ]]; then
code="
select distinct
   's/' || regexp_replace(qc_sampleid, E'[-\\\\.]','[-.]') || '/' || replace(sample,'/',E'\\\\/') || '/g'
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by
   1;
"
   elif [[ ( $TEMPLATE == "historical_unblind_script" ) ]]; then
code="
select distinct
   's/' || regexp_replace(qc_sampleid, E'[-\\\\.]','[-.]') || '/' || replace(sample,'/',E'\\\\/') || '/g'
from
   biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid
where
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
union
select
   's/' || regexp_replace(h.qc_sampleid, E'[-\\\\.]','[-.]') || '/' || replace(h.sample,'/',E'\\\\/') || '/g'
from
   (biosampleob s join gbsKeyFileFact g on
   g.biosampleob = s.obid) join gbs_sampleid_history_fact as h on 
   h.biosampleob = s.obid and h.sample = g.sample
where 
   $sample_phrase1 $enzyme_phrase $gbs_cohort_phrase $species_moniker_phrase $taxid_phrase $qc_cohort_phrase $exclusions_phrase
   and s.sampletype = 'Illumina GBS Library'
order by
   1;
"
   fi 

   echo "\a" > $script_name
   echo "\f '\t'" >> $script_name
   echo "\pset footer off " >> $script_name
   if [[ ( $TEMPLATE == "unblind_script" ) || ( $TEMPLATE == "historical_unblind_script" ) || ( $TEMPLATE == "blast_index_paths" ) || ( $TEMPLATE == "bwa_index_paths" ) || ( $TEMPLATE == "files" ) || ( $TEMPLATE == "method" ) || ( $TEMPLATE == "missing_files" ) || ( $TEMPLATE == "list_species" ) ]]; then
      echo "\t" >> $script_name
   fi
   echo $code >> $script_name
}

function run_extract() {
   if [[ ( -z $FLOWCELL ) || ( $TEMPLATE == "unblind" ) || ( $TEMPLATE == "unblind_script" ) || ( $TEMPLATE == "historical_unblind_script" ) || ( $TEMPLATE == "gbsx" ) || ( $TEMPLATE == "gbsx_qc" ) || ( $TEMPLATE == "blast_index_paths" ) || ( $TEMPLATE == "bwa_index_paths" ) || ( $TEMPLATE == "list_species" ) ]]; then
      if [ $DEBUG == 1 ]; then
         echo  psql -q -U gbs -d agrbrdf -h postgres -v keyfilename=\'$SAMPLE\' -v enzyme=\'$ENZYME\' -v gbs_cohort=\'$GBS_COHORT\' -v qc_cohort=\'$QC_COHORT\' -f $script_name
      fi 
      psql -q -U gbs -d agrbrdf -h postgres -v keyfilename=\'$SAMPLE\' -v enzyme=\'$ENZYME\' -v gbs_cohort=\'$GBS_COHORT\'  -v qc_cohort=\'$QC_COHORT\' -f $script_name
   else
      psql -q -U gbs -d agrbrdf -h postgres -v keyfilename=\'$SAMPLE\' -v enzyme=\'$ENZYME\' -v gbs_cohort=\'$GBS_COHORT\' -v qc_cohort=\'$QC_COHORT\' -f $script_name | egrep -i \($FLOWCELL\|flowcell\)  
   fi

   if [ $? != 0 ]; then
      echo " looks like extract failed - you might need to set up a .pgpass file in your home folder "
      exit 1
   fi 
}


get_opts "$@"

check_opts

build_extract_script 

run_extract 





