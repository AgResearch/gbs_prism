#!/usr/bin/env python


import os.path

header1 = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
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


footer1 = """
</body>
</html>
"""


def make_clientcohort_page(
    base_dir: str,
    cohort: str,
    out_path: str,
    title_prefix: str = "",  # allows for "filtered "
    kgd_subfolder_name: str = "KGD",  # allows for filtered_KGD in case we ever do that
    hapmap_subfolder_name: str = "hapMap",  # allows for filtered_KGD in case we ever do that
):
    """
    create a client oriented html document for each cohort of
    a gbs run (or for a specified cohort foilder) , which presents the various plots generated , and
    has links to text output. Its also calls utilities to make a pdf and
    marshall the output to be sent.
    """

    file_group_iter = (
        ("KGD (plots)", "image"),
        ("KGD (text file links)", "link"),
        ("Hapmap files", "link"),
    )
    file_iters = {
        "KGD (plots)": [
            os.path.join(kgd_subfolder_name, item)
            for item in [
                "AlleleFreq.png",
                "CallRate.png",
                "Co-call-HWdgm.05.png",
                "Co-call-.png",
                "finplot.png",
                "GcompareHWdgm.05.png",
                "Gcompare.png",
                "Gdiagdepth.png",
                "GHWdgm.05diagdepth.png",
                "InbCompare.png",
                "Heatmap-G5HWdgm.05.png",
                "HWdisMAFsig.png",
                "MAFHWdgm.05.png",
                "MAF.png",
                "PC1v2G5HWdgm.05.png",
                "SampDepthCR.png",
                "SampDepthHist.png",
                "SampDepth.png",
                "SampDepth-scored.png",
                "SNPCallRate.png",
                "SNPDepthHist.png",
                "SNPDepth.png",
                "X2star-QQ.png",
                "PlateDepth.png",
                "PlateInb.png",
                "SubplateDepth.png",
                "SubplateInb.png",
            ]
        ],
        "KGD (text file links)": [
            os.path.join(kgd_subfolder_name, item)
            for item in [
                "GHW05.csv",
                "GHW05-Inbreeding.csv",
                "GHW05-long.csv",
                "GHW05-pca_metadata.tsv",
                "GHW05-pca_vectors.tsv",
                "GHW05-PC.csv",
                "GHW05.RData",
                "GHW05.vcf",
                "HeatmapOrderHWdgm.05.csv",
                "HeatmapOrderHWdgm.05.csv.blinded",
                "PCG5HWdgm.05.pdf",
                "SampleStats.csv",
                "SampleStats.csv.blinded",
                "seqID.csv",
                "seqID.csv.blinded",
            ]
        ],
        "Hapmap files": [
            os.path.join(hapmap_subfolder_name, item)
            for item in ["HapMap.hmc.txt", "HapMap.fas.txt"]
        ],
    }

    narratives = {
        "InbCompare.png": """
Check clumpify normalisation (deduplication) by comparing four estimates of inbreeding: a) production estimate
 b) adjust using fitted beta-binomial (bb) c) sampling one read per lane to remove any duplication effect (used to fit bb)
 d) treat two lanes as two individuals. If the points are below the line in the first column (a .v. b,c,d), or alpha
 is low, our normalisation may not be aggressive enough, as production inbreeding estimate is thus higher than these other
 three methods (each of which should provide a robust estimate of inbreeding, even with un-normalised data)
""",
        "AlleleFreq.png": """
Comparisons SNP reference allele frequencies calculated 3 different ways: 1) after naively converting to genotypes, 2) based on allele counts (without any adjustment for multiple counts of the same allele), 3) as given by UNEAK (the same as method 2).
""",
        "CallRate.png": """
Histogram of call rate (proportion of SNPs scored) for each sample.
""",
        "Co-call-HWdgm.05.png": """
Shows the co-call distribution (see Co-call-.png) after applying the Hardy-Weinberg filter to SNPs and combining lanes (if relevant).
""",
        "Co-call-.png": """
The co-call plot shows the distribution (over all possible pairs) of the proportion of SNPs called in a pair of individuals.
Bimodality may indicate that the samples belong to 2+ genetically divergent clusters (low co-call rate for pairs from different clusters)
""",
        "finplot.png": """
A finplot shows raw Hardy-Weinberg disequilibrium (PAA - pA^2) against MAF for each SNP. 
SNPs near the upper border tend to be mainly homozygous. This is often because they have low depth (perhaps only one allele observed).
SNPs near the lower border tend to be mainly heterozygous and may often represent duplicated regions erroneously treated as one region. 
The Hardy-Weinberg filter, HWdgm.05 (Hardy-Weinberg disequilibium > -0.05) used in some analyses removes these heterozygous SNPs.
""",
        "Gcompare.png": """
Comparisons of different methods for calculating off-diagonals of the GRM. G5=KGD method, G3=KGD with single allele per genotype, G1=unadjusted (biased towards 0).
""",
        "GcompareHWdgm.05.png": """
Same as Gcompare.png plot but using only those SNPs passing the Hardy-Weinberg filter and combining lanes (if relevant)
""",
        "SampDepthHist.png": """
Distribution of sample depths. If it is not roughly unimodal, there may be contamination or a mix of different species or breeds. Also, some downstream
 pipelines use a sample-depth cutoff to filter the data, which could be confused by a multi-modal sample-depth distribution.
""",
        "Gdiagdepth.png": """
In theory self-relatedness estimated from GBS data should be uncorrelated with sample depth, so there should be neither negative nor positive trend
 in this plot. A negatively sloping trend has been nick-named a slippery slope, and means something is not quite right somewhere (with either the make-up of the original sample
 -e.g. some kind of contamination, or the enzyme digest, or size selection, or sequencing, or downstream processing). If they persist, slippery slopes need to be investigated and
 resolved
""",
        "GHWdgm.05diagdepth.png": """
This is similar to the Gdiagdepth.png plot, but 1) combining lanes (if relevant) and 2) based on a smaller set of SNPs (net of the Hardy-Weinberg filter), which eliminates some potential sources of
 correlation between self-relatedness estimates and sample depth. So this plot should exhibit less than (or the same) correlation as that plot. 
""",
        "Heatmap-G5HWdgm.05.png": """
Heatmap representation of the G5 GRM.
Relatedness values are coloured from white to red (lowest to highest relatedness). Samples are ordered by a dendrogram from hierarchically clustering a distance matrix of the GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        "HWdisMAFsig.png": """
SNPs plotted as in finplot.png but coloured by an approximate depth-adjusted significance value.
""",
        "MAF.png": """
MAF distribution. Diverse populations tend to have a peak at low values of MAF.
""",
        "MAFHWdgm.05.png": """
MAF distribution of Hardy-Weinberg filtered SNPs after combining lanes (if relevant)
""",
        "PC1v2G5HWdgm.05.png": """
Principal components plot (1st 2 coordinates) of samples, based on the G5 GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        "SampDepthCR.png": """
Plot of depth vs call rate for samples. This is usually a fairly tight upwardly curving line.
""",
        "SampDepthHist.png": """
Histogram of sample depths. This is usually unimodal. 
""",
        "SampDepth.png": """
Plot of mean vs median sample depth.
""",
        "SampDepth-scored.png": """
Plot of mean sample depth for SNPs with at least one read for the sample against the mean sample depth including all SNPs.
""",
        "SNPCallRate.png": """
Histogram of the proportion of samples called for a SNP. There is usually a peak at a high value and tails off to the left.
""",
        "SNPDepthHist.png": """
Histogram of mean SNP depth. There are often a few SNPs with extremely high depth, while most SNPs have relatively low depth. 
The SNPdepth.png plot has SNP depth log-transformed to show the distribution more clearly.
""",
        "SNPDepth.png": """
Plot of SNP call rate against (log-transformed) SNP depth. Usually a S-shaped band. 
High depth low call rate SNPs may indicate diverse populations (some SNPs only seen in a subset) (and/or possibly size selection variation?)
""",
        "X2star-QQ.png": """
Quantile-quantile plot of approximate depth-adjusted Hardy-Weinberg test statistic for each SNP. A 1-1 line indicates the theoretical distribution holds. 
A higher sloped straight line suggests some population structure. SNPs that plot higher than a straight line through the majority of SNPs may indicate SNPs that do not behave in a Mendelian fashion.
""",
        "PlateDepth.png": """
Plot of mean sample depth by plate position. Patterns of depth variation may represent problems with sample handling.
""",
        "PlateInb.png": """
Plot of estimated inbreeding by plate position. Patterns of inbreeding variation may represent problems with sample handling.
""",
        "SubplateDepth.png": """
The same as PlateDepth.png but with a different colour gradient for each subplate within the main plate.
""",
        "SubplateInb.png": """
The same as PlateInb.png but with a different colour gradient for each subplate within the main plate.
""",
        "GUSbase_comet.jpg": """
Plot to assess the validity of the binomial model for read count data generated using high-throughput sequencing technology. 
SNPs tracking an intermediate slope (observed) may be due to non-diploid genome.  A downward diagonal streak (expected) is due to an internal cutoff and is associated with the presence of high depth SNPs
""",
    }

    manifest_path = "%s.manifest" % out_path
    base_relpath = os.path.relpath(base_dir, out_path)

    with open(out_path, "w") as out_f:

        with open(manifest_path, "w") as manifest_f:

            _ = manifest_f.write("%s\n" % out_path)
            _ = manifest_f.write("%s" % manifest_path)

            _ = out_f.write(header1 % {"title": "%sKGD" % title_prefix})

            for file_group, file_type in file_group_iter:
                # output overall header for file group
                _ = out_f.write("<h2> %s </h2>\n" % file_group)
                # output cohort column headings
                _ = out_f.write(
                    f"""<table width=90% align=center>
<tr>
<td> <h4> Name </h4> </td>
{"\n".join(["<td><h4> %s </h4></td>" % cohort for cohort in [cohort]])}
</tr>
"""
                )
                for file_name in file_iters[file_group]:

                    _ = out_f.write("<tr><td>%s</td>\n" % file_name)
                    file_path = os.path.join(base_dir, file_name)
                    file_relpath = os.path.join(base_relpath, file_name)
                    _ = manifest_f.write("%s\n" % file_relpath)
                    if file_type == "image":
                        if os.path.isfile(file_path):
                            if os.path.basename(file_name) in narratives:
                                image_title = '"%s (%s)"' % (
                                    file_relpath,
                                    narratives[os.path.basename(file_name)].replace(
                                        "\n", ""
                                    ),
                                )
                            else:
                                image_title = file_relpath
                            _ = out_f.write(
                                "<td> <img src=%s title=%s height=300 width=300/> </td>\n\n"
                                % (file_relpath, image_title)
                            )

                        else:
                            _ = out_f.write("<td> unavailable </td>\n\n")
                    elif file_type == "link":

                        if os.path.isfile(file_path):
                            _ = out_f.write(
                                "<td width=300> <a href=%s target=%s> %s </a></td>\n\n"
                                % (file_relpath, file_name, file_relpath)
                            )
                        else:
                            _ = out_f.write("<td width=300> unavailable </td>\n\n")
                    _ = out_f.write("</tr>\n\n")
                _ = out_f.write("</table>\n\n")
            _ = out_f.write("%s\n" % footer1)
