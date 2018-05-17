#!/bin/sh

export SEQ_PRISMS_BIN=/dataset/hiseq/active/bin/gbs_prism/seq_prisms
OUT_DIR=/dataset/hiseq/scratch/postprocessing/gbs/weevils

function setup() {
   mkdir -p $OUT_DIR
}

function get_sample_info() {
echo "
select distinct species, gbs_cohort from 
gbskeyfilefact where lower(species) like '%weevil%';

agrbrdf-> gbskeyfilefact where lower(species) like '%weevil%';
        species
-----------------------
 Weevil
 Argentine_stem_weevil
agrbrdf=> select distinct species, gbs_cohort,flowcell,enzyme  from
gbskeyfilefact where lower(species) like '%weevil%';
        species        | gbs_cohort | flowcell  |   enzyme
-----------------------+------------+-----------+------------
 Weevil                | MspI-ApeKI | C9MYUANXX | MspI-ApeKI
 Argentine_stem_weevil | MspI-ApeKI | CBG3AANXX | MspI-ApeKI
 Weevil                | MspI-ApeKI | CA95UANXX | MspI-ApeKI
 Weevil                | MspI-ApeKI | C9NAGANXX | MspI-ApeKI
 Weevil                | MspI-ApeKI | CA81DANXX | MspI-ApeKI
 Argentine_stem_weevil | PstI       | C6JRFANXX | PstI
 Weevil                | MspI-ApeKI | C8F1FANXX | MspI-ApeKI
(7 rows)

agrbrdf=> update gbskeyfilefact set gbs_cohort = 'weevil' where  lower(species) like '%weevil%'
agrbrdf-> ;
UPDATE 1199
agrbrdf=>

   module load DECONVQCenv
   listDBKeyfile.sh -g weevil -t gbsx_qc

   intrepid$  listDBKeyfile.sh -g weevil -t files
lane    fastq_link
1       /dataset/hiseq/active/fastq-link-farm/SQ0260_C8F1FANXX_s_1_fastq.txt.gz
1       /dataset/hiseq/active/fastq-link-farm/SQ0262_C9MYUANXX_s_1_fastq.txt.gz
2       /dataset/hiseq/active/fastq-link-farm/SQ0261_C8F1FANXX_s_2_fastq.txt.gz
2       /dataset/hiseq/active/fastq-link-farm/SQ0257_C9NAGANXX_s_2_fastq.txt.gz
3       /dataset/hiseq/active/fastq-link-farm/SQ0591_CBG3AANXX_s_3_fastq.txt.gz
4       /dataset/hiseq/active/fastq-link-farm/SQ0592_CBG3AANXX_s_4_fastq.txt.gz
5       /dataset/hiseq/active/fastq-link-farm/SQ0593_CBG3AANXX_s_5_fastq.txt.gz
6       /dataset/hiseq/active/fastq-link-farm/SQ0594_CBG3AANXX_s_6_fastq.txt.gz
7       /dataset/hiseq/active/fastq-link-farm/SQ2532_C6JRFANXX_s_7_fastq.txt.gz
7       /dataset/hiseq/active/fastq-link-farm/SQ0458_CA95UANXX_s_7_fastq.txt.gz
7       /dataset/hiseq/active/fastq-link-farm/SQ0595_CBG3AANXX_s_7_fastq.txt.gz
8       /dataset/hiseq/active/fastq-link-farm/SQ0459_CA95UANXX_s_8_fastq.txt.gz
8       /dataset/hiseq/active/fastq-link-farm/SQ0317_CA81DANXX_s_8_fastq.txt.gz
"
   listDBKeyfile.sh -g weevil -t gbsx_qc -s SQ0260 > $OUT_DIR/SQ0260.samples.txt
   listDBKeyfile.sh -g weevil -t files -s SQ0260 > $OUT_DIR/SQ0260.files.txt

   listDBKeyfile.sh -g weevil -t gbsx_qc -e PstI 
   listDBKeyfile.sh -g weevil -t files -e PstI 
intrepid$ listDBKeyfile.sh -g weevil -t files -e PstI
lane    fastq_link
7       /dataset/hiseq/active/fastq-link-farm/SQ2532_C6JRFANXX_s_7_fastq.txt.gz
   listDBKeyfile.sh -g weevil -t gbsx_qc -e PstI -s SQ2532
   listDBKeyfile.sh -g weevil -e PstI -s SQ2532

PS – my understanding not very good – just based on what crashes and what doesnt, has been that 
UNEAK supports ‘MspI-ApeKI’ , but not ‘ApeKI- MspI’ so that , I have some code in the 
keyfile import which translates ‘ApeKI- MspI’  ‘MspI-ApeKI’ 

e.g. these guys \\isamba\dataset\hiseq\scratch\postprocessing\161012_D00390_0269_BC8F1FANXX.gbs\SQ0260.processed_sample\uneak are done
as MspI-ApeKI , though they came through originally http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=SQ0260&context=default  as 
ApeKI- MspI 

on the other hand , GBSX does not support this via suck-it-and-don’t-see  – but I’ll try it with PstI-MspI


From: Brauning, Rudiger 
Subject: RE: gbsx enzyme spec for MspI-ApeKI ? 

Hi Alan,

Not a direct answer to your question, but related…

MspI-ApeKI is not supported by UNEAK. Simply run with ApeKI only. We are using Y adapters that ensure our good reads always start with the first enzyme.
In the case of MspI-ApeKI the first enzyme is ApeKI. MspI is the second enzyme and therefore we can use the same adapters as in the PstI-MspI case.

Cheers,
Rudiger

Quick clarification:

If MspI-ApeKI is supported, but not ApeKI-MspI, then using MspI-ApeKI instead of ApeKI-MspI is the best.
If the double digest is not supported then using just ApeKI is suggested.
Do not replace the ApeKI- MspI with PstI-MspI.

Cheers,
Rudiger



   
}

function run() {
   # possible enzyme issue for this one 
   OUT_DIR=/dataset/hiseq/scratch/postprocessing/gbs/weevils_gbsx
   #./demultiplex_prism.sh -x gbsx -l /dataset/hiseq/active/bin/gbs_prism/SQ0260.samples.txt -O $OUT_DIR /dataset/hiseq/active/bin/gbs_prism/test/SQ0260_test.fastq
   #./demultiplex_prism.sh -x gbsx -l /dataset/hiseq/active/bin/gbs_prism/test/SQ2532.samples.txt -O $OUT_DIR /dataset/hiseq/active/fastq-link-farm/SQ2532_C6JRFANXX_s_7_fastq.txt.gz
   #./demultiplex_prism.sh -x gbsx -l /dataset/hiseq/active/bin/gbs_prism/test/SQ2532.samples.txt -O $OUT_DIR /dataset/hiseq/active/bin/gbs_prism/test/SQ2532_sampled.fastq.gz

   OUT_DIR=/dataset/hiseq/scratch/postprocessing/gbs/weevils_tassel3
   ./demultiplex_prism.sh -x tassel3_qc -e PstI -l /dataset/hiseq/active/bin/gbs_prism/test/SQ2532.txt -O $OUT_DIR /dataset/hiseq/active/bin/gbs_prism/test/SQ2532_C6JRFANXX_s_7_fastq.txt.gz
}


#setup
#get_sample_info
run
   
