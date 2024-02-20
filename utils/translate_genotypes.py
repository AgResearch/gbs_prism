#!/bin/env pypy
from __future__ import print_function
import itertools
import sys
import argparse
import re
from data_prism import  get_text_stream


global summary_table, translation_table

summary_table = {}

# generate translation table 
alleles = "ABCDEFGHIJKLMNOP-"
homozygotes = list(itertools.izip_longest(alleles,alleles))
heterozygotes=list (itertools.ifilterfalse(lambda item:item[0]>=item[1] or '-' in item , itertools.product(alleles,alleles)))
translation_table = dict(zip((item[0] for item in homozygotes), ("%s/%s"%item for item in homozygotes)))
translation_table.update( dict(zip(("%s%s"%item for item in heterozygotes), ("%s/%s"%item for item in heterozygotes)))  ) 


def update_summary(value):
    count=1+summary_table.setdefault(value, 0)
    summary_table[value] = count
    
def translated_iter(options):
    (HEADER,HEADING,DATA)=(0,1,2)
    state=HEADER
    """ input is like this :

!Haplotag_FileType_HTGenos
!Haplotag_File_Version_3
# File creation date: 2020-03-11 12:49
# Haplotag version: 2016-Oct-5
# Website: http://haplotag.aowc.ca
# Copyright: Nick Tinker, in right of Canada.
# This file was created by Haplotag project: Ryegrass_PstI_MspI
# Do not edit headers that begin with an exclamation mark: they are required by Haplotag.
# Comments beginning with the hash tag (#) can be added or edited.
# Data is expected to follow immediately after "!begin"
# Multi-allele (local haplotype) data called by Haplotag
!begin
Progeny F2LP13020-01_CDT5MANXX_8_2847_X4.cnt    F2LP13020-02_CDT5MANXX_8_2847_X4.cnt    F2LP13020-03_CDT5MANXX_8_2847_X4.cnt    F2LP13020-05_CDT5MANXX_8_2847_X4.cnt    F2LP13020-06_CDT5MANX
X_8_2847_X4.cnt F2LP13020-07_CDT5MANXX_8_2847_X4.cnt    F2LP13020-08_CDT5MANXX_8_2847_X4.cnt    F2LP13020-09_CDT5MANXX_8_2847_X4.cnt    F2LP13020-10_CDT5MANXX_8_2847_X4.cnt    F2LP13020-11_
CDT5MANXX_8_2847_X4.cnt F2LP13020-12_CDT5MANXX_8_2847_X4.cnt    F2LP13020-13_CDT5MANXX_8_2847_X4.cnt    F2LP13020-14_CDT5MANXX_8_2847_X4.cnt    F2LP13020-15_CDT5MANXX_8_2847_X4.cnt    F2LP1
3020-16_CDT5MANXX_8_2847_X4.cnt F2LP13020-17_CDT5MANXX_8_2847_X4.cnt    F2LP13020-18_CDT5MANXX_8_2847_X4.cnt    F2LP13020-19_CDT5MANXX_8_2847_X4.cnt    F2LP13020-20_CDT5MANXX_8_2847_X4.cntF2LP13020-22_CDT5MANXX_8_2847_X4.cnt     F2LP13020-23_CDT5MANXX_8_2847_X4.cnt    F2LP13020-24_CDT5MANXX_8_2847_X4.cnt    F2LP13020-25_CDT5MANXX_8_2847_X4.cnt    F2LP13020-26_CDT5MANXX_8_2847
_X4.cnt F2LP13020-27_CDT5MANXX_8_2847_X4.cnt    F2LP13020-28_CDT5MANXX_8_2847_X4.cnt    F2LP13020-29_CDT5MANXX_8_2847_X4.cnt    F2LP13020-30_CDT5MANXX_8_2847_X4.cnt    F2LP13020-31_CDT5MANX
X_8_2847_X4.cnt F2LP13020-32_CDT5MANXX_8_2847_X4.cnt    F2LP13020-33_CDT5MANXX_8_2847_X4.cnt    F2LP13020-34_CDT5MANXX_8_2847_X4.cnt    F2LP13020-35_CDT5MANXX_8_2847_X4.cnt    F2LP13020-36_
CDT5MANXX_8_2847_X4.cnt F2LP13020-37_CDT5MANXX_8_2847_X4.cnt    F2LP13020-38_CDT5MANXX_8_2847_X4.cnt    F2LP13020-39_CDT5MANXX_8_2847_X4.cnt    F2LP13020-40_CDT5MANXX_8_2847_X4.cnt    F2LP1
3020-41_CDT5MANXX_8_2847_X4.cnt F2LP13020-42_CDT5MANXX_8_2847_X4.cnt    F2LP13020-43_CDT5MANXX_8_2847_X4.cnt    F2LP13020-44_CDT5MANXX_8_2847_X4.cnt    F2LP13020-45_CDT5MANXX_8_2847_X4.cntF2LP13020-46_CDT5MANXX_8_2847_X4.cnt     F2LP13020-47_CDT5MANXX_8_2847_X4.cnt    F2LP13020-48_CDT5MANXX_8_2847_X4.cnt    F2LP13020-49_CDT5MANXX_8_2847_X4.cnt    F2LP13020-50_CDT5MANXX_8_2847
_X4.cnt F2LP13020-51_CDT5MANXX_8_28 etc etc
HC4.1   -       -       B       -       -       -       -       -       -       -       -       -       -       -
-       -       B       -       -       -       -       -       -   -B       -       -       -       A       -       -       -       -       -       A       -       A       -       -       -       -       -       -       B       -       AB      -       -   -B       -       -       B       B       -       B       -       -       -       -       B       -       -       -       -       -       B       -       -       B       -       -       B   --       A       -       B       -       -    
"""
    record_iter = (record.strip() for record in get_text_stream(options["file_name"][0]))
    for record in record_iter:
        if state == HEADER:
            if re.match(options["data_begins_with"], record):
                state = HEADING
            yield record
        elif state == HEADING:
            record_length = len(re.split("\s+", record))
            state = DATA
            yield record
        else:
            fields=re.split("\s+", record)
            update_summary("record_count")
            if len(fields) != record_length:
                print("*** warning at record %d: record length %d does not match length of heading %d"%(summary_table["record_count"], len(fields), record_length))
            map(update_summary, fields[1:])
            yield "\t".join(map(lambda x: translation_table.get(x,x), fields))
  

