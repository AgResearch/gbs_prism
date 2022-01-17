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

***********************************************************************************************
* This is the legacy interface for extracting keyfiles. It has been replaced by gquery        *
*                                                                                             *
* To see the gquery equivalent of any command using this interface, run your command with the *
* -n (dry run) option - e.g.                                                                  *
*                                                                                             *
* listDBKeyfile.sh -n -s SQ0566                                                               *                                                              *
*                                                                                             *
* To access a detailed explanation of how the extract was prepared (including the SQL code    *
* that was generated ) , include the --explain option - e.g.                                  *
*                                                                                             *
* listDBKeyfile.sh --explain -s SQ0566                                                        *
*                                                                                             *
* (this interface is now just a stub and calls gquery under the hood                          *
***********************************************************************************************

Examples : 

e.g.
listDBKeyfile.sh  -s SQ0566                  # extract everything for SQ0566, default tassel 3 format
listDBKeyfile.sh  -s SQ0566 -v 5             # extract everything for SQ0566, default tassel 5 format
listDBKeyfile.sh  -s SQ0566 -t gbsx          # extract everything for SQ0566, GBSX format (only include sample, barcode, enzyme)
listDBKeyfile.sh  -s SQ0566 -t qc            # internal primary key used instead of sampleid
listDBKeyfile.sh  -s SQ0566 -t unblind_script       # dump a sed script to patch qc_sampleid to lab sampleid. Save output to a file and then run as sed -f script_file raw_file > patched_file 
listDBKeyfile.sh  -s SQ0566 -t files         # extract distinct lane + fastq file name for SQ0566 (e.g. to help build GBSX command)
listDBKeyfile.sh  -s SQ1014 -t method         # extract distinct geno_method for SQ1014
listDBKeyfile.sh  -s SQ0566 -t bwa_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566
listDBKeyfile.sh  -s SQ0566 -t blast_index_paths  # extract distinct cohort + path to bwa index for cohort species for SQ0566
listDBKeyfile.sh  -s SQ0566 -t list_species  # extract distinct cohort + path to bwa index for cohort species for SQ0566
listDBKeyfile.sh  -g deer                    # extract everything that has gbs_cohort = deer (across all runs, not case sensitive e.g. will include DEER)
listDBKeyfile.sh  -m bee                     # extract everything that has species field deer (across all runs , not case sensitive e.g. will include BEE)
listDBKeyfile.sh  -m bee -t gbsx             # as above, GBSX format 
listDBKeyfile.sh  -g deer -e PstI            # extract everything that has gbs_cohort = deer , and enzyme = PstI (across all runs)
listDBKeyfile.sh  -t gbsx -g deer -e PstI    # as above, GBSX format 
listDBKeyfile.sh  -t files -g deer -e PstI   # as above, report lane + file
listDBKeyfile.sh  -m Argentine_stem_weevil -t missing_files   # report lane and flowcell for any samples where the fastq file is missing
listDBKeyfile.sh  -g deer  -f CA95UANXX      # all deer , but only in flowcell CA95UANXX
listDBKeyfile.sh  -f CA95UANXX               # extract everything on flowcell CA95UANXX
listDBKeyfile.sh  -s SQ1471 -q good      # all the samples flagged as good in SQ1471 
listDBKeyfile.sh -s SQ1471 -f CD5F7ANXX -e PstI -g PstI -q good 
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
    parser.add_argument('-n','--dry_run', dest='dry_run', action='store_const', default = False, const=True, help='dry run - just emit gquery command')
    parser.add_argument('-E','--explain', dest='explain', action='store_const', default = False, const=True, help='explain what was done')


    args = vars(parser.parse_args())

    return args


def call_gquery(options, base_predicate_string):

    predicate_string = base_predicate_string

    if options["enzyme"] is not None:
        enzyme_phrase = "enzyme=%(enzyme)s"%options
        predicate_string="%s;%s"%(predicate_string, enzyme_phrase)
    if options["qc_cohort"] is not None:
        qc_cohort_phrase = "qc_cohort=%(qc_cohort)s"%options
        predicate_string="%s;%s"%(predicate_string, qc_cohort_phrase)
    if options["sample"] is not None:
        args = ["gquery", "-t", "gbs_keyfile", "-b" , "library", "-p", predicate_string , options["sample"]]
        if options["gbs_cohort"] is not None:
            gbs_cohort_phrase = "gbs_cohort=%(gbs_cohort)s"%options
            predicate_string="%s;%s"%(predicate_string, gbs_cohort_phrase)
        if options["flowcell"] is not None:
            flowcell = "flowcell=%(flowcell)s"%options
            predicate_string="%s;%s"%(predicate_string, flowcell)        
    elif options["species_moniker"] is not None:
        args = ["gquery", "-t", "gbs_keyfile", "-b" , "gbs_taxname", "-p", predicate_string,  options["species_moniker"]]
    elif options["gbs_cohort"] is not None and options["flowcell"] is None:
        args = ["gquery", "-t", "gbs_keyfile", "-b" , "gbs_cohort", "-p", predicate_string,  options["gbs_cohort"]]
    elif options["flowcell"] is not None and options["gbs_cohort"] is None:
        args = ["gquery", "-t", "gbs_keyfile", "-b" , "flowcell", "-p", predicate_string,  options["flowcell"]]
    elif options["flowcell"] is not None and options["gbs_cohort"] is not None:
        flowcell_phrase = "flowcell=%(flowcell)s"%options
        predicate_string="%s;%s"%(base_predicate_string, flowcell_phrase)
        args = ["gquery", "-t", "gbs_keyfile", "-b" , "gbs_cohort", "-p", predicate_string,  options["gbs_cohort"]]        
    else:
        print("expected something more ! please specify what to extract")
        exit(1)


    if options["explain"]:
        args.insert(1,"--explain")

    if options["dry_run"]:
        # quote the predicate arg in this note
        p_index=1+args.index("-p")
        quoted_args =  [item for item in args]
        quoted_args[p_index] = "\"%s\""%args[p_index]
        
        print("""*** dry run ***
The equivalent gquery command would be:

%s

Notes:

* use gquery with the --explain option to get an explanation of exactly what was done, including underlying SQL code.
* for species with metadata in genophyle (e.g. aquaculture, ruminants, conservation species), you can add additional column
  names such as animalid,stud,uidtag,labid,breed to the above gquery command, to have these included in the keyfile.
* "gquery -h" will list additional examples of extracting data from the keyfile database using gquery 

"""%" ".join(quoted_args))
    else:
        try:
            proc = subprocess.call(args)
        except OSError,e:
            print("call_gquery failed with : %s"%e)
            raise e

def main():    
    options = get_options()


    if options["template"] in ("tassel", "qc", "gbsx", "gbsx_qc"):

        # extract keyfile. qc template uses the safe sampleid , qc_sampleid
        params = {
            "sample_phrase" : "sample"
        }

        if options["template"] in ("qc", "gbsx_qc"):
            params["sample_phrase"] = "qc_sampleid as sample"

        # extract may be in tassel 3 or 5 format                                           
        columns_phrase = "columns=flowcell,lane,barcode,%(sample_phrase)s,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link"
        if options["client_version"] == "5":
            columns_phrase = "columns=Flowcell,Lane,Barcode,%(sample_phrase)s,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link,FullSampleName"


        # gbs / gbsx template
        if options["template"] in ("gbsx", "gbsx_qc"):
            columns_phrase = "columns=%(sample_phrase)s,barcode,enzyme"
            
        columns_phrase=columns_phrase%params

        predicate_string="%s;distinct"%columns_phrase

        call_gquery(options, predicate_string)

    elif options["template"] == "unblind_script":

        predicate_string = "unblinding;columns=qc_sampleid,sample;noheading"
        call_gquery(options, predicate_string)

    elif options["template"] == "files":

        predicate_string = "columns=lane,fastq_link;distinct;noheading"
        call_gquery(options, predicate_string)

    elif options["template"] == "missing_files":

        predicate_string = "columns=flowcell,lane,fastq_link;fastq_link=* fastq_link is missing *;distinct;noheading"
        call_gquery(options, predicate_string)        

    elif options["template"] == "method":

        predicate_string = "columns=flowcell,lane,geno_method;distinct;noheading"
        call_gquery(options, predicate_string)

    elif options["template"] in ("bwa_index_paths","blast_index_paths"):

        if options["template"] == "bwa_index_paths":
            predicate_string = "columns=gbs_cohort,refgenome_bwa_indexes;distinct;noheading"
        else:
            predicate_string = "columns=gbs_cohort,refgenome_blast_indexes;distinct;noheading"
            
        call_gquery(options, predicate_string)

    elif options["template"] in ("list_species"):

        predicate_string = "columns=species;group;noheading"
        call_gquery(options, predicate_string)

    else:
        print("""
Sorry, the %(template)s option is no longer supported
"""%options)
        exit(1)
                
if __name__=='__main__':
    sys.exit(main())    

    

        

