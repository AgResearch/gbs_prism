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

def get_cohorts(options):
    BASEDIR=options["basedir"]    
    # cohorts are idenitified as subfolders of the run folder that
    # * are not tardis working folders (i.e. have names starting with tardis
    # * are of like SQ0775.all.TILAPIA.PstI-MspI
    #   - i.e. library.qc-cohort.gbs-cohort.enzyme
    run_folder=os.path.join(BASEDIR, options["run_folder"])
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
    BASEDIR=options["basedir"]   # e.g. /bifo/scratch/2023_illumina_sequencing_a/postprocessing/gbs    
    stats = {
        "found file count" : 0,
        "no file count" : 0,
        "no sample count" : 0
    }

    file_group_iter = (  ("KGD (plots)", "image"), ("KGD (text file links)", "link"), ("Hapmap files", "link" ) )
    file_iters = {
        "KGD (plots)" : ['AlleleFreq.png', 'CallRate.png', 'Co-call-HWdgm.05.png', 'Co-call-.png', 'finplot.png', \
                         'GcompareHWdgm.05.png', 'Gcompare.png', 'Gdiagdepth.png', 'GHWdgm.05diagdepth.png', \
                         'InbCompare.png','Heatmap-G5HWdgm.05.png', 'HWdisMAFsig.png', \
                         'MAFHWdgm.05.png', 'MAF.png', 'PC1v2G5HWdgm.05.png', 'SampDepthCR.png', 'SampDepthHist.png', \
                         'SampDepth.png', 'SampDepth-scored.png', 'SNPCallRate.png', 'SNPDepthHist.png', 'SNPDepth.png', \
                         'X2star-QQ.png', 'PlateDepth.png', 'PlateInb.png', 'SubplateDepth.png', 'SubplateInb.png'],
        "KGD (text file links)" : ['GHW05.csv', 'GHW05-Inbreeding.csv', 'GHW05-long.csv', 'GHW05-pca_metadata.tsv', 'GHW05-pca_vectors.tsv', 'GHW05-PC.csv', 'GHW05.RData', 'GHW05.vcf', 'HeatmapOrderHWdgm.05.csv', 'HeatmapOrderHWdgm.05.csv.blinded', 'PCG5HWdgm.05.pdf', 'SampleStats.csv', 'SampleStats.csv.blinded', 'seqID.csv', 'seqID.csv.blinded'],
        "Hapmap files" : ['HapMap.hmc.txt','HapMap.fas.txt']
    }
    file_iters["KGD (plots)"] = [ os.path.join(options["kgd_subfolder_name"], item) for item in file_iters["KGD (plots)"] ]
    file_iters["KGD (text file links)"] = [ os.path.join(options["kgd_subfolder_name"], item) for item in file_iters["KGD (text file links)"] ]
    file_iters["Hapmap files"] = [ os.path.join(options["hapmap_subfolder_name"], item) for item in file_iters["Hapmap files"] ]

    narratives = {
        'InbCompare.png' : """
Check clumpify normalisation (deduplication) by comparing four estimates of inbreeding: a) production estimate
 b) adjust using fitted beta-binomial (bb) c) sampling one read per lane to remove any duplication effect (used to fit bb)
 d) treat two lanes as two individuals. If the points are below the line in the first column (a .v. b,c,d), or alpha
 is low, our normalisation may not be aggressive enough, as production inbreeding estimate is thus higher than these other
 three methods (each of which should provide a robust estimate of inbreeding, even with un-normalised data)
""",
        'AlleleFreq.png' : """
Comparisons SNP reference allele frequencies calculated 3 different ways: 1) after naively converting to genotypes, 2) based on allele counts (without any adjustment for multiple counts of the same allele), 3) as given by UNEAK (the same as method 2).
""",
        'CallRate.png' : """
Histogram of call rate (proportion of SNPs scored) for each sample.
""",
        'Co-call-HWdgm.05.png' : """
Shows the co-call distribution (see Co-call-.png) after applying the Hardy-Weinberg filter to SNPs and combining lanes (if relevant).
""",
        'Co-call-.png' : """
The co-call plot shows the distribution (over all possible pairs) of the proportion of SNPs called in a pair of individuals.
Bimodality may indicate that the samples belong to 2+ genetically divergent clusters (low co-call rate for pairs from different clusters)
""",
        'finplot.png' : """
A finplot shows raw Hardy-Weinberg disequilibrium (PAA - pA^2) against MAF for each SNP. 
SNPs near the upper border tend to be mainly homozygous. This is often because they have low depth (perhaps only one allele observed).
SNPs near the lower border tend to be mainly heterozygous and may often represent duplicated regions erroneously treated as one region. 
The Hardy-Weinberg filter, HWdgm.05 (Hardy-Weinberg disequilibium > -0.05) used in some analyses removes these heterozygous SNPs.
""",
        'Gcompare.png' : """
Comparisons of different methods for calculating off-diagonals of the GRM. G5=KGD method, G3=KGD with single allele per genotype, G1=unadjusted (biased towards 0).
""",
        'GcompareHWdgm.05.png' : """
Same as Gcompare.png plot but using only those SNPs passing the Hardy-Weinberg filter and combining lanes (if relevant)
""",
        'SampDepthHist.png' : """
Distribution of sample depths. If it is not roughly unimodal, there may be contamination or a mix of different species or breeds. Also, some downstream
 pipelines use a sample-depth cutoff to filter the data, which could be confused by a multi-modal sample-depth distribution.
""",
        'Gdiagdepth.png' : """
In theory self-relatedness estimated from GBS data should be uncorrelated with sample depth, so there should be neither negative nor positive trend
 in this plot. A negatively sloping trend has been nick-named a slippery slope, and means something is not quite right somewhere (with either the make-up of the original sample
 -e.g. some kind of contamination, or the enzyme digest, or size selection, or sequencing, or downstream processing). If they persist, slippery slopes need to be investigated and
 resolved
""",
        'GHWdgm.05diagdepth.png' : """
This is similar to the Gdiagdepth.png plot, but 1) combining lanes (if relevant) and 2) based on a smaller set of SNPs (net of the Hardy-Weinberg filter), which eliminates some potential sources of
 correlation between self-relatedness estimates and sample depth. So this plot should exhibit less than (or the same) correlation as that plot. 
""",
        'Heatmap-G5HWdgm.05.png' : """
Heatmap representation of the G5 GRM.
Relatedness values are coloured from white to red (lowest to highest relatedness). Samples are ordered by a dendrogram from hierarchically clustering a distance matrix of the GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        'HWdisMAFsig.png' : """
SNPs plotted as in finplot.png but coloured by an approximate depth-adjusted significance value.
""",
        'MAF.png' : """
MAF distribution. Diverse populations tend to have a peak at low values of MAF.
""",
        'MAFHWdgm.05.png' : """
MAF distribution of Hardy-Weinberg filtered SNPs after combining lanes (if relevant)
""",
        'PC1v2G5HWdgm.05.png' : """
Principal components plot (1st 2 coordinates) of samples, based on the G5 GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        'SampDepthCR.png' : """
Plot of depth vs call rate for samples. This is usually a fairly tight upwardly curving line.
""",
        'SampDepthHist.png' : """
Histogram of sample depths. This is usually unimodal. 
""",
        'SampDepth.png' : """
Plot of mean vs median sample depth.
""",
        'SampDepth-scored.png' : """
Plot of mean sample depth for SNPs with at least one read for the sample against the mean sample depth including all SNPs.
""",
        'SNPCallRate.png' : """
Histogram of the proportion of samples called for a SNP. There is usually a peak at a high value and tails off to the left.
""",
        'SNPDepthHist.png' : """
Histogram of mean SNP depth. There are often a few SNPs with extremely high depth, while most SNPs have relatively low depth. 
The SNPdepth.png plot has SNP depth log-transformed to show the distribution more clearly.
""",
        'SNPDepth.png' : """
Plot of SNP call rate against (log-transformed) SNP depth. Usually a S-shaped band. 
High depth low call rate SNPs may indicate diverse populations (some SNPs only seen in a subset) (and/or possibly size selection variation?)
""",
        'X2star-QQ.png' : """
Quantile-quantile plot of approximate depth-adjusted Hardy-Weinberg test statistic for each SNP. A 1-1 line indicates the theoretical distribution holds. 
A higher sloped straight line suggests some population structure. SNPs that plot higher than a straight line through the majority of SNPs may indicate SNPs that do not behave in a Mendelian fashion.
""",
        'PlateDepth.png' : """
Plot of mean sample depth by plate position. Patterns of depth variation may represent problems with sample handling.
""",
        'PlateInb.png' : """
Plot of estimated inbreeding by plate position. Patterns of inbreeding variation may represent problems with sample handling.
""",
        'SubplateDepth.png' : """
The same as PlateDepth.png but with a different colour gradient for each subplate within the main plate.
""",
        'SubplateInb.png' : """
The same as PlateInb.png but with a different colour gradient for each subplate within the main plate.
""",
        'GUSbase_comet.jpg' : """
Plot to assess the validity of the binomial model for read count data generated using high-throughput sequencing technology. 
SNPs tracking an intermediate slope (observed) may be due to non-diploid genome.  A downward diagonal streak (expected) is due to an internal cutoff and is associated with the presence of high depth SNPs
"""       
    } 
    
    
    
    
    #print "DEBUG : calling get_cohorts"
    if options["cohort_folder" ] is not None:
        cohorts = [ options["cohort_folder" ] ]
        out_stream_filename = options["output_filename"]
        out_manifest_filename = "%s.manifest"%options["output_filename"]
    else:
        cohorts = get_cohorts(options)

        
                        
        
    for cohort in cohorts:

        if options["cohort_folder" ] is None:
            out_stream_filename = os.path.join(BASEDIR, options["run_folder"], "html", cohort, options["output_filename"])
            out_manifest_filename = os.path.join(BASEDIR, options["run_folder"], "html", cohort, "%s.manifest"%options["output_filename"])

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
                        if options["run_folder"] is not None:
                            file_path = os.path.join(BASEDIR, options["run_folder"], cohort, file_name)
                        else:
                            file_path = os.path.join(cohort, file_name)
                            

                        if file_type == "image":
                            image_relpath=file_name

                            print >> out_manifest, image_relpath

                            if os.path.isfile(file_path):
                                title = image_relpath
                                if os.path.basename(file_name) in narratives:
                                    title = "\"%s (%s)\""%(image_relpath, narratives[os.path.basename(file_name)].replace('\n',''))
                                print >> out_stream, "<td> <img src=%s title=%s height=300 width=300/> </td>\n"%(image_relpath, title)
                               
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
    parser.add_argument('-r', '--run_folder' , dest='run_folder', default = None, type=str, help="run name")
    parser.add_argument('-t', '--title' , dest='title', default = None, type=str, help="title")    
    parser.add_argument('-H', '--image_height' , dest='image_height', default=300, type=int, help="image height")
    parser.add_argument('-W', '--image_width' , dest='image_width', default=300, type=int, help="image width")
    parser.add_argument('-o', '--output_filename' , dest='output_filename', default="peacock.html", type=str, help="name of output file")
    parser.add_argument('-U', '--hapmap_subfolder_name' , dest='hapmap_subfolder_name', default="hapMap", type=str, help="name of hapmap subfolder")
    parser.add_argument('-K', '--kgd_subfolder_name' , dest='kgd_subfolder_name', default="KGD", type=str, help="name of KGD sub-folder name")
    parser.add_argument('-b', '--basedir' , dest='basedir', default="/dataset/2023_illumina_sequencing_a/scratch/postprocessing/gbs", type=str, help="base dir of original output")
    
    
    
    args = vars(parser.parse_args())

    if args["run_folder"] is None and args["cohort_folder"] is None:
        raise Exception("must specify either run folder or a cohort folder")

    return args


def main():

    options = get_options()
    print options 
    generate_run_plot(options)

    
if __name__ == "__main__":
   main()



        

