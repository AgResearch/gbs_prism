#!/bin/bash
#
# this prism supports a basic q/c gbs analysis, of data that is assumed to be 
# generated and hosted by AgResearch  - i.e. there are dependencies on the 
# database etc. It assumes that the demultiplex prism has been run.
# 
#

function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_ROOT=""
   FORCE=no
   ENGINE=KGD_tassel3
   ANALYSIS=all
   NUM_THREADS=16
   PLATFORM=novaseq
   CUSTOM_PARAMETERS_FILE=""
   CUSTOM_FASTQ_PATH=""

   help_text="
usage :\n 
./ag_gbs_qc_prism.sh  [-h] [-n] [-d] [-f] [-C hpctype] [-j num_threads] [-a demultiplex|fasta_demultiplex|kgd|filtered_kgd|unblind|historical_unblind|fasta_sample|fastq_sample|kmer_analysis|allkmer_analysis|blast_analysis|bwa_mapping|all|html|trimmed_kmer_analysis|common_sequence|unblinded_plots|clean] -O outdir -r run cohort [.. cohort] \n
example:\n
./ag_gbs_qc_prism.sh -n -O /dataset/novaseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI  SQ2745.all.PstI.PstI  SQ2746.all.PstI.PstI  SQ0756.all.DEER.PstI  SQ0756.all.GOAT.PstI  SQ2743.all.PstI-MspI.PstI-MspI \n
./ag_gbs_qc_prism.sh -n -f -O /dataset/novaseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI SQ2745.all.PstI.PstI SQ2746.all.PstI.PstI SQ0756.all.DEER.PstI SQ0756.all.GOAT.PstI SQ2743.all.PstI-MspI.PstI-MspI\n
./ag_gbs_qc_prism.sh -n -f -C local -O /dataset/novaseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI SQ2745.all.PstI.PstI SQ2746.all.PstI.PstI SQ0756.all.DEER.PstI SQ0756.all.GOAT.PstI SQ2743.all.PstI-MspI.PstI-MspI \n
./ag_gbs_qc_prism.sh -n -f  -a kmer_analysis -O /dataset/gseq_processing/scratch/gbs/180824_D00390_0394_BCCPYFANXX -r 180824_D00390_0394_BCCPYFANXX SQ0784.all.DEER.PstI \n
./ag_gbs_qc_prism.sh -a html -O /dataset/gseq_processing/scratch/gbs/180925_D00390_0404_BCCVH0ANXX\n
"
   while getopts ":nhfO:C:r:a:j:m:p:q:" opt; do
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
       a)
         ANALYSIS=$OPTARG
         ;;
       j)
         NUM_THREADS=$OPTARG
         ;;
       m)
         PLATFORM=$OPTARG
         ;;
       p)
         CUSTOM_PARAMETERS_FILE=$OPTARG
         ;;
       q)
         CUSTOM_FASTQ_PATH=$OPTARG
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

   if [[ $PLATFORM != "novaseq" && $PLATFORM != "iseq" && $PLATFORM != "hiseq" && $PLATFORM != "miseq" ]]; then
      echo "platform (-m option) must be one of novaseq, iseq, hiseq, miseq"
      exit 1
   fi

   if [[ ( $ENGINE != "KGD_tassel3" ) ]] ; then
      echo "gbs engines supported : KGD_tassel3 (not $ENGINE ) "
      exit 1
   fi

   if [[ ( $ANALYSIS != "all" ) && ( $ANALYSIS != "demultiplex" ) && ( $ANALYSIS != "kgd" ) && ( $ANALYSIS != "filtered_kgd" ) &&  ( $ANALYSIS != "fasta_demultiplex" ) && ( $ANALYSIS != "clean" ) && ( $ANALYSIS != "unblind" ) && ( $ANALYSIS != "historical_unblind" ) && ( $ANALYSIS != "fasta_sample" ) && ( $ANALYSIS != "allkmer_analysis" ) && ( $ANALYSIS != "kmer_analysis" ) && ( $ANALYSIS != "blast_analysis" ) && ( $ANALYSIS != "annotation" )  && ( $ANALYSIS != "bwa_mapping" ) && ( $ANALYSIS != "html" ) && ( $ANALYSIS != "trimmed_kmer_analysis" )  && ( $ANALYSIS != "clientreport" )  && ( $ANALYSIS != "fastq_sample" ) && ( $ANALYSIS != "common_sequence" ) && ( $ANALYSIS != "unblinded_plots" ) && ( $ANALYSIS != "warehouse" ) ]]; then
      echo "analysis must be one of clientreport, html, trimmed_kmer_analysis, import_results, all, demultiplex, kgd, filtered_kgd, kmer_analysis, allkmer_analysis, fasta_sample, fastq_sample, annotation , bwa_mapping, unblind, historical_unblind , common_sequence, unblinded_plots, warehouse"
      exit 1
   fi

   if [ ! -z $CUSTOM_PARAMETERS_FILE ]; then
      if [ ! -f $CUSTOM_PARAMETERS_FILE ]; then
         echo "if specify a custom parameters file , file must exist "
         exit 1
      fi 
   fi

   if [ ! -z "$CUSTOM_FASTQ_PATH" ]; then
      if [ ! -d $CUSTOM_FASTQ_PATH ]; then
         echo "if specify a custom fastq path , path must exist and be a foldername "
         exit 1
      fi
   fi


}

function echo_opts() {
  echo OUT_ROOT=$OUT_ROOT
  echo DRY_RUN=$DRY_RUN
  echo DEBUG=$DEBUG
  echo HPC_TYPE=$HPC_TYPE
  echo COHORTS=${cohorts_array[*]}
  echo ENGINE=$ENGINE
  echo ANALYSIS=$ANALYSIS
  echo NUM_THREADS=$NUM_THREADS

}


