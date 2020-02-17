#!/bin/sh
#
function get_opts() {

help_text="\n
 this scripts imports a keyfile to a sample with optional update if the keyfile has already been imported\n

 importOrUpdateKeyfile.sh -s sample_name -k keyfile_base\n
\n
 e.g.\n
 importOrUpdateKeyfile.sh -s SQ0032 -k SQ0032\n
 importOrUpdateKeyfile.sh -s SQ0105 -k SQ0105_ApeKI\n
 importOrUpdateKeyfile.sh -n -s SQ0032 -k SQ0032\n
 jumps through various hoops due to idiosynchracies of\n
 \\copy and copy\n
"

DRY_RUN=no
INTERACTIVE=no
CREATE_FASTQ_COLUMN="no"

while getopts ":nhs:k:" opt; do
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

   # check if the keyfile is already in the database
   in_db=`$GBS_PRISM_BIN/is_keyfile_in_database.sh $KEYFILE_BASE`
   if [ $in_db != "0" ]; then
      echo "*(keyfile has previously been imported - this will be an update)*"
      ACTION="update"
   else
      echo "*(keyfile has not previously been imported - this will be an insert)*"
      ACTION="insert"
   fi 
   set +x
}

check_file_format() {
   set -x

   # check if file has fastq_link column
   fastq_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | grep -i fastq_link > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a fastq_link column)"
   else
      fastq_copy_include=",fastq_link"
   fi

   # check if file has control column
   control_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | grep -i control > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a control column)"
   else
      control_copy_include=",control"
   fi

   # check if file has counter column
   counter_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | grep -i counter > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a counter column)"
   else
      counter_copy_include=",counter"
   fi

   # check if file has bifo column
   bifo_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | grep -i bifo > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a bifo column)"
   else
      bifo_copy_include=",bifo"
   fi

   # check if file has windowsizecolumn
   windowsize_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | grep -i windowsize > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a windowsize column)"
   else
      windowsize_copy_include=",windowsize"
   fi

   # check if file has gbs_cohort column
   gbscohort_copy_include=""
   head -1 $KEY_DIR/$KEYFILE_BASE.txt | egrep -i "gbs(\s|_|-)cohort" > /dev/null
   if [ $? == 1 ]; then
      echo "($KEY_DIR/$KEYFILE_BASE.txt does not appear to contain a gbs_cohort column)"
   else
      gbscohort_copy_include=",gbs_cohort"
   fi


}


function echo_opts() {
    echo "importing $KEY_DIR/$KEYFILE_BASE.txt for sample $SAMPLE"
    echo "DRY_RUN=$DRY_RUN"
    echo "ACTION=$ACTION"
}

get_opts $@

check_opts
check_file_format
echo_opts

