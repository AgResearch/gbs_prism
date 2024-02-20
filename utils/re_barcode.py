#!/usr/bin/env python 

import os
import re
import string
import argparse
import logging
from StringIO import StringIO
from data_prism import get_text_stream , get_file_type
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
from Bio import SeqIO


def seq_from_sequence_file(datafile, filetype, sampling_proportion):
    """
    yields either all or a random sample of seqs from a sequence file
    """
    seq_iter = SeqIO.parse(get_text_stream(datafile), filetype)

    if sampling_proportion is not None:
        seq_iter = (record for record in seq_iter if random() <= sampling_proportion)
        
    return seq_iter


def recode(options):

    if options["action"] == "recode":
        outfile = open(options["output_filename"],"a")

    stats = {}

    for target_sequence_filename in options["decoded_filenames"]:
        stats[target_sequence_filename] = {"barcode":None, "seq_count" : 0, "exclude_count" : 0, "inbase_count" : 0, "outbase_count" : 0 , "exclude_base" : 0}
        # get the barcode from the filename
        match = re.search(options["barcode_regexp"], target_sequence_filename)
        if match is None:
            print "skipping file %s"%target_sequence_filename
            continue
        else:
            barcode = match.groups()[0]
            print "relabelling seqs in %s with barcode %s"%(target_sequence_filename, barcode)
            stats[target_sequence_filename]["barcode"] = barcode

            seq_format=get_file_type(target_sequence_filename)
            
            # make a seq_record containing the barcode by reading in a string fastq_record 
            barcode_string = "@%s\n%s\n+\n%s\n" % ("barcode", barcode, len(barcode)*"F")  
            barcode_record = SeqIO.read(StringIO(barcode_string), seq_format)

            
            seq_iter = seq_from_sequence_file(target_sequence_filename, seq_format , None)
            for seq_record in seq_iter:
                stats[target_sequence_filename]["seq_count"] += 1
                stats[target_sequence_filename]["inbase_count"] += len(seq_record.seq)
                
                
                if len(seq_record.seq) + len(barcode) < options["minlength"]:
                    print "skipped %s, too short (seq=%d barcode=%d)"%(seq_record.id, len(seq_record.seq), len(barcode))
                    stats[target_sequence_filename]["exclude_count"] += 1
                    stats[target_sequence_filename]["exclude_base"] += len(seq_record.seq)
                    continue

                recoded_record = barcode_record + seq_record
                recoded_record.id = seq_record.id
                recoded_record.description = seq_record.description
                stats[target_sequence_filename]["outbase_count"] += len(recoded_record.seq)
                if options["action"] == "recode":                    
                    SeqIO.write(recoded_record, outfile, seq_format)

                # for debugging 
                #if stats[target_sequence_filename]["seq_count"] > 200000:
                #    break
                    
    if options["action"] == "recode":
        outfile.close()


    # print stats
    print "filename\tbarcode\tseq_count\texclude_count\tinbase_count\toutbase_count\texclude_base"
    for (filename, file_stats) in stats.items():
        print "%s\t%s\t%s\t%s\t%s\t%s\t%s"%(filename, file_stats["barcode"], file_stats["seq_count"], file_stats["exclude_count"],
                                file_stats["inbase_count"], file_stats["outbase_count"], file_stats["exclude_base"])
                    

