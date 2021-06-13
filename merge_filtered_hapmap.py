#!/bin/env pypy
from __future__ import print_function
import itertools
import sys
import argparse
import re
import os

# simple fasta iter
def fasta_iter(filestream):
    record_iter = (record.strip() for record in filestream if len(record.strip()) > 0)
    seq_group_iter = itertools.groupby(record_iter, lambda record:{True:"name", False:"seq"}[record[0] == ">"])
    name = None
    for (group, records) in seq_group_iter:
        if group == "name":
            name=records.next().split()[0][1:]
        else:
            yield (name, list(itertools.chain((name,),records)))

def apply_discards(filename, options):
    with open(options["discarded_fasta"],"r") as fastastream:
        filtered_seqs_list = [ item[0] for item in fasta_iter(fastastream)]  # list of names of seqs in the filtered file
        #print(filtered_seqs_list[0:5])
        tagnames = [ re.match("^(\S+?)_",item).groups()[0] for item in filtered_seqs_list ]
        #print(tagnames[0:5])

        # process the file to be merged.

        # first sniff it to see if it is a fasta file
        filetype="tab"
        with open(filename,"r") as mergefile:
            for record in mergefile:
                if re.match("^>", record) is not None:
                    filetype="fasta"
                    break

        with open(filename,"r") as mergestream:
            if filetype == "tab":
                mergefile=mergestream
            else:
                mergefile=fasta_iter(mergestream)

                
            mergename = os.path.join(options["outdir"],os.path.basename(filename))
            
            with open(mergename, "w") as mergeout:
                record_count = 0
                for record in mergefile:         # for tab file will be just a string, for fasta file will be (name, seq)
  
                    # if this is the first record it is a heading, so output and 
                    # continue
                    if record_count == 0 and filetype == "tab":
                        print(record,end="", file=mergeout)
                        record_count += 1
                        continue
     
                    if filetype == "tab":
                        tuples = re.split("\t", record)
                    else:
                        tuples = (re.match("^(\S+?)_",record[0]).groups()[0], record[1])
                    #print(tuples[0])
                    if tuples[0] in tagnames and record_count > 0:
                        continue
                    else:
                        if filetype == "tab":
                            print(record,end="", file=mergeout)
                        else:
                            print(">%s\n%s"%(record[0], "\n".join(record[1][1:])), file=mergeout)
                            
                    record_count += 1

def apply_includes(filename, options):
    with open(options["included_names"],"r") as namestream:
        tagnames = [ re.match("^(\S+?)_",record).groups()[0] for record in namestream ]

        # process the file to be merged.

        # first sniff it to see if it is a fasta file
        filetype="tab"
        with open(filename,"r") as mergefile:
            for record in mergefile:
                if re.match("^>", record) is not None:
                    filetype="fasta"
                    break

        with open(filename,"r") as mergestream:
            if filetype == "tab":
                mergefile=mergestream
            else:
                mergefile=fasta_iter(mergestream)

                
            mergename = os.path.join(options["outdir"],os.path.basename(filename))
            
            with open(mergename, "w") as mergeout:
                record_count = 0
                for record in mergefile:         # for tab file will be just a string, for fasta file will be (name, seq)

                    # if this is the first record it is a heading, so output and
                    # continue
                    if record_count == 0 and filetype == "tab":
                        print(record,end="", file=mergeout)
                        record_count += 1
                        continue

                    if filetype == "tab":
                        tuples = re.split("\t", record)
                    else:
                        tuples = (re.match("^(\S+?)_",record[0]).groups()[0], record[1])
                    #print(tuples[0])
                    if tuples[0] not in tagnames:
                        continue
                    else:
                        if filetype == "tab":
                            print(record,end="", file=mergeout)
                        else:
                            print(">%s\n%s"%(record[0], "\n".join(record[1][1:])), file=mergeout)
                            
                    record_count += 1

                    
        
        

def get_options():
    description = """
Use a fasta file of discards ( for example, tags with adapter have been removed e.g. by cutadapt) to filter the
tabular and fasta hapmap files , by removing the discards together with any tag-pair siblings of the discards.
Example counts :

iramohio-01$ wc in.txt out.txt
 15498  15498 258234 in.txt ( = all tags in )
 15463  15463 257658 out.txt ( = tags out together with tags discarded by cutadapt - the difference (35) is untrimmed sibling of trimmed partner) 

 reconcile :

tags out : 
iramohio-01$ grep ">" /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap_filtered/HapMap.fas.txt | wc
  11998   11998  199880

tags in :  
iramohio-01$ grep ">" /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.fas.txt | wc
  15498   15498  258234

tags discarded : 
iramohio-01$ grep ">" /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap_filtered/HapMap.fas.discarded.txt | wc
   3465    3465   57778


15498 tags less 3465 discarded (cutadapt trim) less 35 (untrimmed sibling of trimmed partner) = 11,998

Example :

iramohio-01$ diff in.txt out.txt | head
117d116
< >TP10212_hit_64
1279d1277
< >TP1314_hit_64
1794d1791
< >TP14277_query_64  <---------
1806d1802
< >TP14304_query_64
2007d2002
< >TP14868_hit_64


iramohio-01$ grep TP14277 /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap_filtered/HapMap.fas.discarded.txt
>TP14277_hit_64
iramohio-01$

i.e. TP14277_hit_64 was discarded by cutadapt (but not its sibling), but we discard both
    """

    long_description = """
    Example :

merge_filtered_hapmap.py  -D /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap_filtered/HapMap.fas.discarded.txt -O /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap_filtered /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.hmc.txt /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.hmp.txt /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.fas.txt /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.hmp.txt.blinded /dataset/gseq_processing/scratch/gbs/200730_D00390_0568_BCECP9ANXX/SQ1326.all.PstI.PstI/hapMap/HapMap.hmc.txt.blinded

    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('files', type=str, nargs='*',help='space-seperated list of files to process')
    parser.add_argument('-D', '--discarded_fasta', dest='discarded_fasta', type=str, default = None , help="fasta file of discarded tags (e.g. from cutadapt)")
    parser.add_argument('-I', '--included_names', dest='included_names', type=str, default = None , help="file containing tag names to be included")    
    parser.add_argument('-O', '--outdir', dest='outdir', type=str, default = None, required=True , help="out dir")

    
    args = vars(parser.parse_args())

    return args


def main():

    args=get_options()
    for filetodo in args["files"]:
        if not os.path.exists(filetodo):
            print("(merge_hapMap_filtered.py:  %s does not exist so ignoring) "%filetodo)
            continue

        if args["discarded_fasta"] is not None and args["included_names"] is None:
            apply_discards(filetodo, args)
        elif args["discarded_fasta"] is None and args["included_names"] is not None:
            apply_includes(filetodo, args)
        else:
            raise Exception("must supply one of discards or included")
        

if __name__ == "__main__":
   main()

