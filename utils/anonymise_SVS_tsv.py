#!/bin/env python
from __future__ import print_function
import argparse
import time
import sys
import os
import re
import itertools
import random 



def get_options(): 
    description = """
Anonymise an export file from SVS (to be supplied to Golden Helix to help debug 
a problem running PCA on this data)

example:

./anonymise_SVS_tsv.py /localdata/SVS/clarkej/Jordan_repro/merged_pheno_geno.tsv

    """
    long_description = """
    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('items', type=str, nargs='*',help='space-separated list of items to process (e.g. names of samples, subjects, libraries , sequence files, taxnames, taxids etc.')

    
    parser.add_argument('-t', '--task' , dest='task', required=False, type=str,
                        choices=[], help="what you want to get / do")
    
    args = vars(parser.parse_args())
             
    return args


def get_anon_ids(filename):
    """
read through the file and compile anonymisation tables for herd, yob and tag

File format is like this :
    
    
    Herd:YOB:Tag    herd    byr     sex     aod     bdev    hy      hysx    cgW12   cgCDOY  rflk    ryr     rcg     mage    W12     MWT     CDOY    Herd:YOB:Tag
    CM008008.1_172315       CM008008.1_870470       CM008008.1_870556       CM008008.1_907211       CM008008.1_907380       CM008008.1_1238085      CM008008.1_1419709      CM008008.1_1535811
    CM008008.1_1567605      CM008008.1_1699595....
    
    8051:1996:205Y  8051    1996    1       4       0       80511996        805119961       805196000000000 0       0       1997    0       1       116.8   0       0       8051:1996:205Y  A_B     ?_?
    ?_?     ?_?     A_A     B_B     A_B     B_B     ?_?     ?_?     B_B     B_B     A_B     A_B     A_B     A_A     ?_?     A_A     A_A     B_B     B_B     B_B     B_B     B_B     ?_?     B_B
    B_B     B_B     A_A     ?_?     A_A     A_B     A_A     A_A     B_B     A_B     A_A     B_B     A_A     A_A     A_B     ?_?     A_A     B_B     A_B     A_A     B_B     B_B     B_B     A_A
    B_B     B_B     B_B     A_A     B_B     A_A     B_B     A_A     A_B     ?_?     ?_?     A_A     B_ ....
    
    """
    id_index = 17 # second copy of ID here
    genotype_index = 18  # genotypes start from here
    herd_index=1
    yob_index=2

    herds = set()
    yobs=set()
    tags=set()

    count = 0
    with open(filename,"r") as f:
        for record in f:
            count += 1
            #if count > 50:
            #    break
            fields = re.split("\t", record)
            if fields[0] != fields[17] and count > 1:
                print("oops1 ! : %s"%str(fields))
                break
            (herd, yob, tag) = re.split("\:",fields[0])

            if herd != fields[herd_index] and count > 1:
                print("oops2 ! : %s"%str(fields))
                break

            if yob != fields[yob_index] and count > 1:
                print("oops3 ! : %s"%str(fields))
                break
                
            herds.add(herd)  # like 
            yobs.add(yob)
            tags.add(tag)

    # make a random set of herds same length as herds - like
    # 8002
    # 8005
    rand_herds = set()
    while len(rand_herds) < len(herds):
        rand_herds.add(random.randint(1000,9999))
    rand_herds_table = dict(zip(herds, rand_herds))  # lookup table to randomise
            

    # make a random set of yobs same length as yobs
    # 1998
    # 1999
    # 2000
    rand_yobs = set()
    while len(rand_yobs) < len(yobs):
        rand_yobs.add(random.randint(1994,2019))
    rand_yobs_table = dict(zip(yobs,rand_yobs))  # lookup table to randomise
        
    # make a random set of tags same length as tags like
    # YE17550
    # YE17551
    # YE17552
    rand_tags = set()
    while len(rand_tags) < len(tags):
        rand_tags.add("TAG%04d"%random.randint(100,50000))
    rand_tags_table = dict(zip(tags, rand_tags))  # lookup table to randomise
    

    return (rand_herds_table, rand_yobs_table, rand_tags_table)

def anonymise(filename,rand_herds_table, rand_yobs_table, rand_tags_table):
    """
    read through the file, look up herd, yob and tag in the anonymise tables,
    and output 
    """
    id_index = 17 # second copy of ID here
    genotype_index = 18  # genotypes start from here
    herd_index=1
    yob_index=2
    ryr_index=11
    

    count = 0
    with open(filename,"r") as f:
        for record in f:
            count += 1
            #if count > 50:
            #    break
            fields = re.split("\t", record.strip())

            if count > 1:
                (herd, yob, tag) = re.split("\:",fields[0])
                fields[0] = "%s:%s:%s"%(rand_herds_table[herd],rand_yobs_table[yob],rand_tags_table[tag])
                fields[17] = fields[0]
                fields[herd_index]=str(rand_herds_table[herd])
                fields[yob_index]=str(rand_yobs_table[yob])
                fields[ryr_index]=str(1+int(rand_yobs_table[yob]))

            print("\t".join(fields))

def main():    
    options = get_options()

    (rand_herds_table, rand_yobs_table, rand_tags_table) = get_anon_ids(options["items"][0])

    anonymise(options["items"][0],rand_herds_table, rand_yobs_table, rand_tags_table)
        
    
if __name__=='__main__':
    sys.exit(main())    

