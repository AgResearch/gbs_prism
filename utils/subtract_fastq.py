#!/bin/env pypy
from __future__ import print_function
import itertools
import sys
import argparse
import re
from data_prism import  get_text_stream

# simple fastq iter
def fastq_iter(filename):
    record_iter = (record.strip() for record in get_text_stream(filename) if len(record.strip()) > 0)
    numbered_record_iter=itertools.izip(itertools.cycle(("name","seq","seq","seq")), record_iter)
    seq_group_iter = itertools.groupby(numbered_record_iter, lambda record:record[0])
    name = None
    for (group, records) in seq_group_iter:
        if group == "name":
            name=records.next()[1]
        else:
            yield (re.split("\s+",name)[0][1:], itertools.chain((name,),(record[1] for record in records)))

def run(options):
    seqs = fastq_iter(options["seqfile"][0])
    subtractions = fastq_iter(options["subtractfile"])

    # for each subtract seq
    subtract = subtractions.next()

    for seq in seqs:
        # if subtract is None then output
        if subtract is None:
            print("\n".join(seq[1]))

        # else if seq is not subtract then output
        elif seq[0] != subtract[0]:
            print("\n".join(seq[1]))
            
        else:
            try:
                subtract = subtractions.next()
            except StopIteration:
                subtract = None

def get_options():
    description = """
    """

    long_description = """
    Example :

./subtract_fastq.py -s  /dataset/GBS_Tcirc/ztmp/SQ1014_analysis2/repeats/SQ1014_CDT5UANXX_s_3_fastq.txt.repeats /dataset/GBS_Tcirc/ztmp/SQ1014_analysis2/filtered/SQ1014_CDT5UANXX_s_3_fastq.txt


    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('seqfile', type=str, nargs=1,metavar="seqfile", help='file to process')
    parser.add_argument('-s', '--subtractfile', dest='subtractfile', type=str, metavar='fastq input file to subtract', default = None, required=True , help="specify a fastq file to be subtracted")
    
    args = vars(parser.parse_args())

    return args


def main():

    args=get_options()
    run(args)


if __name__ == "__main__":
   main()