#
# edit this method to set required environment (or set up
# before running this script)
#
function configure_env() {
   export CONDA_ENVS_PATH=$CONDA_ENVS_PATH:/dataset/bioinformatics_dev/active/conda-env
   cd $GBS_PRISM_BIN
   cp ag_gbs_qc_prism.sh $OUT_ROOT
   cp ag_gbs_qc_prism.mk $OUT_ROOT
   cp demultiplex_prism.sh $OUT_ROOT
   cp genotype_prism.sh $OUT_ROOT
   cp $GBS_PRISM_BIN/../melseq_prism/melseq_prism.sh $OUT_ROOT

   echo "
max_tasks=50
jobtemplatefile = \"$GBS_PRISM_BIN/etc/gbs_qc_slurm_array_job\"
" > $OUT_ROOT/tardis.toml

   echo "
conda activate bifo-essential
" > $OUT_ROOT/bifo-essential_env.inc

   echo "
conda activate /dataset/gseq_processing/active/bin/gbs_prism/conda/multiqc
" > $OUT_ROOT/multiqc_env.inc

   echo "
export CONDA_ENVS_PATH=$CONDA_ENVS_PATH
conda activate bioconductor
" > $OUT_ROOT/configure_bioconductor_env.src

   echo "
conda activate /dataset/gseq_processing/active/bin/gbs_prism/conda/gbs_prism 
" > $OUT_ROOT/gbs_prism_env.inc

   echo "
conda activate /dataset/bioinformatics_dev/active/conda-env/blast2.9
" > $OUT_ROOT/blast_env.inc

   NT_BLAST_DB=/dataset/blastdata/active/mirror/nt

   GENO_IMPORT_EXTENSION_DIR=/dataset/genophyle_data/active/database/Ndb/bin/snp_import
   GENO_IMPORT_SCRATCH_DIR=/dataset/genophyle_data/scratch/import_export

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

   rm -f $OUT_ROOT/*_targets.txt

   for ((j=0;$j<$NUM_COHORTS;j=$j+1)) do
      cohort=${cohorts_array[$j]}
      cohort_moniker=${RUN}.$cohort

      # extract keyfile and unblinding script for this cohort
      # cohort is like SQ0756.all.DEER.PstI
      libname=`echo $cohort | awk -F\. '{print $1}' -`
      qc_cohort=`echo $cohort | awk -F\. '{print $2}' -`
      gbs_cohort=`echo $cohort | awk -F\. '{print $3}' -`
      enzyme=`echo $cohort | awk -F\. '{print $4}' -`
      fcid=`echo $RUN | awk -F_ '{print substr($4,2)}' -`


      custom_fastq_path_phrase="dummy"
      if [ ! -z "$CUSTOM_FASTQ_PATH" ]; then
         custom_fastq_path_phrase="fastq_path=$CUSTOM_FASTQ_PATH"
      fi


      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t qc | sed -r 's/HpaII|HpaIII/MspI/g' - > $OUT_ROOT/${cohort_moniker}.key
      # keyfile for tassel
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;columns=flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link;$custom_fastq_path_phrase" $libname | sed -r 's/HpaII|HpaIII/MspI/g' - > $OUT_ROOT/${cohort_moniker}.key

      # gbsx keyfile 
      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t gbsx_qc > $OUT_ROOT/${cohort_moniker}.gbsx.key
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;columns=qc_sampleid as sample,Barcode,Enzyme" $libname > $OUT_ROOT/${cohort_moniker}.gbsx.key

      # unblind script
      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t unblind_script  > $OUT_ROOT/${cohort_moniker}.unblind.sed
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;unblinding;columns=qc_sampleid,sample;noheading" $libname > $OUT_ROOT/${cohort_moniker}.unblind.sed

      # historical unblinding  - not supported by gquery
      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t historical_unblind_script  > $OUT_ROOT/${cohort_moniker}.historical_unblind.sed
      echo "
      example query to generate a historical unblind script - but this is unlikely
      to be needed. The use case is , the keyfile has been reimported so new qc sampleid generated,
      but you want to unblind some old results

      select distinct 's/' || regexp_replace(qc_sampleid, E'[-\\.]','[-.]') || '/' || replace(sample,'/',E'\\/') || '/g' from biosampleob s join gbsKeyFileFact g on g.biosampleob = s.obid where s.samplename = :keyfilename and coalesce(qc_cohort,'included') != 'excluded' and s.sampletype = 'Illumina GBS Library' union select 's/' || regexp_replace(h.qc_sampleid, E'[-\\.]','[-.]') || '/' || replace(h.sample,'/',E'\\/') || '/g' from (biosampleob s join gbsKeyFileFact g on g.biosampleob = s.obid) join gbs_sampleid_history_fact as h on h.biosampleob = s.obid and h.sample = g.sample where s.samplename = :keyfilename and coalesce(qc_cohort,'included') != 'excluded' and s.sampletype = 'Illumina GBS Library' order by 1;
      " > $OUT_ROOT/${cohort_moniker}.historical_unblind.readme.txt

      # non-redundant fastq file listing
      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t files  > $OUT_ROOT/${cohort_moniker}.filenames
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;columns=lane,fastq_link;noheading;distinct;$custom_fastq_path_phrase" $libname > $OUT_ROOT/${cohort_moniker}.filenames

      # method
      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t method  | awk '{print $3}' - | sort -u > $OUT_ROOT/${cohort_moniker}.method
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;columns=geno_method;distinct;noheading;no_unpivot" $libname > $OUT_ROOT/${cohort_moniker}.method

      # check there is only one method for a cohort
      method_count=`wc -l $OUT_ROOT/${cohort_moniker}.method | awk '{print $1}' -`
      if [ $method_count != "1" ]; then
         echo "*** Bailing out as found $method_count distinct genotyping methods for cohort ${cohort_moniker} - should be exactly one. Has the keyfile for this cohort been imported ? If so check and change cohort defn or method geno_method col  ***"
         exit 1
      fi

      #$GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t bwa_index_paths > $OUT_ROOT/${cohort_moniker}.bwa_references
      gquery -t gbs_keyfile -b library -p "flowcell=$fcid;enzyme=$enzyme;gbs_cohort=$gbs_cohort;columns=gbs_cohort,refgenome_bwa_indexes;noheading;distinct" $libname > $OUT_ROOT/${cohort_moniker}.bwa_references 

      adapter_phrase="-a TCGTATGCCGTCTTCTGCTTG -a TCGTATGCCGTCTTCTGCTTG -a ATCTCGTATGCCGTCTTCTGCTTG -a GATCGGAAGAGCACACGTCT -a GATCGGAAGAGCACACGTCT -a AGATCGGAAGAG -a GATCGGAAGAGCACACGTCTGAACTCCAGTCAC -a AGATCGGAAGAGCGGTTCAGCAGGAATGCCGAGACCGATCTCGTATGCCGTCTTCTGCTT -a AGATCGGAAGAG -a GATCGGAAGAGCACACGTCT -a GATCGGAAGAGCACACGTCTGAACTCCAGTCAC"
      # the first 6 from an empirical assembly of recent data which matched 
      # Illumina NlaIII Gex Adapter 2.02 1885 TCGTATGCCGTCTTCTGCTTG
      # Illumina DpnII Gex Adapter 2.01 1885 TCGTATGCCGTCTTCTGCTTG
      # Illumina Small RNA 3p Adapter 1 1869 ATCTCGTATGCCGTCTTCTGCTTG
      # Illumina Multiplexing Adapter 1 1426 GATCGGAAGAGCACACGTCT
      # Illumina Universal Adapter 1423 AGATCGGAAGAG
      # Illumina Multiplexing Index Sequencing Primer 1337 GATCGGAAGAGCACACGTCTGAACTCCAGTCAC

      bwa_alignment_parameters="-B 10"

      for analysis_type in all bwa_mapping demultiplex kgd filtered_kgd fasta_demultiplex clean unblind historical_unblind kmer_analysis allkmer_analysis blast_analysis fasta_sample fastq_sample annotation common_sequence unblinded_plots ; do
         echo $OUT_ROOT/$cohort_moniker.$analysis_type  >> $OUT_ROOT/${analysis_type}_targets.txt
         script=$OUT_ROOT/${cohort_moniker}.${analysis_type}.sh
         if [ -f $script ]; then
            if [ ! $FORCE == yes ]; then
               echo "found existing gbs script $script  - will re-use (use -f to force rebuild of scripts) "
               continue
            fi
         fi
      done

      ############### demultiplex script (tassel demultiplex)
      custom_parameters_phrase=""
      if [ ! -z "$CUSTOM_PARAMETERS_FILE" ]; then
         custom_parameters_phrase="-p $CUSTOM_PARAMETERS_FILE"
      fi
      echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort
# run demultiplexing
./demultiplex_prism.sh -C $HPC_TYPE -x tassel3_qc $custom_parameters_phrase -l $OUT_ROOT/${cohort_moniker}.key  -e $enzyme -O $OUT_ROOT/$cohort \`cat $OUT_ROOT/${cohort_moniker}.filenames | awk '{print \$2}' -\` 
if [ \$? != 0 ]; then
   echo \"warning demultiplex of $OUT_ROOT/${cohort_moniker}.key returned an error code\"
   exit 1
fi
      " > $OUT_ROOT/${cohort_moniker}.demultiplex.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.demultiplex.sh

     ################ clean script
     mkdir -p $OUT_ROOT/clean

     # generate two scripts - the first one execs the second one , which deletes the first one
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
exec clean/${cohort_moniker}.clean.sh
     " > $OUT_ROOT/${cohort_moniker}.clean.sh
     chmod +x $OUT_ROOT/${cohort_moniker}.clean.sh
    
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT

# a recursive rm of the output folder can often be too slow - so just rename it
if [ -d $OUT_ROOT/OLD_$cohort ]; then
   # also slow but do no often encounter this case so OK 
   echo \"removing an older run $OUT_ROOT/OLD_$cohort...\" > $OUT_ROOT/clean/${cohort_moniker}.clean.log 2>&1
   rm -rf $OUT_ROOT/OLD_$cohort  >> $OUT_ROOT/clean/${cohort_moniker}.clean.log 2>&1
fi
mv $OUT_ROOT/$cohort $OUT_ROOT/OLD_$cohort   >> $OUT_ROOT/clean/${cohort_moniker}.clean.log 2>&1
rm -f *.${cohort}.*  >> $OUT_ROOT/clean/${cohort_moniker}.clean.log 2>&1
     " >  $OUT_ROOT/clean/${cohort_moniker}.clean.sh
      chmod +x $OUT_ROOT/clean/${cohort_moniker}.clean.sh

     ################ kgd script
     method=`cat $OUT_ROOT/${cohort_moniker}.method`
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort
# run genotyping
./genotype_prism.sh -C $HPC_TYPE -x KGD_tassel3 -p $method $OUT_ROOT/$cohort
if [ \$? != 0 ]; then
   echo \"warning , genotyping of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi

# create a merged tag count and sample stats file
# note that this assumes these two files are still expressed in terms of the internal qc sampleid  - if we find landmark files indicating these files have been unblinded , skip this step 
if [ -f $OUT_ROOT/$cohort/KGD/SampleStats.csv.blinded ]; then
   echo \"Warning, found unblinding landmark file $OUT_ROOT/$cohort/KGD/SampleStats.csv.blinded - unable to merge unblinded tag counts and sample stats files\"
   echo \"(you could do this manually using the following command : $GBS_PRISM_BIN/collate_tags_reads.py --report_name tags_reads_kgdstats  --kgd_stats_file $OUT_ROOT/$cohort/KGD/SampleStats.csv.blinded --run $RUN --cohort $cohort $OUT_ROOT/$cohort/TagCount.csv.blinded)\"
else
   $GBS_PRISM_BIN/collate_tags_reads.py --report_name tags_reads_kgdstats  --kgd_stats_file $OUT_ROOT/$cohort/KGD/SampleStats.csv --run $RUN --cohort $cohort $OUT_ROOT/$cohort/TagCount.csv > $OUT_ROOT/$cohort/TagCountsAndSampleStats.csv 
fi

python $GBS_PRISM_BIN/make_clientcohort_pages.py -U hapMap -K KGD -t \"KGD\" -o $OUT_ROOT/$cohort/KGD.html $OUT_ROOT/$cohort
     " >  $OUT_ROOT/${cohort_moniker}.kgd.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.kgd.sh 


     ################ filtered_kgd script
     method=`cat $OUT_ROOT/${cohort_moniker}.method`
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

mkdir -p $OUT_ROOT/$cohort/filtered_hapMap

tardis --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort --shell-include-file $OUT_ROOT/bifo-essential_env.inc cutadapt -f fasta --discard-untrimmed $adapter_phrase $OUT_ROOT/$cohort/hapMap/HapMap.fas.txt  1\>$OUT_ROOT/$cohort/filtered_hapMap/HapMap.fas.discarded.txt  2\>$OUT_ROOT/$cohort/filtered_hapMap/HapMap.fas.report.txt

tardis  --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort python $GBS_PRISM_BIN/merge_filtered_hapmap.py  -D $OUT_ROOT/$cohort/filtered_hapMap/HapMap.fas.discarded.txt -O $OUT_ROOT/$cohort/filtered_hapMap $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt $OUT_ROOT/$cohort/hapMap/HapMap.hmp.txt $OUT_ROOT/$cohort/hapMap/HapMap.fas.txt $OUT_ROOT/$cohort/hapMap/HapMap.hmp.txt.blinded $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt.blinded

cd $OUT_ROOT
mkdir -p $cohort
# run genotyping
./genotype_prism.sh -f -C $HPC_TYPE -x KGD_tassel3 -p $method -m filtered_hapMap -o filtered_KGD $OUT_ROOT/$cohort
if [ \$? != 0 ]; then
   echo \"warning , genotyping of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
python $GBS_PRISM_BIN/make_clientcohort_pages.py -U filtered_hapMap -K filtered_KGD -t \"Filtered KGD\" -o $OUT_ROOT/$cohort/filtered_KGD.html $OUT_ROOT/$cohort
     " >  $OUT_ROOT/${cohort_moniker}.filtered_kgd.sh
     chmod +x $OUT_ROOT/${cohort_moniker}.filtered_kgd.sh

     ################ fasta_demultiplex script
     # (this should work for any cohort, but is intended for making non-redundant fasta available to the microbiome pipelines , hence the path used below)
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN
export MELSEQ_PRISM_BIN=$GBS_PRISM_BIN/../melseq_prism

DEMUX_ROOT=/dataset/2024_illumina_sequencing_e/scratch/microbiome_fasta/qc/$libname
mkdir -p \$DEMUX_ROOT

# get keyfile needed
$GBS_PRISM_BIN/listDBKeyfile.sh -s $libname -t gbsx  | awk '{if(NR>1) print}' - > \$DEMUX_ROOT/sample_info.txt

\$MELSEQ_PRISM_BIN/_run_melseq -b -a format -O \$DEMUX_ROOT  \`cat $OUT_ROOT/${cohort_moniker}.filenames | awk '{print \$2}' -\` 
if [ \$? != 0 ]; then
   echo \"fasta_demultiplex returned an error code ( \$? )\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.fasta_demultiplex.sh
     chmod +x $OUT_ROOT/${cohort_moniker}.fasta_demultiplex.sh

     ################ unblind script
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
if [ ! -d $cohort ]; then 
   exit 1
fi
# generate unblinded output
for file in  $OUT_ROOT/$cohort/TagCount.csv $OUT_ROOT/$cohort/TagCountsAndSampleStats.csv $OUT_ROOT/$cohort/${cohort}.KGD_tassel3.KGD.stdout $OUT_ROOT/$cohort/KGD/*.csv $OUT_ROOT/$cohort/KGD/*.tsv $OUT_ROOT/$cohort/KGD/*.vcf $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt $OUT_ROOT/$cohort/hapMap/HapMap.hmp.txt $OUT_ROOT/$cohort/blast/locus*.txt $OUT_ROOT/$cohort/blast/locus*.dat $OUT_ROOT/$cohort/blast/taxonomy*.txt $OUT_ROOT/$cohort/blast/taxonomy*.dat $OUT_ROOT/$cohort/blast/frequency_table.txt $OUT_ROOT/$cohort/blast/information_table.txt $OUT_ROOT/$cohort/kmer_analysis/*.txt $OUT_ROOT/$cohort/kmer_analysis/*.dat $OUT_ROOT/$cohort/allkmer_analysis/*.txt $OUT_ROOT/$cohort/allkmer_analysis/*.dat ; do
   if [ -f \$file ]; then
      if [ ! -f \$file.blinded ]; then
         cp -p \$file \$file.blinded
      fi
      cat \$file.blinded | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > \$file
   fi
done
     " >  $OUT_ROOT/${cohort_moniker}.unblind.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.unblind.sh

     ################ historical unblind script (can be used in the corner (race-condition) case, where a keyfile was reloaded in another job, 
     # after the current job has completed processing, but before it has completed unblinding. In that case, samples have been assigned new 
     # qc_sampleids that do not correspond with those in the current process, and therefore they will not be unblinded by the usual default
     # script. 
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
if [ ! -d $cohort ]; then
   exit 1
fi
# generate unblinded output
for file in  $OUT_ROOT/$cohort/TagCount.csv $OUT_ROOT/$cohort/TagCountsAndSampleStats.csv $OUT_ROOT/$cohort/${cohort}.KGD_tassel3.KGD.stdout $OUT_ROOT/$cohort/KGD/*.csv $OUT_ROOT/$cohort/KGD/*.tsv $OUT_ROOT/$cohort/KGD/*.vcf $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt $OUT_ROOT/$cohort/hapMap/HapMap.hmp.txt $OUT_ROOT/$cohort/blast/locus*.txt $OUT_ROOT/$cohort/blast/locus*.dat $OUT_ROOT/$cohort/blast/taxonomy*.txt $OUT_ROOT/$cohort/blast/taxonomy*.dat $OUT_ROOT/$cohort/blast/frequency_table.txt $OUT_ROOT/$cohort/blast/information_table.txt $OUT_ROOT/$cohort/kmer_analysis/*.txt $OUT_ROOT/$cohort/kmer_analysis/*.dat $OUT_ROOT/$cohort/allkmer_analysis/*.txt $OUT_ROOT/$cohort/allkmer_analysis/*.dat ; do
   if [ -f \$file ]; then
      if [ ! -f \$file.historical_blinded ]; then
         cp -p \$file \$file.historical_blinded
      fi
      cat \$file.historical_blinded | sed -f $OUT_ROOT/${cohort_moniker}.historical_unblind.sed > \$file
   fi
done
     " >  $OUT_ROOT/${cohort_moniker}.historical_unblind.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.historical_unblind.sh


     ################ fasta_sample script (i.e. samples and also filters tags)
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/fasta_alldepthsample 
mkdir -p $cohort/fasta_medium_lowdepthsample
mkdir -p $cohort/fasta_small_lowdepthsample
# run fasta_sample
# sample all tags 
$SEQ_PRISMS_BIN/sample_prism.sh -C $HPC_TYPE  -a tag_count_unique -s .001 -O $OUT_ROOT/$cohort/fasta_alldepthsample $OUT_ROOT/$cohort/tagCounts/*.cnt
# small sample of low coverage tags (as used in GBS by KGD) - e.g. for blast work
$SEQ_PRISMS_BIN/sample_prism.sh -C $HPC_TYPE  -a tag_count_unique -t 2 -T 50 -s .002 -O $OUT_ROOT/$cohort/fasta_small_lowdepthsample $OUT_ROOT/$cohort/tagCounts/*.cnt
# medium sample of low coverage tags (as used in GBS by KGD) - e.g. for kmer analysis 
$SEQ_PRISMS_BIN/sample_prism.sh -C $HPC_TYPE  -a tag_count_unique -t 2 -T 50 -s .05 -O $OUT_ROOT/$cohort/fasta_medium_lowdepthsample $OUT_ROOT/$cohort/tagCounts/*.cnt

# trim the samples that will be used by blast
for landmark in $OUT_ROOT/$cohort/fasta_small_lowdepthsample/*.sample_prism ; do
   outbase=\`basename \$landmark .sample_prism\`
   fasta_sample=$OUT_ROOT/$cohort/fasta_small_lowdepthsample/\${outbase}.fasta
   outdir=\`dirname \$fasta_sample\`
   tardis -d $OUT_ROOT/$cohort --hpctype $HPC_TYPE --shell-include-file $OUT_ROOT/bifo-essential_env.inc cutadapt -f fasta -m 1 $adapter_phrase \$fasta_sample 1\>\$outdir/\${outbase}.trimmed.fasta 2\>\$outdir/\${outbase}.trimmed.fasta.report
done

if [ \$? != 0 ]; then
   echo \"warning , fasta sample of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.fasta_sample.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.fasta_sample.sh 


     ################ fastq_sample script (uses gbsx demuliplex)
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/fastq
mkdir -p $cohort/fastq_sample

# first demultiplex
./demultiplex_prism.sh -C $HPC_TYPE -x gbsx -l $OUT_ROOT/${cohort_moniker}.gbsx.key -O $OUT_ROOT/$cohort/fastq \`cat $OUT_ROOT/${cohort_moniker}.filenames | awk '{print \$2}' -\`
if [ \$? != 0 ]; then
   echo \"warning gbsx demultiplex of $OUT_ROOT/${cohort_moniker}.gbsx.key returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.fastq_sample.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.fastq_sample.sh

     ################ blast script 
### note ###
# Re "Misunderstood parameter of NCBI BLAST impacts the correctness of bioinformatics workflows", Nidhi Shah  Michael G Nute  Tandy Warnow  Mihai Pop
# and our use of "-max_target_seqs 1"
# In the present context, the top hit returned from each (randomly sampled) sequence, from each sequenced biological sample, 
# is used to prepare a numeric profile vector for each file, with the semantic details of the hits discarded.
# The numeric vectors are then input to unsupervised machine learning - for example clustered
# - so that we can highlight how similar or dissimilar new files are to previous files, and to each other.
# It is not necessary for our purpose here that the hit returned , is the best (i.e. lowest evalue) in the database.
# (This ("non-semantic") approach does depend on the same database version being used throughout
# the series of files - and this would be true even if this blast parameter behaved as intuitively 
# expected - i.e. returned the actual best hit in the database).
############
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/blast
# configure a custom slurm batch job that will specify medium memory 
cp $GBS_PRISM_BIN/etc/medium_mem_slurm_array_job $OUT_ROOT
echo \"
jobtemplatefile = \\\"$OUT_ROOT/medium_mem_slurm_array_job\\\"
max_tasks = 60
\" > $OUT_ROOT/$cohort/blast/tardis.toml
# run blast
$SEQ_PRISMS_BIN/align_prism.sh -C $HPC_TYPE -j $NUM_THREADS -m 60 -a blastn -e $OUT_ROOT/blast_env.inc -r $NT_BLAST_DB -p \"-evalue 1.0e-10  -dust \\'20 64 1\\' -max_target_seqs 1 -outfmt \\'7 qseqid sseqid pident evalue staxids sscinames scomnames sskingdoms stitle\\'\" -O $OUT_ROOT/$cohort/blast $OUT_ROOT/$cohort/fasta_small_lowdepthsample/*.trimmed.fasta
if [ \$? != 0 ]; then
   echo \"warning , blast  of $OUT_ROOT/$cohort/fasta_small_lowdepthsample returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.blast_analysis.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.blast_analysis.sh


     ################ annotation script 
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
# summarise species from blast results 
$SEQ_PRISMS_BIN/annotation_prism.sh -C $HPC_TYPE -w tag_count -a taxonomy -O $OUT_ROOT/$cohort/blast $OUT_ROOT/$cohort/blast/*.results.gz  
return_code1=\$?
# summarise descriptions from blast results 
rm -f $OUT_ROOT/$cohort/blast/*.annotation_prism
$SEQ_PRISMS_BIN/annotation_prism.sh -C $HPC_TYPE -w tag_count -a description -O $OUT_ROOT/$cohort/blast $OUT_ROOT/$cohort/blast/*.results.gz  
return_code2=\$?
# provide unblinded frequency tables
for file in  $OUT_ROOT/$cohort/blast/frequency_table.txt $OUT_ROOT/$cohort/blast/locus_freq.txt ; do
   if [ -f \$file ]; then
      if [ ! -f \$file.blinded ]; then
         cp -p \$file \$file.blinded
      fi
      cat \$file.blinded | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > \$file
   fi
done
if [[ ( \$return_code1 != 0 ) || ( \$return_code2 != 0 ) ]]; then
   echo \"warning, summary of $OUT_ROOT/$cohort/blast returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.annotation.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.annotation.sh 


     ################ low-depth kmer summary script
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/kmer_analysis
$SEQ_PRISMS_BIN/kmer_prism.sh -C $HPC_TYPE -j $NUM_THREADS -a fasta -p \"-k 6 -A --weighting_method tag_count\" -O $OUT_ROOT/$cohort/kmer_analysis $OUT_ROOT/$cohort/fasta_medium_lowdepthsample/*.fasta 
if [ \$? != 0 ]; then
   echo \"warning, kmer analysis of $OUT_ROOT/$cohort/fasta_medium_lowdepthsample returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.kmer_analysis.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.kmer_analysis.sh


     ################ all-depth kmer summary script
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/allkmer_analysis
$SEQ_PRISMS_BIN/kmer_prism.sh -C $HPC_TYPE -j $NUM_THREADS -a fasta -p \"-k 6 -A --weighting_method tag_count\" -O $OUT_ROOT/$cohort/allkmer_analysis $OUT_ROOT/$cohort/fasta_alldepthsample/*.fasta 
if [ \$? != 0 ]; then
   echo \"warning, kmer analysis of $OUT_ROOT/$cohort/fasta_alldepthsample returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.allkmer_analysis.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.allkmer_analysis.sh


     ################ bwa mapping script (includes sampling and trimming)
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p bwa_mapping/$cohort   # note - must not allow tassel to see any fastq file names under $cohort ! 
#
# sample each file referred to in $OUT_ROOT/${cohort_moniker}.filenames
$SEQ_PRISMS_BIN/sample_prism.sh -C $HPC_TYPE  -s .00005 -M 15000 -a fastq -O $OUT_ROOT/bwa_mapping/$cohort \`cut -f 2 $OUT_ROOT/${cohort_moniker}.filenames\`   
if [ \$? != 0 ]; then
   echo \"warning, sampling in $OUT_ROOT/bwa_mapping/$cohort returned an error code\"
   exit 1
fi
# trim the samples 
for fastq_sample in $OUT_ROOT/bwa_mapping/$cohort/*.s.00005.fastq.gz; do
   outbase=\`basename \$fastq_sample .fastq.gz \`
   tardis -d $OUT_ROOT/bwa_mapping/$cohort --hpctype $HPC_TYPE --shell-include-file $OUT_ROOT/bifo-essential_env.inc cutadapt -f fastq $adapter_phrase \$fastq_sample \> $OUT_ROOT/bwa_mapping/$cohort/\$outbase.trimmed.fastq 2\>$OUT_ROOT/bwa_mapping/$cohort/\$outbase.trimmed.report
   if [ \$? != 0 ]; then
      echo \"warning, cutadapt of \$fastq_sample returned an error code\"
      exit 1
   fi
done

# align the trimmed samples to the references referred to in $OUT_ROOT/${cohort_moniker}.bwa_references if it exists
cut -f 2 $OUT_ROOT/$cohort_moniker.bwa_references > $OUT_ROOT/bwa_mapping/$cohort/references.txt
contents=\`head -1 $OUT_ROOT/bwa_mapping/$cohort/references.txt\`
if [ ! -z \"\$contents\" ]; then
   $SEQ_PRISMS_BIN/align_prism.sh -C $HPC_TYPE -m 60 -a bwa -r $OUT_ROOT/bwa_mapping/$cohort/references.txt -p \"$bwa_alignment_parameters\" -O $OUT_ROOT/bwa_mapping/$cohort -C $HPC_TYPE $OUT_ROOT/bwa_mapping/$cohort/*.trimmed.fastq
   if [ \$? != 0 ]; then
      echo \"warning, bwa mapping in $OUT_ROOT/bwa_mapping/$cohort returned an error code\"
      exit 1
   fi
   # rm the short-cuts that the sampler created in case we rerun this (else it will create additional redundant ones) 
   for link in $OUT_ROOT/bwa_mapping/$cohort/*.fastq.gz; do
      if [ -h \$link ]; then
         rm -f \$link
      fi
   done
fi
     " >  $OUT_ROOT/${cohort_moniker}.bwa_mapping.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.bwa_mapping.sh

     ################ common sequences script  
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
# trimmed sequence
mkdir -p common_sequence/$cohort/trimmed_sequence # note - must not allow tassel to see any fastq file names under $cohort !
$SEQ_PRISMS_BIN/kmer_prism.sh -C $HPC_TYPE -j $NUM_THREADS -a fastq -p \"-k 6 -A\" -O $OUT_ROOT/common_sequence/$cohort/trimmed_sequence $OUT_ROOT/bwa_mapping/$cohort/*.trimmed.fastq > $OUT_ROOT/common_sequence/$cohort/trimmed_sequence/kmer_analysis.log

cd $OUT_ROOT
# tags
mkdir -p common_sequence/$cohort/lowdepth_tags
cat $OUT_ROOT/$cohort/fasta_medium_lowdepthsample/*.fasta >  common_sequence/$cohort/lowdepth_tags/sample.fasta
$SEQ_PRISMS_BIN/kmer_prism.sh -C $HPC_TYPE -j $NUM_THREADS -a fasta -p \"-k 6 -A --weighting_method tag_count\" -O $OUT_ROOT/common_sequence/$cohort/lowdepth_tags $OUT_ROOT/common_sequence/$cohort/lowdepth_tags/sample.fasta

if [ \$? != 0 ]; then
   echo \"warning, common_sequence analysis of $OUT_ROOT/bwa_mapping/$cohort/*.trimmed.fastq  returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.common_sequence.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.common_sequence.sh


     ################ unblinded plots script
     # (code here is cloned from seq_prisms  - we attempt to do "unblinded" plots. This 
     # may occassionally fail due to feral sample names. If these succeed then the 
     # unblinded plots supercede the blinded ones. If anything here fails, the blinded 
     # plot is still available.
     echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_ROOT
mkdir -p $cohort/unblinded_plots

# taxonomy plots if applicable 
if [ -f $cohort/blast/information_table.txt ]; then
   cat $cohort/blast/information_table.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > $cohort/unblinded_plots/information_table.txt
   cat $cohort/blast/locus_freq.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > $cohort/unblinded_plots/locus_freq.txt
   cat $cohort/blast/frequency_table.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > $cohort/unblinded_plots/frequency_table.txt

   tardis --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort/unblinded_plots --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla  $SEQ_PRISMS_BIN/taxonomy_prism.r analysis_name=\'$ANALYSIS_NAME\' summary_table_file=$OUT_ROOT/$cohort/unblinded_plots/information_table.txt output_base=\"taxonomy_summary\" 1\>$OUT_ROOT/$cohort/unblinded_plots/tax_plots.stdout  2\>$OUT_ROOT/$cohort/unblinded_plots/tax_plots.stderr

   tardis --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort/unblinded_plots --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla  $SEQ_PRISMS_BIN/locus_summary_heatmap.r num_profiles=50 moniker="locus_freq" datafolder=$OUT_ROOT/$cohort/unblinded_plots 1\>\>$OUT_ROOT/$cohort/unblinded_plots/tax_plots.stdout  2\>\>$OUT_ROOT/$cohort/unblinded_plots/tax_plots.stderr

fi

#low depth kmer plots if applicable
mkdir -p $cohort/unblinded_plots/kmer_analysis
if [ -f $cohort/kmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt ]; then
   cat $cohort/kmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed | sed -r 's/.cnt.tag_count_unique.s.05m2T[[:digit:]]+_taggt2.fasta.k6Aweighting_methodtag_count.1.kmerdist//g' - > $cohort/unblinded_plots/kmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt
fi
if [ -f $cohort/kmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt ]; then
   cat $cohort/kmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed |  sed -r 's/.cnt.tag_count_unique.s.05m2T[[:digit:]]+_taggt2.fasta.k6Aweighting_methodtag_count.1.kmerdist//g' > $cohort/unblinded_plots/kmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt
fi

# first do plots including N's , then rename and do plots excluding N's
if [ -f $cohort/unblinded_plots/kmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt ]; then
   for version in \"\" \"_plus\" ; do
      rm -f $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/kmer_summary.txt
      cp -s $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/kmer_summary\${version}.k6Aweighting_methodtag_count.txt $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/kmer_summary.txt
      tardis.py --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla $SEQ_PRISMS_BIN/kmer_plots.r datafolder=$OUT_ROOT/$cohort/unblinded_plots/kmer_analysis  1\>\> $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/kmer_prism.log 2\>\> $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/kmer_prism.log
      for output in kmer_entropy kmer_zipfian_comparisons kmer_zipfian zipfian_distances; do
         if [ -f $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}.jpg ]; then
            mv $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}.jpg $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}\${version}.k6Aweighting_methodtag_count.jpg
         fi
      done
      for output in heatmap_sample_clusters  zipfian_distances_fit ; do
         if [ -f $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}.txt ]; then
            mv $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}.txt $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/\${output}${version}.k6Aweighting_methodtag_count.txt
         fi
      done
   done
fi


#all-depth kmer plots
mkdir -p $cohort/unblinded_plots/allkmer_analysis
if [ -f $cohort/allkmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt ]; then
   cat $cohort/allkmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed | sed 's/.cnt.tag_count_unique.s.001.fasta.k6Aweighting_methodtag_count.1.kmerdist//g' - > $cohort/unblinded_plots/allkmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt
fi
if [ -f $cohort/allkmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt ]; then
   cat $cohort/allkmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed | sed 's/.cnt.tag_count_unique.s.001.fasta.k6Aweighting_methodtag_count.1.kmerdist//g' - > $cohort/unblinded_plots/allkmer_analysis/kmer_summary_plus.k6Aweighting_methodtag_count.txt
fi

# first do plots including N's , then rename and do plots excluding N's
if [ -f $cohort/unblinded_plots/allkmer_analysis/kmer_summary.k6Aweighting_methodtag_count.txt ]; then
   for version in \"\" \"_plus\" ; do
      rm -f $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/kmer_summary.txt
      cp -s $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/kmer_summary\${version}.k6Aweighting_methodtag_count.txt $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/kmer_summary.txt
      tardis.py --hpctype $HPC_TYPE -d $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla $SEQ_PRISMS_BIN/kmer_plots.r datafolder=$OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis  1\>\> $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/kmer_prism.log 2\>\> $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/kmer_prism.log
      for output in kmer_entropy kmer_zipfian_comparisons kmer_zipfian zipfian_distances; do
         if [ -f $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}.jpg ]; then
            mv $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}.jpg $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}\${version}.k6Aweighting_methodtag_count.jpg
         fi
      done
      for output in heatmap_sample_clusters  zipfian_distances_fit ; do
         if [ -f $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}.txt ]; then
            mv $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}.txt $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/\${output}${version}.k6Aweighting_methodtag_count.txt
         fi
      done
   done
fi


if [ \$? != 0 ]; then
   echo \"warning, unblinded plots of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.unblinded_plots.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.unblinded_plots.sh
   done
}

function fake() {
   echo "dry run ! 

   "
   exit 0
}

function run() {
   cd $OUT_ROOT

   if [ $FORCE == "yes" ]; then
      echo "cleaning any existing target files so targets will be remade. . . "
      for target in `cat $OUT_ROOT/${ANALYSIS}_targets.txt`; do
         rm -f $target
      done
   else
      echo "warning, not cleaning existing target files - use -f option to force a rebuild"
   fi

   make -f ag_gbs_qc_prism.mk -d -k  --no-builtin-rules -j $NUM_THREADS `cat $OUT_ROOT/${ANALYSIS}_targets.txt` > $OUT_ROOT/${ANALYSIS}.log 2>&1

   # run summaries
}

function trimmed_kmer_analysis() {
   # kmer analysis of a sample of all the trimmed raw data 
   cd $OUT_ROOT
   mkdir -p trimmed_kmer_analysis
   if [ ! -d $OUT_ROOT/bwa_mapping ]; then
      echo "*** please run bwa mapping before trimmed kmer analysis - unable to run trimmed kmer analysis as no trimmed fastq available yet ***"
   else
      cp -fs $OUT_ROOT/bwa_mapping/*/*.trimmed.fastq $OUT_ROOT/trimmed_kmer_analysis   # this step eliminates duplicate filenames 
      $SEQ_PRISMS_BIN/kmer_prism.sh -C $HPC_TYPE -j $NUM_THREADS -a fastq -p "-k 6 -A" -O $OUT_ROOT/trimmed_kmer_analysis $OUT_ROOT/trimmed_kmer_analysis/*.trimmed.fastq  > $OUT_ROOT/trimmed_kmer_analysis/kmer_analysis.log
   fi
}

function html() {
   mkdir -p $OUT_ROOT/html
   OUT_BASE=`dirname $OUT_ROOT`
   RUN_FOLDER=`basename $OUT_ROOT`

   # make shortcuts to output files that wil be linked to , under html root
   for ((j=0;$j<$NUM_COHORTS;j=$j+1)) do
      cohort=${cohorts_array[$j]}

      # copy some misc files 
      mkdir -p  $OUT_ROOT/html/$cohort
      cp -s $OUT_ROOT/$cohort/*.FastqToTagCount.stdout $OUT_ROOT/html/$cohort/FastqToTagCount.stdout
      cp -s $OUT_ROOT/$cohort/*.KGD_tassel3.KGD.stdout $OUT_ROOT/html/$cohort/KGD.stdout

      mkdir -p  $OUT_ROOT/html/$cohort/KGD
      for file in $OUT_ROOT/$cohort/TagCount.csv; do
         cp -s $file $OUT_ROOT/html/$cohort
      done

      for file in $OUT_ROOT/$cohort/TagCountsAndSampleStats.csv; do
         cp -s $file $OUT_ROOT/html/$cohort
      done

      rm $OUT_ROOT/html/$cohort/KGD/*
      for file in $OUT_ROOT/$cohort/KGD/*; do
         cp -s $file $OUT_ROOT/html/$cohort/KGD
      done

      mkdir -p  $OUT_ROOT/html/$cohort/kmer_analysis
      rm $OUT_ROOT/html/$cohort/kmer_analysis/*
      # first copy blinded files 
      for file in $OUT_ROOT/$cohort/kmer_analysis/*.jpg $OUT_ROOT/$cohort/kmer_analysis/*.txt ; do
         cp -s $file $OUT_ROOT/html/$cohort/kmer_analysis
      done
      # try replacing with unblinded files that are available (depending on sample names, unblinded plotting  may fail)
      for file in $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/*.jpg $OUT_ROOT/$cohort/unblinded_plots/kmer_analysis/*.txt ; do
         cp -fs $file $OUT_ROOT/html/$cohort/kmer_analysis
      done

      # first copy blinded files 
      mkdir -p  $OUT_ROOT/html/$cohort/allkmer_analysis
      rm $OUT_ROOT/html/$cohort/allkmer_analysis/*
      for file in $OUT_ROOT/$cohort/allkmer_analysis/*.jpg $OUT_ROOT/$cohort/allkmer_analysis/*.txt ; do
         cp -s $file $OUT_ROOT/html/$cohort/allkmer_analysis
      done
      # try replacing with unblinded files that are available (depending on sample names, unblinded plotting  may fail)
      for file in $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/*.jpg $OUT_ROOT/$cohort/unblinded_plots/allkmer_analysis/*.txt ; do
         cp -fs $file $OUT_ROOT/html/$cohort/allkmer_analysis
      done

      # first try blinded files
      mkdir -p  $OUT_ROOT/html/$cohort/blast
      rm $OUT_ROOT/html/$cohort/blast/*
      for file in $OUT_ROOT/$cohort/blast/*.jpg $OUT_ROOT/$cohort/blast/taxonomy*clusters.txt $OUT_ROOT/$cohort/blast/frequency_table.txt  $OUT_ROOT/$cohort/blast/locus_freq.txt; do
         cp -s $file $OUT_ROOT/html/$cohort/blast
      done
      # try replacing with unblinded files that are available (depending on sample names, unblinded plotting  may fail)
      for file in $OUT_ROOT/$cohort/unblinded_plots/*.jpg $OUT_ROOT/$cohort/unblinded_plots/taxonomy*clusters.txt; do
         cp -fs $file $OUT_ROOT/html/$cohort/blast
      done

      mkdir -p  $OUT_ROOT/html/$cohort/hapMap
      rm $OUT_ROOT/html/$cohort/hapMap 
      for file in $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt $OUT_ROOT/$cohort/hapMap/HapMap.fas.txt; do
         cp -s $file $OUT_ROOT/html/$cohort/hapMap
      done

      mkdir -p $OUT_ROOT/html/$cohort/common_sequence
      rm $OUT_ROOT/common_sequence/$cohort/all_common_sequence_trimmed.txt
      rm $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_trimmed.txt
      for file in $OUT_ROOT/common_sequence/$cohort/trimmed_sequence/*.k6A.log ; do
         grep assembled_by_distinct $file | sed 's/assembled_by_distinct//g' >> $OUT_ROOT/common_sequence/$cohort/all_common_sequence_trimmed.txt 
         grep assembled_by_distinct $file | head -10 | sed 's/assembled_by_distinct//g' >> $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_trimmed.txt 
      done
      for file in $OUT_ROOT/common_sequence/$cohort/all_common_sequence_trimmed.txt $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_trimmed.txt; do
         cp -s $file $OUT_ROOT/html/$cohort/common_sequence
      done
      rm $OUT_ROOT/common_sequence/$cohort/all_common_sequence_lowdepthtags.txt
      rm $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_lowdepthtags.txt
      for file in $OUT_ROOT/common_sequence/$cohort/lowdepth_tags/*.k6A*.log ; do
         grep assembled_by_distinct $file | sed 's/assembled_by_distinct//g' >> $OUT_ROOT/common_sequence/$cohort/all_common_sequence_lowdepthtags.txt
         grep assembled_by_distinct $file | head -10 | sed 's/assembled_by_distinct//g' >> $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_lowdepthtags.txt
      done
      for file in $OUT_ROOT/common_sequence/$cohort/all_common_sequence_lowdepthtags.txt $OUT_ROOT/common_sequence/$cohort/preview_common_sequence_lowdepthtags.txt; do
         cp -s $file $OUT_ROOT/html/$cohort/common_sequence
      done


      # summarise overall SNP yield and information efficiency in cohort
      $GBS_PRISM_BIN/get_snp_yield.py $OUT_ROOT/$cohort/*.FastqToTagCount.stdout $OUT_ROOT/$cohort/hapMap/HapMap.hmc.txt  > $OUT_ROOT/$cohort/overall_snp_yield.txt
      $GBS_PRISM_BIN/snp_info_from_vcf.py $OUT_ROOT/$cohort/KGD/GHW05.vcf > $OUT_ROOT/$cohort/information_efficiency.txt


      # locate and summarise the deduplication counts.
      # currently this is done as follows:
      # * get fastq links from the Illumina folder in the cohort processing folder
      # * from these get the real paths 
      # * the dedupe summary is a file in the same folder as the fastq
      # * summarise this into a text file in the cohort folder
      # * present this inline in the web page
      $GBS_PRISM_BIN/get_dedupe_log.py $OUT_ROOT/$cohort/Illumina/* > $OUT_ROOT/html/$cohort/dedupe_summary.txt

   done

   cp -s $OUT_ROOT/SampleSheet.csv $OUT_ROOT/html

   # fastqc and multiqc
   mkdir -p $OUT_ROOT/html/multiqc
   rm -rf $OUT_ROOT/html/multiqc/*
   tardis -d $OUT_ROOT --hpctype local --shell-include-file $OUT_ROOT/multiqc_env.inc  multiqc --interactive -i \"multifastqc for $RUN\" -o $OUT_ROOT/html/multiqc $OUT_ROOT/../../illumina/$PLATFORM/$RUN/*/fastqc_run/fastqc
   
   cp -pR $OUT_ROOT/../../illumina/$PLATFORM/$RUN/*/fastqc_run/fastqc $OUT_ROOT/html/fastqc

   # bclconvert
   mkdir $OUT_ROOT/html/bclconvert
   cp -pR $OUT_ROOT/../../illumina/$PLATFORM/$RUN/*/bclconvert/Reports/html/* $OUT_ROOT/html/bclconvert
   mkdir -p $OUT_ROOT/html/kmer_analysis
   for file in kmer_entropy.k6A.jpg heatmap_sample_clusters.k6A.txt kmer_zipfian_comparisons.k6A.jpg ; do
      cp -s $OUT_ROOT/../../illumina/$PLATFORM/$RUN/*/kmer_run/kmer_analysis/$file $OUT_ROOT/html/kmer_analysis
   done
   mkdir -p $OUT_ROOT/html/trimmed_kmer_analysis
   for file in kmer_entropy.k6A.jpg heatmap_sample_clusters.k6A.txt kmer_zipfian_comparisons.k6A.jpg ; do
      cp -s $OUT_ROOT/trimmed_kmer_analysis/$file $OUT_ROOT/html/trimmed_kmer_analysis
   done


   # make peacock page which mashes up plots, output files etc.
   $GBS_PRISM_BIN/make_cohort_pages.py -r $RUN_FOLDER -b $OUT_BASE -o $OUT_ROOT/html/peacock.html

   # (re ) summarise bwa mappings 
   tardis --hpctype local -d $OUT_ROOT/html $SEQ_PRISMS_BIN/collate_mapping_stats.py $OUT_ROOT/bwa_mapping/*/*.stats \> $OUT_ROOT/html/stats_summary.txt
   tardis --hpctype local -d $OUT_ROOT/html --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla  $SEQ_PRISMS_BIN/mapping_stats_plots.r datafolder=$OUT_ROOT/html

   # (re ) summarise barcode yields 
   tardis --hpctype local -d $OUT_ROOT/html $GBS_PRISM_BIN/collate_barcode_yields.py $OUT_ROOT/*/*.tassel3_qc.FastqToTagCount.stdout \> $OUT_ROOT/html/barcode_yield_summary.txt
   tardis --hpctype local -d $OUT_ROOT/html --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla  $GBS_PRISM_BIN/barcode_yields_plots.r datafolder=$OUT_ROOT/html

   # summarise and plot tag and read counts by cohort
   # CV
   $GBS_PRISM_BIN/summarise_read_and_tag_counts.py -o $OUT_ROOT/html/tags_reads_summary.txt $OUT_ROOT/S*/TagCount.csv
   cat $OUT_ROOT/html/tags_reads_summary.txt | awk -F'\t' '{printf("%s\t%s\t%s\n",$1,$4,$9)}' - > $OUT_ROOT/html/tags_reads_cv.txt
   $GBS_PRISM_BIN/summarise_read_and_tag_counts.py -t unsummarised -o $OUT_ROOT/html/tags_reads_list.txt $OUT_ROOT/S*/TagCount.csv
   Rscript --vanilla  $GBS_PRISM_BIN/tag_count_plots.r infile=$OUT_ROOT/html/tags_reads_list.txt outfolder=$OUT_ROOT/html 
   convert $OUT_ROOT/html/tag_stats.jpg $OUT_ROOT/html/read_stats.jpg +append $OUT_ROOT/html/tag_read_stats.jpg

}

