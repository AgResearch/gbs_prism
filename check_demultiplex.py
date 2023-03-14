#!/usr/bin/env python
from __future__ import print_function
#########################################################################
# check log of FastqToTagCount step for tag count files written more than once   
# (can happen with custom keyfiles containing libraries from same flowcell,
# where barcode hopping has occurred )
#########################################################################
import sys
import gzip
import re
import itertools
import argparse
import os 

def check(filename):
    """
    for each record (i.e. SNP locus) in a VCF , count how many samples the SNP is
    called in, how many missing, and return (called count, missing count).
    """

    check_dict = {}
    fastq_count = 0
    with open(filename,"r") as demultlog:
        for record in demultlog:
            if record.startswith("Reading FASTQ file"):
                match=re.match("Reading FASTQ file: (\S+)$", record.strip()) 
                current_file = match.groups()[0]
                fastq_count += 1 
                continue

            match=re.search("^(\d+) tags will be output to (\S+)$",record.strip())

            if match != None:
                (tagcount, tagfile)=match.groups()

                if tagfile not in check_dict:
                    check_dict[tagfile] = [(current_file, tagcount)]
                else:
                    check_dict[tagfile].append(tuple((current_file, tagcount)))

    overwrites = [ tagfile for tagfile in check_dict if len(check_dict[tagfile]) > 1]

    print("%d fastq files were processed and %d tagfiles were written"%(fastq_count, len(check_dict)))

    if len(overwrites) > 0:
        print("%d tagfiles were written more than once:"%len(overwrites))
        print("listing overwritten tagfiles, fastq source and tag count written from each source")
        for tagfile in overwrites:
            print("%s was written %d times: \t %s"%(tagfile, len(check_dict[tagfile]), str(check_dict[tagfile])))
    else:
        print("(no tagfiles were written more than once)")


def get_options(): 
    description = """
    """
    long_description = """

examples :

./check_demultiplex.py /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/elk_red/PstI/sample_info.key.PstI.tassel3_qc.FastqToTagCount.stdout


    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filenames', type=str, nargs='*',help='space-separated list of files to check ')
    parser.add_argument('-v','--verbose', dest='verbose', action='store_const', default = False, const=True, help='request (context-sensitive) verbosity')
    args = vars(parser.parse_args())

    # check args
    for filepath in args["filenames"]:
        if not os.path.isfile(filepath):
            print("%s does not exist"%filepath)
            sys.exit(1)
 

    return args
            

def main():

    args=get_options()

    for filename in args["filenames"]:
        check(filename)
            
    return 0

if __name__=='__main__':
    sys.exit(main())    

    

        

