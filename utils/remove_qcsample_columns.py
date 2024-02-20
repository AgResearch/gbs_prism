#!/bin/env pypy
from __future__ import print_function
import itertools
import sys
import re


# from tab delimited summary, remove columns whose headings are blinded sampleid's
def cut_iter():
    record_number = 1

    for record in sys.stdin:
        fields=re.split("\t", record.strip())
        if record_number == 1:
            # get the indexes of the valid columns
            valid_columns_index  = [ i for i in range(len(fields)) if re.match("qc\d+-\d+", fields[i]) is None ]
            
        yield "\t".join( [fields[i] for i in valid_columns_index ] )
        record_number += 1
        
def main():

    cut_stream = cut_iter()

    for record in cut_stream:
        print(record)

if __name__ == "__main__":
   main()

