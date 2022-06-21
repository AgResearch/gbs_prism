#!/bin/env python
from __future__ import print_function
#########################################################################
# ramify a custom keyfile into different libraries to prep for demultiplexing
# safely (check for name collisions) merge the count files from different libraries into a single folder 
#########################################################################
import argparse
import sys
import os
import re
import itertools

BARCODE_LENGTH=10


def get_options():
    description = """
    """
    long_description = """

check whether a GBS (tassel3) keyfile contains multiple flowcell-library-fastqfile combinations, if so need to demultiplex each combination separately
the ramify_tassel_keyfile.py script will set up a tassel demultiplexing environment in subfolders of tagCounts_parts. These will be called e.g.
tagCounts_parts/part_NNN
where NNN is 1,2,... 
so the structure will be
tagCounts_parts/part<digest>/tagCounts
                        /key
                        /Illumina

examples:

/dataset/gseq_processing/active/bin/gbs_prism/ramify_tassel_keyfile.py -t ramify -o /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts_parts --sub_tassel_prefix part /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/key/sample_info.key

# merge the outputs into the top level folder
/dataset/gseq_processing/active/bin/gbs_prism/ramify_tassel_keyfile.py -t merge_results -o  /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts --sub_tassel_prefix part
number_of_parts=`cat ${OUT_DIR}/tagCounts_parts/number_of_keyfile_parts.txt`


"""

    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('keyfile', type=str, nargs=1,help='keyfile to ramify')
    parser.add_argument('-t', '--task' , dest='task', required=False, type=str, choices=["ramify", "merge_results"], default = "exclude_tiles", help="what you want to get / do")
    parser.add_argument('-o','--output_folder', dest='output_folder', type=str, default=None, help='output folder')
    parser.add_argument('-m','--merge_folder', dest='merge_folder', type=str, default=None, help='merge folder')    
    parser.add_argument('-p','--sub_tassel_prefix', dest='sub_tassel_prefix', type=str, default="part", required=False, help='min pass filter')
    
    args = vars(parser.parse_args())

    if not os.path.exists(args["keyfile"][0]):
        print("keyfile %(keyfile)s does not exist"%args)
        sys.exit(1)
    else:
        if not os.path.isfile(os.path.realpath( args["keyfile"][0] )):
            print("keyfile %(keyfile)s is not a file "%args)
            sys.exit(1)
                
    return args