def get_options():
    description = """
    """

    long_description = """

Example: In the original dataset, it has A, B, C, AB, CE, … stands for different possible
combination of genotypes/haplotypes, where A, B, C etc.. stands for different allele. The tricky bits here:

It doesn’t have the full form of diploid genotype, i.e. AA. Instead, it puts A or B etc. alone.;
– represents missingness, again, it fails to accommodate the diploid format, such as -/- like we normally see in the vcf files;
Also, the heterozygous genotype, which should be written in the form, e.g., A/B, is written as AB.
Can you please help to suggest a way to reformat this file into a more approachable form? The data file I’m referring to is

/dataset/SRP102976/active/PstI_MspI/UNEAK/Haplotag/output/HTGenos.txt

    Example :

./translate_genotypes.py  -T /dataset/SRP102976/active/PstI_MspI/UNEAK/Haplotag/output/HTGenos_translated.txt /dataset/SRP102976/active/PstI_MspI/UNEAK/Haplotag/output/HTGenos.txt > /dataset/SRP102976/active/PstI_MspI/UNEAK/Haplotag/output/HTGenos_translated.log

    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file_name', type=str, nargs=1,metavar="filename", help='result file to process')
    parser.add_argument('-i', '--in_format' , dest='in_format', type=str, default = 'default',  choices=["default"], help="input format")
    parser.add_argument('-o', '--out_format' , dest='out_format', type=str, default = 'default',  choices=["default"], help="output format")
    parser.add_argument('-d', '--data_begins_with' , dest='data_begins_with', type=str, default = '^\\!begin', help="regexp which matches beginning (i.e. at next record)of data")
    parser.add_argument('-T', '--out_filename' , dest='out_filename', type=str, required=True , help="output filename")


    args = vars(parser.parse_args())
        
    return args


def main():
    args=get_options()

    print("using the following translations:")
    for (key, value) in translation_table.items():
        print("%s  -->  %s"%(key,value))

    if args["in_format"] == "default" and args["out_format"] == "default":
        i=translated_iter(args)
    else:
        raise Exception("unsupported file format")

    with open(args["out_filename"],"w") as out_file:


        for record in i:
            print(record, file=out_file)
            
        print("the following raw genotype codes were encountered:")
        for (key, value) in summary_table.items():
            print("%s : %d"%(key,value))


        not_translated = [ key for key in summary_table.keys() if key not in translation_table.keys() and key not in ["record_count"]]
        if len(not_translated) > 0:
            print("*** warning : the following raw codes were not translated:")
            for key in not_translated:
                print("%s : %d"%(key,summary_table[key]))





if __name__ == "__main__":
   main()

