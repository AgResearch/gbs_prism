#!/usr/bin/env python
#
# annotate output with gbs_cohort, species, enzyme, count
#
import sys
import os
import re
import itertools
import string
import exceptions
import argparse
import subprocess



def annotate():

    # records are like

    #/dataset/gseq_processing/scratch/gbs/181005_D00390_0407_BCCV91ANXX/SQ0807.all.DEER.PstI/KGD -0.02888578 0.3695895
    #/dataset/gseq_processing/scratch/gbs/181005_D00390_0407_BCCV91ANXX/SQ2766.all.ApeKI.ApeKI/KGD -0.1362936 0.2429048

    #/bifo/scratch/2023_illumina_sequencing_a/postprocessing/180810_D00390_0392_BCCR4LANXX.gbs/SQ0772.processed_sample/uneak/all.DEER.PstI.cohort/KGD -2.523152 5.655549e-05
    #/bifo/scratch/2023_illumina_sequencing_a/postprocessing/180810_D00390_0392_BCCR4LANXX.gbs/SQ0772.processed_sample/uneak/all.GOAT.PstI.cohort/KGD -0.03751884 0.002106262
    #/bifo/scratch/2023_illumina_sequencing_a/postprocessing/180810_D00390_0392_BCCR4LANXX.gbs/SQ0775.processed_sample/uneak/all.Cattle.PstI.cohort/KGD 0.007961025 0.7796325
    #
    # and
    # /bifo/scratch/2023_illumina_sequencing_a/postprocessing/171218_D00390_0337_BCBG3AANXX.gbs/SQ0575.processed_sample/uneak/PstI.PstI.cohort
    # and
    # /dataset/2023_illumina_sequencing_a/scratch/postprocessing/150224_D00390_0217_AC4UAUACXX.gbs/SQ0056.processed_sample/uneak/all.PstI.PstI.cohort/KGD -0.2113675 2.645513e-25
    # from this :
    # flowcell = CCR4LANXX
    # libraryprepid = 772 etc
    # (cohort, enzyme) = 
    
    record_array = [ re.split("\s+", record.strip()) for record in sys.stdin if len(record.strip()) > 1 ]

    
    for record in record_array:
        (path, sloope, pval) = record
        (flowcell, libraryprepid, gbs_cohort) = ("?", "?", "?")
        flowcell_match=re.search("\d+_[^_]+_\d+_.([^./]+)[/\.]", path)
        if flowcell_match is not None:
            flowcell = flowcell_match.groups()[0]
        library_match = re.search("/SQ(\d+)\.", path)
        if library_match is not None:
            libraryprepid = library_match.groups()[0]
            libraryprepid = re.sub("^0+","",libraryprepid)
        #cohort_match  = re.search("all\.([^.]+)\.", path)
        cohort_match  = re.search("[\/.]([^.\/]+)\.[^.\/]+/KGD", path)

        if cohort_match is not None:
            gbs_cohort = cohort_match.groups()[0]
            
        # exmaple :
        # psql -U agrbrdf -d agrbrdf -h postgres -v flowcell="'CCR4LANXX'" -v libraryprepid=775 -v gbs_cohort="'TILAPIA'" -f get_cohort_count.psql -q                
        command = ["psql",  "-U",  "gbs",  "-d" ,"agrbrdf", "-h", "postgres", "-v","flowcell='%s'"%flowcell, "-v", \
                   "libraryprepid=%s"%libraryprepid, "-v", "gbs_cohort='%s'"%gbs_cohort, "-f",  "get_cohort_count.psql",  "-q"]

        print >> sys.stderr, "executing %s"%" ".join(command)
        proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (stdout, stderr) = proc.communicate()
        stdout_lines = re.split("\n", stdout)  # e.g. ['species\tgbs_cohort\tenzyme\tcount', 'goat\tGOAT\tPstI\t214', '']
        if len(stdout_lines) >= 3:
            (species, gbs_cohort, enzyme, count) = re.split("\t", stdout_lines[1])
            print >> sys.stdout, "\t".join(record + list((species, gbs_cohort, enzyme, count)))
        else:
            print >> sys.stderr,"Warning unexpected return from query : %s"%stdout
            (species, gbs_cohort, enzyme, count) = ("?","?","?","?")
            print >> sys.stderr, "\t".join(record + list((species, gbs_cohort, enzyme, count)))

        if proc.returncode != 0:
            print "query appears to have failed"       
        
def main():

    annotate()


if __name__ == "__main__":
   main()
  

