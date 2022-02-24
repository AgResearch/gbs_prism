#!/usr/bin/env python
from __future__ import print_function
#########################################################################
# summarise SNP call rates in a VCF file like this: 
# in a VCF for N individuals across  S SNPS 
# "information efficiency" = (Sum [i = 1 to S] C(i) ) / ( N x S) 
#(where C(i) = count of how many samples in which you called SNP i ) 
#########################################################################
import sys
import gzip
import re
import itertools
import argparse
import os 

def info_from_vcf(filename):
    """
    for each record (i.e. SNP locus) in a VCF , count how many samples the SNP is
    called in, how many missing, and return (called count, missing count).
    """
    header=("#CHROM","POS","ID","REF","ALT","QUAL","FILTER","INFO","FORMAT")
    with open(filename,"r") as vcf:
        # example /bifo/scratch/gseq_processing/gbs/210324_D00390_0613_BCD418ANXX/SQ1572.all.deer.PstI/KGD/GHW05.vcf
        # skip ## records
        # header record looks like #CHROM  POS     ID      REF     ALT     QUAL    FILTER  INFO    FORMAT
        # data records look like
        # TP3     1       TP3     C       G       .       .       .       GT:GP:GL:AD     ./.:0.8289,0.1631,0.008:0,0,0:0,0
        for record in vcf:
            if record.startswith("##"):
                continue
            if record.startswith("#"):
                fields=re.split("\t",record.strip())
                if tuple(fields[0:len(header)]) != header:
                    print("unexpected header start: %s"%str( fields[0:len(header)] ))
                    sys.exit(1)
                continue
            fields = re.split("\t",record.strip())
            information = 0
            missing = 0
            #print(fields[0:len(header)])
            for i_genotype in range(len(header),len(fields)):
                genotype = fields[i_genotype][0:3]
                if genotype == "./.":
                    missing += 1
                elif genotype == "0/1":
                    information +=1
                elif genotype == "1/0":
                    information += 1
                elif genotype == "0/0":
                    information += 1
                elif genotype == "1/1":
                    information += 1
                else:
                    print("unexpected genotpye %s in %s"%(genotype, str(fields[0:len(header)])))
                    sys.exit(1)
                    
            if missing + information != len(fields) - len(header):
                print("unexpected genotpye counts in %s : total = %d, expected %d"%(str(fields[0:len(header)]), missing + information, len(fields) - len(header)))
                sys.exit(1)

            yield (information, missing)

def get_options(): 
    description = """
    """
    long_description = """

examples :

python snp_info_from_vcf.py /bifo/scratch/gseq_processing/gbs/210324_D00390_0613_BCD418ANXX/SQ1572.all.deer.PstI/KGD/GHW05.vcf /dataset/gseq_processing/scratch/gbs/210324_D00390_0613_BCD418ANXX/SQ2965.all.PstI-MspI.PstI-MspI/KGD/GHW05.vcf


    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filenames', type=str, nargs='*',help='space-separated list of files to summarise ')
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
    
        info_gen = info_from_vcf(filename)
        snp_count = 0
        sample_count = None
        total_information = 0
        for (information , missing) in info_gen:
            if sample_count is None:
                sample_count = information + missing
            total_information += information
            snp_count += 1

        if args["verbose"]:
            print("filename=%s, total information = %d, snp-count=%d , sample_count=%d, information efficiency = %9.2f"%(filename,total_information, snp_count, sample_count, total_information / (1.0 * sample_count * snp_count)))
        else:
            print("efficiency = %9.2f"%(total_information / (1.0 * sample_count * snp_count)))
            
            
            
            
    return 0

if __name__=='__main__':
    sys.exit(main())    

    

        

