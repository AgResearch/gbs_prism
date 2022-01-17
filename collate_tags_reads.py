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

def get_reads_tags(args,format="database_import"):
    """
    
    """
    for filename in args["filenames"]:
        with open(filename,"r") as tag_counts:
            # e.g.
            #sample,flowcell,lane,sq,tags,reads
            #total,H2TTCDMXY,1,SQ1745,,361922664
            #good,H2TTCDMXY,1,SQ1745,,333623829
            #qc823992-1,H2TTCDMXY,1,1745,129084,626118
            #qc824060-1,H2TTCDMXY,1,1745,36105,91036
            novaseq_counts = {} 
            column_headings=None
            flowcell = None
            sq = None
            for record in tag_counts:
                if column_headings is None:
                    column_headings = re.split("\s*,\s*", record.strip())
                    column_headings = [item.lower().strip() for item in column_headings]
                    if tuple(column_headings) != ("sample","flowcell","lane","sq","tags","reads"):
                        raise Exception("collate_tags_reads.py : heading = %s, did not expect that"%str(column_headings))
                    continue
                fields=[item.strip() for item in re.split("\s*,\s*", record.strip())]
                if len(fields) == 0:
                    continue

                if len(fields) != len(column_headings):
                    raise Exception("collate_tags_reads.py : wrong number of fields in %s, should match %s"%(str(fields),str(column_headings)))

                field_dict=dict(zip(column_headings, fields))

                if field_dict["sample"] in ("total","good"):
                    continue

                if flowcell is None:
                    flowcell = field_dict["flowcell"]
                    sq = field_dict["sq"]

                if flowcell != field_dict["flowcell"] or sq != field_dict["sq"]:
                    raise Exception("looks like one or more files contains data for more than one flowcell or sq number - this is not supported. First saw %s, then later %s"%(str((flowcell, sq)), str((field_dict["flowcell"], field_dict["sq"]))))
                
                if args["machine"] in ("hiseq", "miseq", "iseq"):
                    yield (args["run"],args["cohort"]) + tuple(field_dict[name] for name in ("sample","flowcell","lane","sq","tags","reads"))
                elif args["machine"] == "novaseq":
                    # the novaseq tag count file has totals for several "lanes", and we want to collpase these
                    novaseq_counts[field_dict["sample"]] = list(map(lambda x,y:x+y, [int(field_dict["tags"]),int(field_dict["reads"])], novaseq_counts.get(field_dict["sample"],[0,0])))
                else:
                    raise Exception("oops unexpected machine type %(machine)s"%args)

            if args["machine"] == "novaseq":
                for sample in novaseq_counts:
                    yield (args["run"],args["cohort"], sample, flowcell, "1", sq, str(novaseq_counts[sample][0]),  str(novaseq_counts[sample][1]))
            

def get_options(): 
    description = """
    """
    long_description = """

examples :

collate_tags_reads.py --run 211217_A01439_0043_BH2TTCDMXY --cohort SQ1744.all.PstI-MspI.PstI-MspI /dataset/hiseq/scratch/postprocessing/gbs/211217_A01439_0043_BH2TTCDMXY/SQ1744.all.PstI-MspI.PstI-MspI/TagCount.csv.blinded

# for testing 
./collate_tags_reads.py --run 211020_A01439_0028_AHHYWFDRXY --cohort SQ1705.all.salmon.PstI-MspI --machine hiseq /dataset/hiseq/scratch/postprocessing/gbs/211020_A01439_0028_AHHYWFDRXY/SQ1705.all.salmon.PstI-MspI/TagCount.csv.blinded
./collate_tags_reads.py --run 211020_A01439_0028_AHHYWFDRXY --cohort SQ1706.all.chinook_salmon.PstI-MspI --machine hiseq /dataset/hiseq/scratch/postprocessing/gbs/211020_A01439_0028_AHHYWFDRXY/SQ1706.all.chinook_salmon.PstI-MspI/TagCount.csv.blinded
./collate_tags_reads.py --run 211020_A01439_0028_AHHYWFDRXY --cohort SQ1706.all.salmon.PstI-MspI --machine hiseq /dataset/hiseq/scratch/postprocessing/gbs/211020_A01439_0028_AHHYWFDRXY/SQ1706.all.salmon.PstI-MspI/TagCount.csv.blinded


-rw-rw-r-- 1 mccullocha hiseq_users 32029 Oct 22 10:30 /dataset/hiseq/scratch/postprocessing/gbs/211020_A01439_0028_AHHYWFDRXY/SQ1706.all.salmon.PstI-MspI/TagCount.csv.blinded




   #cat $file | awk -F, '{printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",run,cohort,$1,$2,$3,$4,$5,$6);}' run=$run cohort=$cohort - >> $RUN_PATH/html/gbs_yield_import_temp.dat
   # e.g.
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    sample  flowcell        lane    sq      tags    reads
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    total   CCVK0ANXX       1       SQ0788          298918641
   #180914_D00390_0399_ACCVK0ANXX   SQ0788.all.DEER.PstI    good    CCVK0ANXX       1       SQ0788          268924508

+ awk -F, '{printf("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",run,cohort,$1,$2,$3,$4,$5,$6);}' run=211217_A01439_0043_BH2TTCDMXY cohort=SQ1744.all.PstI-MspI.PstI-MspI -
+ cat /dataset/hiseq/scratch/postprocessing/gbs/211217_A01439_0043_BH2TTCDMXY/SQ1744.all.PstI-MspI.PstI-MspI/TagCount.csv.blinded
   


python collate_tags_reads.py /bifo/scratch/gseq_processing/gbs/210324_D00390_0613_BCD418ANXX/SQ1572.all.deer.PstI/KGD/GHW05.vcf /dataset/gseq_processing/scratch/gbs/210324_D00390_0613_BCD418ANXX/SQ2965.all.PstI-MspI.PstI-MspI/KGD/GHW05.vcf
python collate_tags_reads.py 


    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filenames', type=str, nargs='*',help='space-separated list of tag count files to summarise ')
    parser.add_argument('--run', dest='run', type=str, required=True, help='run name')
    parser.add_argument('--cohort', dest='cohort', type=str, required=True, help='cohort')
    parser.add_argument('--machine', dest='machine', choices = ['novaseq','hiseq','miseq','iseq'], default="novaseq", type=str, help='which machine')
    
    args = vars(parser.parse_args())

    # check args
    for filepath in args["filenames"]:
        if not os.path.isfile(filepath):
            print("%s does not exist"%filepath)
            sys.exit(1)
 

    return args
            

def main():

    args=get_options()

    reads_tags = get_reads_tags(args)

    for record in reads_tags:
        print("\t".join(record))
    return 0

if __name__=='__main__':
    sys.exit(main())    

    

        

