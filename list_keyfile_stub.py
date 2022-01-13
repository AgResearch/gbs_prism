#!/bin/env python
from __future__ import print_function
#########################################################################
# a stub to delegate keyfile queries to gquery
#########################################################################
import argparse
import time
import platform
import sys
import os
import re
import itertools
import subprocess


def get_options():
    description = """
    """
    long_description = """

*********************************************************
* This is the legacy interface for extracting keyfiles  *
*                                                       *
* If possible please using gquery to extract keyfiles   *
* (gquery -h for examples). This adds features such as  *
* extracting multiple libraries, and integrates metadata*
* from the genophyle database into the keyfile          *
*                                                       *
* (this interface now calls gquery under the hood       *
*********************************************************

Examples : 

e.g.
list_keyfile.sh  -s SQ0566                  # extract everything for SQ0566, default tassel 3 format
list_keyfile.sh  -s SQ0566 -v 5             # extract everything for SQ0566, default tassel 5 format
list_keyfile.sh  -s SQ0566 -v 5 -t all      # extract everything for SQ0566, extended tassel 5 format (also include subject name)
list_keyfile.sh  -s SQ0566 -t gbsx          # extract everything for SQ0566, GBSX format (only include sample, barcode, enzyme)
list_keyfile.sh  -s SQ0566 -t qc            # internal primary key used instead of sampleid
list_keyfile.sh  -s SQ0566 -t unblind       # dump a mapping between qc_sampleid and lab sampleid 
list_keyfile.sh  -s SQ0566 -t unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid. Save output to a file and then run as sed -f script_file raw_file > patched_file 
list_keyfile.sh  -s SQ1131 -t historical_unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid - including historical qc_sampleids (e.g. if keyfile was reloaded) . Save output to a file and then run as sed -f script_file raw_file > patched_file 
list_keyfile.sh  -s SQ0566 -t files         # extract distinct lane + fastq file name for SQ0566 (e.g. to help build GBSX command)
list_keyfile.sh  -s SQ1014 -t method         # extract distinct geno_method for SQ1014
list_keyfile.sh  -s SQ0566 -t bwa_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566
list_keyfile.sh  -s SQ0566 -t blast_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566
list_keyfile.sh  -s SQ0566 -t list_species  # extract distinct cohort + path to bwa index for cohort species for SQ0566
list_keyfile.sh  -g deer                    # extract everything that has gbs_cohort = deer (across all runs, not case sensitive e.g. will include DEER)
list_keyfile.sh  -m bee                     # extract everything that has species field deer (across all runs , not case sensitive e.g. will include BEE)
list_keyfile.sh  -m goat -x                     # extract everything that has species field goat , that has been excluded 
list_keyfile.sh  -m bee -t gbsx             # as above, GBSX format 
list_keyfile.sh  -g deer -e PstI            # extract everything that has gbs_cohort = deer , and enzyme = PstI (across all runs)
list_keyfile.sh  -t gbsx -g deer -e PstI    # as above, GBSX format 
list_keyfile.sh  -t files -g deer -e PstI   # as above, report lane + file
list_keyfile.sh  -t missing_files -g deer -e PstI   # as above, but report lane and any samples where the fastq file is missing
list_keyfile.sh  -g deer  -f CA95UANXX      # all deer , but only in flowcell CA95UANXX
list_keyfile.sh  -f CA95UANXX               # extract everything on flowcell CA95UANXX
list_keyfile.sh  -s SQ2701 -q uncontaminated      # all the samples flagged as uncontaminated in SQ2701 
list_keyfile.sh -s SQ2701 -f CC5V9ANXX -e ApeKI -g Ryegrass -q contaminated_xanthomonas_translucens 
list_keyfile.sh                             # don't be greedy ! (extract entire keyfile database, ~ 200,000 records)
"""



    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--client_version' , dest='client_version', required=False, default="3",type=str,choices=["5", "3"], help="tassel version this keyfile is for")
    parser.add_argument('-t', '--template' , dest='template', required=False, type=str,
                        choices=["tassel", "qc","unblind","unblind_script","historical_unblind_script","files","method","bwa_index_paths","blast_index_paths","list_species","gbsx","missing_files"], \
                        default="tassel", help="what you want to get")
    parser.add_argument('-s','--sample', dest='sample', type=str, default=None, help='sample e.g. SQ0566')
    parser.add_argument('-g','--gbs_cohort', dest='gbs_cohort', type=str, default=None, help='gbs cohort')
    parser.add_argument('-j','--job_name', dest='job_name', type=str, default=None, help='job name (will be used to name output folder if applicable)')        
    parser.add_argument('-f','--flowcell', dest='flowcell', type=str, default=None, help='flowcell')
    parser.add_argument('-m','--species_moniker', dest='species_moniker', type=str, default=None, help='species moniker')
    parser.add_argument('-T','--taxid', dest='taxid', type=str, default=None, help='taxid')   
    parser.add_argument('-e','--enzyme', dest='enzyme', type=str, default=None, help='enzyme')    
    parser.add_argument('-x','--excluded', dest='excluded', action='store_const', default = False, const=True, help='also extract excluded records')
    parser.add_argument('-q','--qc_cohort', dest='qc_cohort', type=str, default=None, help='qc_cohort')

    args = vars(parser.parse_args())

    return args


def call_gquery(args):
    try:
        proc = subprocess.call(args)
    except OSError,e:
        print("call_gquery failed with : %s"%e)
        raise e


def parse_SQ(arg):
    m=re.search("(\d+)", arg)
    if m is not None:
        return m.groups()[0]
    

    
def main():    
    options = get_options()


    if options["template"] in ("tassel"):
        if options["sample"] is not None:
            call_gquery(["gquery", "-t", "gbs_keyfile", "-b" , "library", "-p", "columns=flowcell,lane,barcode,sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link,animalid,stud,uidtag,labid,breed" , parse_SQ(options["sample"])])            
        elif options["species_moniker"] is not None:
            call_gquery(["gquery", "-t", "gbs_keyfile", "-b" , "taxname", "-p", "columns=flowcell,lane,barcode,sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link,animalid,stud,uidtag,labid,breed",  options["species_moniker"]])            
        else:
            print("expected something more ! please specify what to extract")
            exit(1)
    

                
if __name__=='__main__':
    sys.exit(main())    

    

        