echo "importing data from $KEY_DIR/$KEYFILE_BASE.txt"
#more $KEY_DIR/$1.txt
if [ $INTERACTIVE == "yes" ]; then
   echo "do you want to continue ? (y/n)
   (you might want to check http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=${SAMPLE}&context=default
   to make sure this keyfile hasn't already been imported)
   "
   answer="n"
   read answer
   if [ "$answer" != "y" ]; then
      echo "OK quitting"
      exit 1
   fi
fi

rm -f /tmp/$KEYFILE_BASE.txt
if [ -f /tmp/$KEYFILE_BASE.txt ]; then
   echo "rm -f /tmp/$KEYFILE_BASE.txt failed - quitting"
   exit 1
fi
rm -f /tmp/$KEYFILE_BASE.psql
if [ -f /tmp/$KEYFILE_BASE.psql ]; then
   echo "rm -f /tmp/$KEYFILE_BASE.psql failed - quitting"
   exit 1
fi

cat $KEY_DIR/$KEYFILE_BASE.txt | iconv -c -t UTF8 | $GBS_PRISM_BIN/sanitiseKeyFile.py > /tmp/$KEYFILE_BASE.txt
if [ $? != 0 ]; then
   echo "Error looks like a malformed keyfile $KEY_DIR/$KEYFILE_BASE.txt ,this failed : 
   cat $KEY_DIR/$KEYFILE_BASE.txt | iconv -c -t UTF8 | $GBS_PRISM_BIN/sanitiseKeyFile.py
   "
   exit 1
fi

if [ $ACTION == "insert" ]; then

echo "
delete from keyfile_temp;

\copy keyfile_temp(Flowcell,Lane,Barcode,Sample,PlateName,PlateRow,PlateColumn,LibraryPrepID${counter_copy_include},Comment,Enzyme,Species,NumberOfBarcodes${bifo_copy_include}${control_copy_include}${windowsize_copy_include}${gbscohort_copy_include}${fastq_copy_include}) from /tmp/$KEYFILE_BASE.txt with NULL as ''

update keyfile_temp set gbs_cohort = lower(gbs_cohort) where gbs_cohort  is not null;
update keyfile_temp set gbs_cohort = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') where gbs_cohort is null;
update keyfile_temp set gbs_cohort = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') where length(ltrim(rtrim(gbs_cohort))) = 0;
update keyfile_temp set gbs_cohort = replace(gbs_cohort, ' ', '_');
update keyfile_temp set enzyme = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') ;
update keyfile_temp set enzyme = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') ;


insert into gbsKeyFileFact (
   biosampleob,
   Flowcell,
   Lane,
   Barcode,
   Sample,
   PlateName,
   PlateRow,
   PlateColumn,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   control,
   windowsize,
   gbs_cohort,
   fastq_link,
   voptypeid 
   )
select
   s.obid,
   Flowcell,
   Lane,
   Barcode,
   Sample,
   PlateName,
   PlateRow,
   PlateColumn,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   control,
   windowsize,
   gbs_cohort,
   fastq_link,
   93
from
   biosampleob as s join keyfile_temp as t on
   s.samplename = :samplename and
   s.sampletype = 'Illumina GBS Library';
" > /tmp/$KEYFILE_BASE.psql


# these next updates add an audit-trail of the import 
echo "
insert into datasourceob(xreflsid, datasourcename, datasourcetype)
select
   :keyfilename,
   :keyfilename,
   'GBS Keyfile'
where not exists (select obid from datasourceob where xreflsid = :keyfilename);

insert into importfunction(xreflsid,datasourceob, ob, importprocedureob)
select 
   bs.samplename || ':' || ds.datasourcename,
   ds.obid,
   bs.obid,
   ip.obid
from 
   (datasourceob ds join biosampleob bs on 
   ds.xreflsid = :keyfilename and bs.samplename = :samplename and sampletype = 'Illumina GBS Library') join
   importprocedureob ip on ip.xreflsid = 'importKeyfile.sh';
" >> /tmp/$KEYFILE_BASE.psql

# the next update assigns qc_sampleid to the newly imported samples 
echo "
update
   gbskeyfilefact as g
set
   qc_sampleid = q.qcsampleid
from (
   select
      sample,
      flowcell,
      libraryprepid,
      'qc'||min(factid)||'-'||count(*) as qcsampleid
   from
      gbskeyfilefact
   where 
      qc_sampleid is null and
      biosampleob = (select obid from
      biosampleob where samplename = :samplename and
      sampletype = 'Illumina GBS Library')
   group by
      flowcell,
      sample,
      libraryprepid 
) as q
where
   g.qc_sampleid is null and 
   g.sample = q.sample and
   g.flowcell = q.flowcell and
   g.libraryprepid = q.libraryprepid ;

" >> /tmp/$KEYFILE_BASE.psql

elif [ $ACTION == "update" ]; then 

echo "
delete from keyfile_temp;

\copy keyfile_temp(Flowcell,Lane,Barcode,Sample,PlateName,PlateRow,PlateColumn,LibraryPrepID${counter_copy_include},Comment,Enzyme,Species,NumberOfBarcodes${bifo_copy_include}${control_copy_include}${windowsize_copy_include}${gbscohort_copy_include}${fastq_copy_include}) from /tmp/$KEYFILE_BASE.txt with NULL as ''

update keyfile_temp set gbs_cohort = lower(gbs_cohort) where gbs_cohort  is not null;
update keyfile_temp set gbs_cohort = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') where gbs_cohort is null;
update keyfile_temp set gbs_cohort = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') where length(ltrim(rtrim(gbs_cohort))) = 0;
update keyfile_temp set gbs_cohort = replace(gbs_cohort, ' ', '_');
update keyfile_temp set enzyme = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') ;
update keyfile_temp set enzyme = replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') ;

insert into gbsKeyFileFact (
   biosampleob,
   Flowcell,
   Lane,
   Barcode,
   Sample,
   PlateName,
   PlateRow,
   PlateColumn,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   control,
   windowsize,
   gbs_cohort,
   fastq_link,
   voptypeid
   )
select
   s.obid,
   Flowcell,
   Lane,
   Barcode,
   Sample,
   PlateName,
   PlateRow,
   PlateColumn,
   LibraryPrepID,
   Counter,
   Comment,
   Enzyme,
   Species,
   NumberOfBarcodes,
   Bifo,
   control,
   windowsize,
   gbs_cohort,
   fastq_link,
   93
from
   biosampleob as s join keyfile_temp as t on
   s.samplename = :samplename and
   s.sampletype = 'Illumina GBS Library'
where not exists
   (select biosampleob from gbsKeyFileFact where
      Flowcell = t.Flowcell and 
      Lane = t.Lane and 
      Sample = t.Sample and 
      Barcode = t.Barcode and 
      PlateName = t.PlateName and 
      LibraryPrepID = t.LibraryPrepID );
" > /tmp/$KEYFILE_BASE.psql

# these next updates add an audit-trail of the import
echo "
insert into importfunction(xreflsid,datasourceob, ob, importprocedureob)
select
   bs.samplename || ':' || ds.datasourcename,
   ds.obid,
   bs.obid,
   ip.obid
from
   (datasourceob ds join biosampleob bs on
   ds.xreflsid = :keyfilename and bs.samplename = :samplename and bs.sampletype = 'Illumina GBS Library') join
   importprocedureob ip on ip.xreflsid = 'importOrUpdateKeyfile.sh';
" >> /tmp/$KEYFILE_BASE.psql

# the next update assigns qc_sampleid to the newly imported samples
echo "
update
   gbskeyfilefact as g
set
   qc_sampleid = q.qcsampleid
from (
   select
      sample,
      flowcell,
      libraryprepid,
      'qc'||min(factid)||'-'||count(*) as qcsampleid
   from
      gbskeyfilefact
   where
      qc_sampleid is null and
      biosampleob = (select obid from
      biosampleob where samplename = :samplename and
      sampletype = 'Illumina GBS Library')
   group by
      flowcell,
      sample,
      libraryprepid
) as q
where
   g.qc_sampleid is null and
   g.sample = q.sample and
   g.flowcell = q.flowcell and
   g.libraryprepid = q.libraryprepid ;
" >> /tmp/$KEYFILE_BASE.psql



fi


if [ $DRY_RUN == "no" ]; then
   psql -U agrbrdf -d agrbrdf -h invincible -v keyfilename=\'$KEYFILE_BASE\' -v samplename=\'$SAMPLE\' -f /tmp/$KEYFILE_BASE.psql
   result=$?
   psql -U agrbrdf -d agrbrdf -h invincible  -f $GBS_PRISM_BIN/fill_in_ref_indexes.psql
else
   echo "keyfile import : will run 
   psql -U agrbrdf -d agrbrdf -h invincible -v keyfilename=\'$KEYFILE_BASE\' -v samplename=\'$SAMPLE\' -f /tmp/$KEYFILE_BASE.psql
   psql -U agrbrdf -d agrbrdf -h invincible  -f $GBS_PRISM_BIN/fill_in_ref_indexes.psql
   "
fi

if [ $result != 0 ]; then
   echo "*** looks like this failed : psql -U agrbrdf -d agrbrdf -h invincible -v keyfilename=\'$KEYFILE_BASE\' -v samplename=\'$SAMPLE\' -f /tmp/$KEYFILE_BASE.psql
   (bad return code )
   ****" 
fi

echo "done (url to access keyfile is http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=${SAMPLE}&context=default )"

