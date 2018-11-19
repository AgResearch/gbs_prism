#!/usr/bin/env python


#
# this script creates a client oriented html document for each cohort of
# a gbs run, which presents the various plots generated , and
# has links to text output. Its also calls utilities to make a pdf and
# marshall the output to be sent.
#
import os
import re
import itertools
import string
import exceptions
import argparse


header1="""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
   "httpd://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title>
Results for %(cohort_name)s
</title>
</head>
<body>
<h1> Results for %(cohort_name)s </h1>
<ul>
</p>
"""


footer1="""
</body>
</html>
"""

BASEDIR="/dataset/gseq_processing/scratch/gbs"


def get_cohorts(options):
    # cohorts are idenitified as subfolders of the run folder that
    # * are not tardis working folders (i.e. have names starting with tardis
    # * are of like SQ0775.all.TILAPIA.PstI-MspI
    #   - i.e. library.qc-cohort.gbs-cohort.enzyme
    run_folder=os.path.join(BASEDIR, options["run_name"])
    #print "DEBUG : "+run_folder
    #SQ0810.all.PstI-MspI.PstI-MspI
    #SQ0812.all.ApeKI.ApeKI
    #SQ2768.all.ApeKI.ApeKI
    #SQ2769.all.ApeKI.ApeKI
    #SQ2770.all.ApeKI.ApeKI

    cohort_folders=[ node for node in os.listdir(run_folder) if re.search("^tardis", node) is None and  \
                     re.search("^\S+\.\S+\.\S+\.\S+$", node) is not None and os.path.isdir(os.path.join(run_folder, node)) ]
    
    return cohort_folders
    
    
def generate_run_plot(options):
    stats = {
        "found file count" : 0,
        "no file count" : 0,
        "no sample count" : 0
    }

    file_group_iter = (  ("KGD (plots)", "image"), ("KGD (text file links)", "link"), ("Hapmap files", "link" ) )
    file_iters = {
        "KGD (plots)" : ['KGD/AlleleFreq.png', 'KGD/CallRate.png', 'KGD/Co-call-HWdgm.05.png', 'KGD/Co-call-.png', 'KGD/finplot.png', 'KGD/GcompareHWdgm.05.png', 'KGD/Gcompare.png', 'KGD/Gdiagdepth.png', 'KGD/G-diag.png', 'KGD/GHWdgm.05diagdepth.png', 'KGD/GHWdgm.05-diag.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/HWdisMAFsig.png', 'KGD/LRT-hist.png', 'KGD/LRT-QQ.png', 'KGD/MAFHWdgm.05.png', 'KGD/MAF.png', 'KGD/PC1v2G5HWdgm.05.png', 'KGD/SampDepthCR.png', 'KGD/SampDepthHist.png', 'KGD/SampDepth.png', 'KGD/SampDepth-scored.png', 'KGD/SNPCallRate.png', 'KGD/SNPDepthHist.png', 'KGD/SNPDepth.png', 'KGD/X2star-QQ.png'],
        "KGD (text file links)" : ['KGD/GHW05.csv', 'KGD/GHW05-Inbreeding.csv', 'KGD/GHW05-long.csv', 'KGD/GHW05-pca_metadata.tsv', 'KGD/GHW05-pca_vectors.tsv', 'KGD/GHW05-PC.csv', 'KGD/GHW05.RData', 'KGD/GHW05.vcf', 'KGD/HeatmapOrderHWdgm.05.csv', 'KGD/HeatmapOrderHWdgm.05.csv.blinded', 'KGD/PCG5HWdgm.05.pdf', 'KGD/SampleStats.csv', 'KGD/SampleStats.csv.blinded', 'KGD/seqID.csv', 'KGD/seqID.csv.blinded'],
        "Hapmap files" : ['hapMap/HapMap.hmc.txt','hapMap/HapMap.hmp.txt']
    }
    
    #print "DEBUG : calling get_cohorts"
    cohorts = get_cohorts(options)
    for cohort in cohorts:


        with open(os.path.join(BASEDIR, options["run_name"], "html", cohort, options["output_filename"]),"w") as out_stream:

            with open(os.path.join(BASEDIR, options["run_name"], "html", cohort, "%s.manifest"%options["output_filename"]),"w") as out_manifest:

                print >> out_manifest, options["output_filename"]
                print >> out_manifest, "%s.manifest"%options["output_filename"]
                
                xoptions=options
                xoptions.update({"cohort_name" : cohort})

                print >> out_stream, header1%xoptions

                for (file_group, file_type)  in file_group_iter:
                    # output overall header for file group
                    print >> out_stream, "<h2> %s </h2>\n"%file_group
                    # output cohort column headings
                    print >> out_stream, "<table width=90%% align=center>\n", \
                                         "<tr>\n", \
                                         "<td> <h4> Name </h4> </td>\n",\
                                         "\n".join(["<td><h4> %s </h4></td>"%cohort for cohort in [cohort]]), \
                                         "\n</tr>\n"
                    for file_name in file_iters[file_group]:


                        print >> out_stream , "<tr><td>%s</td>\n"%file_name
                        file_path = os.path.join(BASEDIR, options["run_name"], cohort, file_name)

                        if file_type == "image":
                            image_relpath=file_name

                            print >> out_manifest, image_relpath

                            if os.path.isfile(file_path):
                                print >> out_stream, "<td> <img src=%s title=%s height=300 width=300/> </td>\n"%(image_relpath, file_path)
                            else:
                                print >> out_stream, "<td> unavailable </td>\n"
                        elif file_type == "link":
                            link_relpath=file_name

                            print >> out_manifest, link_relpath


                            if os.path.isfile(file_path):
                                print >> out_stream, "<td width=300> <a href=%s target=%s> %s </a></td>\n"%(link_relpath, file_name, link_relpath)
                            else:
                                print >> out_stream, "<td width=300> unavailable </td>\n"
                        print >> out_stream , "</tr>\n"
                    print >> out_stream, "</table>\n"
                print >> out_stream, footer1

    print stats
                
                
def get_options():
    description = """
    """
    long_description = """
example :

./make_clientcohort_pages.py -r 181112_D00390_0415_BCD04NANXX -o report.html
key file summary looks like :

run     run_number      lane    samplename      species file_name
140624_D00390_0044_BH9PEBADXX   0044    1       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140624_D00390_0044_BH9PEBADXX   0044    2       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209    1       SQ0008  Deer    140904_D00390_0209_BC4U6YACXX.gbs/SQ0008.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209 

    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-r', '--run_name' , dest='run_name', required=True, type=str, help="run name")
    parser.add_argument('-H', '--image_height' , dest='image_height', default=300, type=int, help="image height")
    parser.add_argument('-W', '--image_width' , dest='image_width', default=300, type=int, help="image width")
    parser.add_argument('-o', '--output_filename' , dest='output_filename', default="peacock.html", type=str, help="name of output file")

    
    args = vars(parser.parse_args())

    return args


def main():

    options = get_options()
    print options 
    generate_run_plot(options)

    
if __name__ == "__main__":
   main()



        

