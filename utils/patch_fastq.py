#!/bin/env python
from __future__ import print_function
#########################################################################
# summarise and patch PstI site in fastq file 
#########################################################################
import argparse
import sys
import os
import re
import gzip 

BARCODE_LENGTH=10


def get_options():
    description = """
    """
    long_description = """

examples :

pypy patch_fastq.py -t analyse_psti -i /bifo/scratch/hiseq/postprocessing/illumina/novaseq/210915_A01439_0021_AHKTNTDRXY/SampleSheet/bclconvert/SQ1693_S4_L001_R1_001.fastq.gz


pypy patch_fastq.py -t patch_psti -i /bifo/scratch/hiseq/postprocessing/illumina/novaseq/210915_A01439_0021_AHKTNTDRXY/SampleSheet/bclconvert/SQ1693_S4_L001_R1_001.fastq.gz -o /bifo/scratch/hiseq/postprocessing/illumina/novaseq/210915_A01439_0021_AHKTNTDRXY/SampleSheet/bclconvert_edited/SQ1693_S4_L001_R1_001.fastq.gz TGCAA TGCAT TGAAA TGCAC


pypy patch_fastq.py -t patch_psti -i /bifo/scratch/hiseq/postprocessing/illumina/novaseq/210915_A01439_0021_AHKTNTDRXY/SampleSheet/bclconvert/SQ1693_S4_L001_R1_001.fastq.gz -o /bifo/scratch/hiseq/postprocessing/illumina/novaseq/210915_A01439_0021_AHKTNTDRXY/SampleSheet/bclconvert_edited/SQ1693_S4_L001_R1_001.fastq.gz


"""

    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('site_alleles', type=str, nargs='*',help='optional space-separated list of alleles to patch (if not supplied will work it out)')
    
    parser.add_argument('-t', '--task' , dest='task', required=False, type=str,
                        choices=["patch_psti", "analyse_psti"], help="what you want to get / do")
    parser.add_argument('-i','--input_file', dest='input_file', type=str, default=None, help='input file')
    parser.add_argument('-o','--output_file', dest='output_file', type=str, default=None, help='output file')
    parser.add_argument('-Q','--patch_quality', dest='patch_quality', action='store_const', default = False, const=True, help='dry run only')    
    
    args = vars(parser.parse_args())

    return args

def patch_psti(options):
    PSTI="TGCAG"

    if len(options["site_alleles"]) == 0:
        print("analysing file. . . ")
        site_alleles = analyse_psti(options)
    else:
        site_alleles = options["site_alleles"]
        

    print("running patch job to patch %s to %s"%(str(site_alleles), PSTI))

    record_count = 0
    with gzip.open(options["input_file"],"r") as input_file:
        with gzip.open(options["output_file"],"wb") as output_file:
            fastq_subrecord_number=0  # used to remember where in fastq logical record we are (e.g. to edit quality record)
            for record in input_file:
                #print(record,end="")
                # if we have patched the sequence, patch the quality
                if fastq_subrecord_number > 0:
                    fastq_subrecord_number += 1
                    if fastq_subrecord_number == 4: # quality record
                        # patch the quality - this is done by recycling the fastq quality value for the
                        # first base after the barcode, and using this for all of the PstI site
                        print(record[0:BARCODE_LENGTH]+len(PSTI)*record[BARCODE_LENGTH]+record[BARCODE_LENGTH+len(PSTI):],end="",file=output_file)
                        fastq_subrecord_number = 0
                    else:
                        print(record,end="",file=output_file)
                else:    
                    if re.match("[NACGT]{%s}"%BARCODE_LENGTH, record) is not None:
                        allele =  record[BARCODE_LENGTH:BARCODE_LENGTH+len(PSTI)]
                        if allele in site_alleles:
                            print(record[0:BARCODE_LENGTH]+PSTI+record[BARCODE_LENGTH+len(PSTI):],end="",file=output_file)
                            fastq_subrecord_number = 2
                        else:
                            print(record,end="",file=output_file)
                    else:
                        print(record,end="",file=output_file)

                record_count += 1
                #if record_count > 1000000:
                #    break


def analyse_psti(options):
    PSTI="TGCAG"
    RECORDS_TO_ANALYSE=15000000

    record_count = 0
    allele_dict = {}
    with gzip.open(options["input_file"],"r") as input_file:
        for record in input_file:
            #print(record,end="")
            if re.match("[NACGT]{%s}"%BARCODE_LENGTH, record) is not None:
                record_count += 1
                allele = record[BARCODE_LENGTH:BARCODE_LENGTH+len(PSTI)]
                #print(allele)
                allele_dict[allele] = 1+ allele_dict.setdefault(allele, 0) 
            if record_count > RECORDS_TO_ANALYSE:
                break

    alleles_to_patch = []

    if PSTI not in allele_dict:
        print("PstI site not found in the first %d seqs  - unable to do anything more !"%RECORDS_TO_ANALYSE)

    for allele in allele_dict:
        if allele[0:2] == "TG" and allele != PSTI and allele_dict[allele]/(1.0 * allele_dict[PSTI]) >= 0.05:
            alleles_to_patch.append(allele)
            print("will patch %s to %s ( count was %5.2f %% of PstI site count )"%(allele, PSTI, 100.0*allele_dict[allele]/(1.0 * allele_dict[PSTI])))

    print("allele counts : ")
    for allele in sorted(allele_dict.keys(), cmp=lambda x,y:cmp(allele_dict[x], allele_dict[y]), reverse=True):
        print("%s\t%d"%(allele, allele_dict[allele]))
 
    return alleles_to_patch
            
         
def main():    
    options = get_options()

    if options["task"] == "patch_psti":
        patch_psti(options)
    elif options["task"] == "analyse_psti":
        analyse_psti(options)
        

    #print(options) 

    
            
if __name__=='__main__':
    sys.exit(main())    

    

        