function clientreport() {
   if [ ! -d $OUT_ROOT/html ]; then 
      echo "could not find $OUT_ROOT/html (please generate the html summaries first)"
      exit 1
   fi

   echo "refreshing GBS tab extract. . . "
   gquery -t sql -p "interface_type=postgres;host=postgres_readonly" $GBS_PRISM_BIN/get_genophyle_export.sql > $GENO_IMPORT_SCRATCH_DIR/genophyle_gbs_import.txt


   echo "generating client reports. . . "
   $GBS_PRISM_BIN/make_clientcohort_pages.py -r $RUN -o report.html
   for ((j=0;$j<$NUM_COHORTS;j=$j+1)) do
      set -x
      cohort=${cohorts_array[$j]}
      cd  $OUT_ROOT/html/$cohort 
      rm -f report.zip report.tar*
      tar -cv --auto-compress --dereference -f report.tar.gz  --files-from=report.html.manifest
      cat report.html.manifest | zip -@ report
      set +x
   done
}

function warehouse() {
   echo "refreshing the GBS tab in genophyle. . . "
   python $GENO_IMPORT_EXTENSION_DIR/geno_import.py -H invsqlpv05 -t gbs_tab $GENO_IMPORT_SCRATCH_DIR/genophyle_gbs_import.txt | tee $OUT_ROOT/warehouse_update.log
   return_code=$?
}


function clean() {
   echo "to clean up tardis working folders, execute this : 

   nohup find $OUT_ROOT -name "tardis_*" -type d -exec rm -r {} \; > $OUT_ROOT/gbs_clean.log 2>&1 &

   "
}


function main() {
   get_opts "$@"
   check_opts
   echo_opts
   check_env
   configure_env

   if [ $ANALYSIS == "html" ]; then
      html
   elif [ $ANALYSIS == "trimmed_kmer_analysis" ]; then
      trimmed_kmer_analysis 
   elif [ $ANALYSIS == "clientreport" ]; then
      clientreport
   elif [ $ANALYSIS == "warehouse" ]; then
      warehouse
      if [ $return_code != 0 ]; then
         exit $return_code
      fi
   else
      get_targets
      if [ $DRY_RUN != "no" ]; then
         fake
      else
         run
         if [ $? == 0 ] ; then
            clean
            echo "* done clean *"  # mainly to yield zero exit code
         else
            echo "error state from  run - skipping html page generation and clean-up"
            exit 1
         fi
      fi
   fi
}


set -x
main "$@"
set +x
