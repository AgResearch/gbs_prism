#!/usr/bin/env python


#
# this script creates a client oriented html document for each cohort of
# a gbs run (or for a specified cohort foilder) , which presents the various plots generated , and
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
Results for %(title)s
</title>
</head>
<body>
<h1> Results for %(title)s </h1>
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
                     re.search("^\S+\.\S+\.\S+\.\S+$", node) is not None and os.path.isdir(os.path.join(run_folder, node)) and
                     re.search("^OLD_", node) is None]
    
    return cohort_folders
    
    
def generate_run_plot(options):
    stats = {
        "found file count" : 0,
        "no file count" : 0,
        "no sample count" : 0
    }

    file_group_iter = (  ("KGD (plots)", "image"), ("KGD (text file links)", "link"), ("Hapmap files", "link" ) )
    file_iters = {
        "KGD (plots)" : ['AlleleFreq.png', 'CallRate.png', 'Co-call-HWdgm.05.png', 'Co-call-.png', 'finplot.png', 'GcompareHWdgm.05.png', 'Gcompare.png', 'Gdiagdepth.png', 'G-diag.png', 'GHWdgm.05diagdepth.png', 'GHWdgm.05-diag.png', 'Heatmap-G5HWdgm.05.png', 'HWdisMAFsig.png', 'LRT-hist.png', 'LRT-QQ.png', 'MAFHWdgm.05.png', 'MAF.png', 'PC1v2G5HWdgm.05.png', 'SampDepthCR.png', 'SampDepthHist.png', 'SampDepth.png', 'SampDepth-scored.png', 'SNPCallRate.png', 'SNPDepthHist.png', 'SNPDepth.png', 'X2star-QQ.png'],
        "KGD (text file links)" : ['GHW05.csv', 'GHW05-Inbreeding.csv', 'GHW05-long.csv', 'GHW05-pca_metadata.tsv', 'GHW05-pca_vectors.tsv', 'GHW05-PC.csv', 'GHW05.RData', 'GHW05.vcf', 'HeatmapOrderHWdgm.05.csv', 'HeatmapOrderHWdgm.05.csv.blinded', 'PCG5HWdgm.05.pdf', 'SampleStats.csv', 'SampleStats.csv.blinded', 'seqID.csv', 'seqID.csv.blinded'],
        "Hapmap files" : ['HapMap.hmc.txt','HapMap.hmp.txt']
    }

    file_iters["KGD (plots)"] = [ os.path.join(options["kgd_subfolder_name"], item) for item in file_iters["KGD (plots)"] ]
    file_iters["KGD (text file links)"] = [ os.path.join(options["kgd_subfolder_name"], item) for item in file_iters["KGD (text file links)"] ]
    file_iters["Hapmap files"] = [ os.path.join(options["hapmap_subfolder_name"], item) for item in file_iters["Hapmap files"] ]
    
    
    
    #print "DEBUG : calling get_cohorts"
    if options["cohort_folder" ] is not None:
        cohorts = [ options["cohort_folder" ] ]
        out_stream_filename = options["output_filename"]
        out_manifest_filename = "%s.manifest"%options["output_filename"]
    else:
        cohorts = get_cohorts(options)

        
                        
        
    for cohort in cohorts:

        if options["cohort_folder" ] is None:
            out_stream_filename = os.path.join(BASEDIR, options["run_name"], "html", cohort, options["output_filename"])
            out_manifest_filename = os.path.join(BASEDIR, options["run_name"], "html", cohort, "%s.manifest"%options["output_filename"])

        print cohort, out_stream_filename, out_manifest_filename


        with open(out_stream_filename,"w") as out_stream:

            with open(out_manifest_filename,"w") as out_manifest:

                print >> out_manifest, options["output_filename"]
                print >> out_manifest, "%s.manifest"%options["output_filename"]

                if options["title"] is None:
                    print >> out_stream, header1%{"title" : cohort}
                else:
                    print >> out_stream, header1%options
                

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
                        if options["run_name"] is not None:
                            file_path = os.path.join(BASEDIR, options["run_name"], cohort, file_name)
                        else:
                            file_path = os.path.join(cohort, file_name)
                            

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
examples :

# for a standard hiseq run 

./make_clientcohort_pages.py -r 181112_D00390_0415_BCD04NANXX -o report.html
key file summary looks like :

run     run_number      lane    samplename      species file_name
140624_D00390_0044_BH9PEBADXX   0044    1       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140624_D00390_0044_BH9PEBADXX   0044    2       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209    1       SQ0008  Deer    140904_D00390_0209_BC4U6YACXX.gbs/SQ0008.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209


# for some custom runs
python ../gbs_prism/make_clientcohort_pages.py -t "Unfiltered run" -o /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI/unfiltered.html /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI
python ../gbs_prism/make_clientcohort_pages.py -U filtered_hapMap -K filtered_KGD -t "Filtered run" -o /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI/filtered.html /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI
python ../gbs_prism/make_clientcohort_pages.py -U discarded_hapMap -K discarded_KGD -t "Filtered run - using discarded tags" -o /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI/discarded.html /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/gbsathon_adapter/PstI-MspI


    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('cohort_folder', nargs='?', type=str, default=None)
    parser.add_argument('-r', '--run_name' , dest='run_name', default = None, type=str, help="run name")
    parser.add_argument('-t', '--title' , dest='title', default = None, type=str, help="title")    
    parser.add_argument('-H', '--image_height' , dest='image_height', default=300, type=int, help="image height")
    parser.add_argument('-W', '--image_width' , dest='image_width', default=300, type=int, help="image width")
    parser.add_argument('-o', '--output_filename' , dest='output_filename', default="peacock.html", type=str, help="name of output file")
    parser.add_argument('-U', '--hapmap_subfolder_name' , dest='hapmap_subfolder_name', default="hapMap", type=str, help="name of hapmap subfolder")
    parser.add_argument('-K', '--kgd_subfolder_name' , dest='kgd_subfolder_name', default="KGD", type=str, help="name of KGD sub-folder name")
    
    
    args = vars(parser.parse_args())

    if args["run_name"] is None and args["cohort_folder"] is None:
        raise Exception("must specify either run name or a cohort folder")

    return args


def main():

    options = get_options()
    print options 
    generate_run_plot(options)

    
if __name__ == "__main__":
   main()



        