def ramify(options):
    """
typical keyfile looks like 

iramohio-01$ head /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/bee_SQ1793_SQ1794/sample_info.key
flowcell        lane    barcode sample  platename       row     column  libraryprepid   counter comment enzyme  species numberofbarcodes        bifo    control fastq_link
HN7WGDRXY       1       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
HN7WGDRXY       2       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz
HN7WGDRXY       1       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
HN7WGDRXY       2       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz

"""

    # read keyfile into array of tuples and get heading
    # bail out if do not see columns called flowcell, lane, libraryprepid and fastq_link
    print("ramifying keyfile %s"%options["keyfile"][0])
    with open(options["keyfile"][0],"r") as instream:
        records = [ re.split("\t", record.strip()) for record in instream ]
        print("read %d keyfile records"%len(records))

        header = [ item.strip().lower() for item in records[0] ]
        indexes={}
        for fieldname in ("flowcell", "lane", "libraryprepid" , "fastq_link"):
            if fieldname not in header:
                raise Exception("ramify_tassel_keyfile : could not find '%s' in header - unable to ramify keyfile (header contains : %s)"%(fieldname, str(header)))
            else:
                indexes[fieldname] = header.index(fieldname)

        # sort the keyfile array
        # define a comparator
        def my_cmp(record1, record2):
            if record1[indexes["flowcell"]] != record2[indexes["flowcell"]]:
                return cmp(record1[indexes["flowcell"]], record2[indexes["flowcell"]])
            else: 
                return cmp(record1[indexes["libraryprepid"]], record2[indexes["libraryprepid"]])

        print("sorting keyfile")
        sorted_records = sorted(records[1:], my_cmp)
            
        # set up an iterator, grouping by flowcell and libraryprepid
        print("analysing keyfile")        
        sub_file_iter = itertools.groupby(sorted_records, lambda rec:(rec[indexes["flowcell"]],rec[indexes["libraryprepid"]]))
        
        # for each group, create the sub-folder structure and write the sub-key-file
        part_number = 1
        for flowcell_lib_tuple, record_iter in sub_file_iter:
            # sub-folder structure
            part_folder = os.path.join(options["output_folder"], "%s%d"%(options["sub_tassel_prefix"],part_number))
            key_folder=os.path.join(part_folder, "key")
            tag_folder=os.path.join(part_folder, "tagCounts")
            illumina_folder=os.path.join(part_folder, "Illumina")
            for folder_name in (part_folder, key_folder,tag_folder, illumina_folder): 
                if not os.path.isdir(folder_name):
                    os.mkdir(folder_name)
                if not os.path.isdir(folder_name):
                    raise Exception("unable to create folder %s"%folder_name)

            # write keyfile and also validate the number of distinct lanes and fastq file in each group is the same, and create the
            # links to fastq 
            lanes=set()
            fastq_files=set()
            sub_key_file_name = os.path.join(key_folder, "%s_%s.keyfile"%flowcell_lib_tuple)
            with open(sub_key_file_name,"w") as key_out:
                print("\t".join(header), file=key_out)
                for record in record_iter:
                    print("\t".join(record),file=key_out)
                    lanes.add(record[indexes["lane"]])
                    fastq_files.add(record[indexes["fastq_link"]])
                if len(lanes) != len(fastq_files):
                    raise Exception("lanes .v. fastq links mismatch : %s versus %s"%(str(list(lanes)), str(list(fastq_files))))

                for link in fastq_files:
                    if not os.path.exists( os.path.join(key_folder, os.path.basename(link)) ):
                        os.symlink(link, os.path.join(illumina_folder, os.path.basename(link)))

            part_number += 1

        print("wrote out %d partial keyfiles and supporting folders "%part_number)                

def merge_results(options):
    """
typical keyfile looks like 

iramohio-01$ head /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/bee_SQ1793_SQ1794/sample_info.key
flowcell        lane    barcode sample  platename       row     column  libraryprepid   counter comment enzyme  species numberofbarcodes        bifo    control fastq_link
HN7WGDRXY       1       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
HN7WGDRXY       2       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz
HN7WGDRXY       1       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
HN7WGDRXY       2       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz

"""

    # list the subfolders of the out folder, that are folders and match the expected name
    print("merging demultiplexing from %s to %s"%(options["output_folder"], options["merge_folder"]))                
    part_folders = os.listdir(options["output_folder"])
    part_folders = [ os.path.join(options["output_folder"] , content) for content in part_folders if re.match(options["sub_tassel_prefix"],content) is not None ]
    part_folders = [ folder for folder in part_folders if os.path.isdir(folder)]

    print("folders to merge from : %s"%str(part_folders))

    # create shortcuts to the count files in the main output and detect name collisions
    unique_count_files = set()
    for part_folder in part_folders:
        count_files = [count_file for count_file in os.listdir(os.path.join(part_folder, "tagCounts")) if re.search("\.cnt$", count_file) is not None]
        for count_file in count_files:
            base = os.path.basename(count_file)
            if base in unique_count_files:
                raise Exception("error - encountered two copies of %s - bailing out, please check sample sheets and keyfiles"%base)
            unique_count_files.add(base)
            target = os.path.join(options["merge_folder"], base)
            os.symlink(count_file, target)
            

                
         
def main():    
    options = get_options()

    if options["task"] == "ramify":
        ramify(options)
    elif options["task"] == "merge_results":
        merge_results(options) 
        
    
            
if __name__=='__main__':
    sys.exit(main())    

    

        