def get_options():
    description = """
    This script adds back barcodes to sequences, where  a custom demuliplexing run
    has generated many files, one for each barcode, and we want to re-attach those
    barcodes and make a single sequence file (...to fit in with a GBS pipeline)
    """
    long_description = """
    Example 1 :

    re_barcode.py -o /dataset/hiseq/scratch/postprocessing/161005_D00390_0268_AC9NRJANXX.processed/bcl2fastq/Project_Red_Clover/Sample_SQ2592/SQ2592_NoIndex_L008_R1_001.fastq /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/*.gz

    where the input files are like

/dataset/hiseq/scratch/SQ2592/demulti/_s_8_/10-2bA_ACTGGT_apeki.R1.fastq.gz    /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/63-3aA_TTGCAGT_apeki.R1.fastq.gz
/dataset/hiseq/scratch/SQ2592/demulti/_s_8_/10-2bB_GAATCT_apeki.R1.fastq.gz    /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/63-3aB_CGGTTGGA_apeki.R1.fastq.gz
/dataset/hiseq/scratch/SQ2592/demulti/_s_8_/15-4A_GTTCATA_apeki.R1.fastq.gz    /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/64-1A_TTGCTAGGT_apeki.R1.fastq.gz
/dataset/hiseq/scratch/SQ2592/demulti/_s_8_/15-4B_TTGCGGCA_apeki.R1.fastq.gz   /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/65-1A_CCAATGTAA_apeki.R1.fastq.gz
/dataset/hiseq/scratch/SQ2592/demulti/_s_8_/23-30A_AAGCA_apeki.R1.fastq.gz     /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/65-1B_CCAAGCTTA_apeki.R1.fastq.gz

- i.e. they include the barcode as part of the name 

    Example 2 : 

    re_barcode.py -B "\S+_([ACTG]+)_psti-mspi" -l /dataset/GBS_Tcirc/ztmp/SQ1014_analysis/filtered/SQ1014_CDT5UANXX_s_3_filtered.fastq.log -o /dataset/GBS_Tcirc/ztmp/SQ1014_analysis/filtered/SQ1014_CDT5UANXX_s_3_filtered.fastq /dataset/GBS_Tcirc/ztmp/SQ1014_analysis/filtering/SQ1014_CDT5UANXX_s_3_fastq.txt.gz.demultiplexed_935074_GAATCGAA_psti-mspi.R1_trimmed.fastq_Hcont_microb_sheep_Tcircemp_Tcircref_Tcolub_Tcircmito_Tvit_00001000.fastq /dataset/GBS_Tcirc/ztmp/SQ1014_analysis/filtering/SQ1014_CDT5UANXX_s_3_fastq.txt.gz.demultiplexed_935074_GAATCGAA_psti-mspi.R1_trimmed.fastq_Hcont_microb_sheep_Tcircemp_Tcircref_Tcolub_Tcircmito_Tvit_00011000.fastq > /dataset/GBS_Tcirc/ztmp/SQ1014_analysis/filtered/SQ1014_CDT5UANXX_s_3_filtered.fastq.stats

Example in and out :

intrepid$ gunzip -c /dataset/hiseq/scratch/SQ2592/demulti/_s_8_/10-2bA_ACTGGT_apeki.R1.fastq.gz | head -12                                                                  @INV-D00390:268:C9NRJANXX:8:1101:1848:2053 1:N:0:
@INV-D00390:268:C9NRJANXX:8:1101:1848:2053 1:N:0:
CTGCCGAATCTTCCACTGGGACATGGACAACTGTGTGGACCGATGGACTTACCAGTCTTGATCGTTATAAAGGACGCTG
+
BF<FFFFFF<FFFFBBBFBBFFFFBF/FFF<FBFFF<BFFFFFFFF<BF//FBF</<BFFFBFFBF/<BFFBFFFFFFF
@INV-D00390:268:C9NRJANXX:8:1101:1912:2130 1:N:0:
CTGCAGAGTTATCATCATACTGTCCCCTCCATGCATTGCCACTATCTGTCCCACTGGATGCTTGATTTGGGATTGGAACATTACCACCTAAA
+
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF<FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF<FFFFFBFFFFFFFFFFFFFFFF
@INV-D00390:268:C9NRJANXX:8:1101:3101:2138 1:N:0:
CTGCGTTCGGGAAGGATGAATCGCTCCCGAAGAGGAATCTATTGATTCTCTCCCAATTGGATGGACCGTAGGTGCGATGATTTACTTCACGG
+
FFFFFFFFFBFBFFBFFFFFFFFFFFFFFBBFF<//BBFFFFF/FFFFFFFFFFFFFFBBFF/BFFF<FFF/F<FFFFFFFFFFFFFFFFF<


intrepid$ head -12 /dataset/hiseq/scratch/postprocessing/161005_D00390_0268_AC9NRJANXX.processed/bcl2fastq/Project_Red_Clover/Sample_SQ2592/SQ2592_NoIndex_L008_R1_001.fastq
@INV-D00390:268:C9NRJANXX:8:1101:1848:2053 1:N:0:
ACTGGTCTGCCGAATCTTCCACTGGGACATGGACAACTGTGTGGACCGATGGACTTACCAGTCTTGATCGTTATAAAGGACGCTG
+
FFFFFFBF<FFFFFF<FFFFBBBFBBFFFFBF/FFF<FBFFF<BFFFFFFFF<BF//FBF</<BFFFBFFBF/<BFFBFFFFFFF
@INV-D00390:268:C9NRJANXX:8:1101:1912:2130 1:N:0:
ACTGGTCTGCAGAGTTATCATCATACTGTCCCCTCCATGCATTGCCACTATCTGTCCCACTGGATGCTTGATTTGGGATTGGAACATTACCACCTAAA
+
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF<FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF<FFFFFBFFFFFFFFFFFFFFFF
@INV-D00390:268:C9NRJANXX:8:1101:3101:2138 1:N:0:
ACTGGTCTGCGTTCGGGAAGGATGAATCGCTCCCGAAGAGGAATCTATTGATTCTCTCCCAATTGGATGGACCGTAGGTGCGATGATTTACTTCACGG
+
FFFFFFFFFFFFFFFBFBFFBFFFFFFFFFFFFFFBBFF<//BBFFFFF/FFFFFFFFFFFFFFBBFF/BFFF<FFF/F<FFFFFFFFFFFFFFFFF<
    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('decoded_filenames', type=str, nargs="+",metavar="decoded_filenames", help='names of decoded files')
    parser.add_argument('-o', '--output_filename' , dest='output_filename',  default = None, metavar="recoded filename", type=str, help="recoded filename")
    parser.add_argument('-l', '--log_filename' , dest='log_filename', default = "info_trim.log", metavar="log filename", type=str, help="name of the file for logging / stats info")
    parser.add_argument('-x', '--action' , dest='action', default="recode", metavar="action to perform", choices=["recode", "report"],type=str, help="action")    
    parser.add_argument('-m', '--minlength' , dest='minlength', type=int, default=33, metavar="minlength", help="minlength")    
    parser.add_argument('-B', '--barcode_regexp', dest='barcode_regexp', type=str, default="\S+_([ACTG]+)_\S+\.R1\.fastq\.gz", help="regexp to extract barcode from filename")

    args = vars(parser.parse_args())

    # output file should not already exist
    if args["action"] == "recode":
        if args["output_filename"] is None:
            parser.error("need an output filename if recoding")
        else:
            if os.path.exists(args["output_filename"]):
                print "Warning - appending to existing file %(output_filename)s"%args

    # set up logging
    logging.basicConfig(filename=args["log_filename"],level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
                    

    return args


def main():
    options = get_options()
    print options

    logging.info(recode(options))
    
    return 

    
if __name__ == "__main__":
   main()



        

