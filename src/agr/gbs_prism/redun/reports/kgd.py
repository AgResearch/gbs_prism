import os.path
from dataclasses import dataclass
from redun import task, File
from typing import Optional

from agr.util.report import (
    Report,
    Chapter,
    Section,
    Row,
    render_report,
)
from agr.redun.tasks.kgd import KgdOutput

from .util import image_or_none, link_or_none

redun_namespace = "agr.gbs_prism.reports"


@dataclass
class KgdTargets:
    kgd_output: KgdOutput
    kgd_text_files_unblind: dict[str, File]
    hap_map_files_unblind: dict[str, File]

    def kgd_output_file(self, name: str) -> Optional[File]:
        """Look in all locations: plots, text files, binary files."""
        BLINDED_SUFFIX = ".blinded"
        blind = name.endswith(BLINDED_SUFFIX)
        basename = name.removesuffix(BLINDED_SUFFIX)
        return (
            self.kgd_output.text_files.get(basename)
            if blind
            else self.kgd_text_files_unblind.get(
                basename,
                self.kgd_output.binary_files.get(
                    basename, self.kgd_output.plot_files.get(basename)
                ),
            )
        )


def kgd_plots_section(cohorts_targets: dict[str, KgdTargets], relbase: str) -> Section:
    KGD_PLOT_WIDTH = 300
    KGD_PLOT_HEIGHT = 300
    return Section(
        name="KGD (plots)",
        named_rows=True,
        rows=[
            Row(
                name="KGD/%s" % name,
                by_column={
                    cohort_name: image_or_none(
                        cohort.kgd_output.plot_files.get(name),
                        relbase,
                        KGD_PLOT_WIDTH,
                        KGD_PLOT_HEIGHT,
                    )
                    for (
                        cohort_name,
                        cohort,
                    ) in cohorts_targets.items()
                },
                description=narration,
            )
            for (name, narration) in _KGD_PLOTS_WITH_NARRATION
        ],
    )


def kgd_links_section(cohorts_targets: dict[str, KgdTargets], relbase: str) -> Section:
    return Section(
        name="KGD (output file links)",
        rows=[
            Row(
                name=f"KGD/{name}",
                by_column={
                    cohort_name: link_or_none(cohort.kgd_output_file(name), relbase)
                    for (cohort_name, cohort) in cohorts_targets.items()
                },
            )
            for name in _KGD_LINKS
        ],
    )


def hap_map_files_section(
    cohorts_targets: dict[str, KgdTargets], relbase: str
) -> Section:
    return Section(
        name="Hapmap files",
        rows=[
            Row(
                name=f"hapMap/{name}",
                by_column={
                    cohort_name: link_or_none(
                        cohort.hap_map_files_unblind[name], relbase
                    )
                    for (cohort_name, cohort) in cohorts_targets.items()
                },
            )
            for name in _HAPMAP_FILES
        ],
    )


@task()
def create_kgd_report(
    title: str,
    cohorts_targets: dict[str, KgdTargets],
    out_path: str,
) -> File:
    """Create report, target dir for a cohort is the one containing KGD as a subdirectory."""
    relbase = os.path.dirname(out_path)
    report = Report(
        name=title,
        chapters=[
            Chapter(
                columns=sorted(cohorts_targets.keys()),
                sections=[
                    kgd_plots_section(
                        cohorts_targets,
                        relbase=relbase,
                    ),
                    kgd_links_section(
                        cohorts_targets,
                        relbase=relbase,
                    ),
                    hap_map_files_section(
                        cohorts_targets,
                        relbase=relbase,
                    ),
                ],
            )
        ],
    )
    render_report(report=report, out_path=out_path)
    return File(out_path)


_KGD_PLOTS_WITH_NARRATION = [
    (
        "AlleleFreq.png",
        """
Comparisons SNP reference allele frequencies calculated 3 different ways: 1) after naively converting to genotypes, 2) based on allele counts (without any adjustment for multiple counts of the same allele), 3) as given by UNEAK (the same as method 2).
""",
    ),
    (
        "CallRate.png",
        """
Histogram of call rate (proportion of SNPs scored) for each sample.
""",
    ),
    (
        "Co-call-HWdgm.05.png",
        """
Shows the co-call distribution (see Co-call-.png) after applying the Hardy-Weinberg filter to SNPs and combining lanes (if relevant).
""",
    ),
    (
        "Co-call-.png",
        """
The co-call plot shows the distribution (over all possible pairs) of the proportion of SNPs called in a pair of individuals.
Bimodality may indicate that the samples belong to 2+ genetically divergent clusters (low co-call rate for pairs from different clusters)
""",
    ),
    (
        "finplot.png",
        """
A finplot shows raw Hardy-Weinberg disequilibrium (PAA - pA^2) against MAF for each SNP. 
SNPs near the upper border tend to be mainly homozygous. This is often because they have low depth (perhaps only one allele observed).
SNPs near the lower border tend to be mainly heterozygous and may often represent duplicated regions erroneously treated as one region. 
The Hardy-Weinberg filter, HWdgm.05 (Hardy-Weinberg disequilibium > -0.05) used in some analyses removes these heterozygous SNPs.
""",
    ),
    (
        "GcompareHWdgm.05.png",
        """
Same as Gcompare.png plot but using only those SNPs passing the Hardy-Weinberg filter and combining lanes (if relevant)
""",
    ),
    (
        "Gcompare.png",
        """
Comparisons of different methods for calculating off-diagonals of the GRM. G5=KGD method, G3=KGD with single allele per genotype, G1=unadjusted (biased towards 0).
""",
    ),
    (
        "Gdiagdepth.png",
        """
In theory self-relatedness estimated from GBS data should be uncorrelated with sample depth, so there should be neither negative nor positive trend
 in this plot. A negatively sloping trend has been nick-named a slippery slope, and means something is not quite right somewhere (with either the make-up of the original sample
 -e.g. some kind of contamination, or the enzyme digest, or size selection, or sequencing, or downstream processing). If they persist, slippery slopes need to be investigated and
 resolved
""",
    ),
    (
        "GHWdgm.05diagdepth.png",
        """
This is similar to the Gdiagdepth.png plot, but 1) combining lanes (if relevant) and 2) based on a smaller set of SNPs (net of the Hardy-Weinberg filter), which eliminates some potential sources of
 correlation between self-relatedness estimates and sample depth. So this plot should exhibit less than (or the same) correlation as that plot. 
""",
    ),
    (
        "InbCompare.png",
        """
Check clumpify normalisation (deduplication) by comparing four estimates of inbreeding: a) production estimate
 b) adjust using fitted beta-binomial (bb) c) sampling one read per lane to remove any duplication effect (used to fit bb)
 d) treat two lanes as two individuals. If the points are below the line in the first column (a .v. b,c,d), or alpha
 is low, our normalisation may not be aggressive enough, as production inbreeding estimate is thus higher than these other
 three methods (each of which should provide a robust estimate of inbreeding, even with un-normalised data)
""",
    ),
    (
        "Heatmap-G5HWdgm.05.png",
        """
Heatmap representation of the G5 GRM.
Relatedness values are coloured from white to red (lowest to highest relatedness). Samples are ordered by a dendrogram from hierarchically clustering a distance matrix of the GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
    ),
    (
        "HWdisMAFsig.png",
        """
SNPs plotted as in finplot.png but coloured by an approximate depth-adjusted significance value.
""",
    ),
    (
        "MAFHWdgm.05.png",
        """
MAF distribution of Hardy-Weinberg filtered SNPs after combining lanes (if relevant)
""",
    ),
    (
        "MAF.png",
        """
MAF distribution. Diverse populations tend to have a peak at low values of MAF.
""",
    ),
    (
        "PC1v2G5HWdgm.05.png",
        """
Principal components plot (1st 2 coordinates) of samples, based on the G5 GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
    ),
    (
        "SampDepthCR.png",
        """
Plot of depth vs call rate for samples. This is usually a fairly tight upwardly curving line.
""",
    ),
    (
        "SampDepthHist.png",
        """
Distribution of sample depths. If it is not roughly unimodal, there may be contamination or a mix of different species or breeds. Also, some downstream
 pipelines use a sample-depth cutoff to filter the data, which could be confused by a multi-modal sample-depth distribution.
""",
    ),
    (
        "SampDepth.png",
        """
Plot of mean vs median sample depth.
""",
    ),
    (
        "SampDepth-scored.png",
        """
Plot of mean sample depth for SNPs with at least one read for the sample against the mean sample depth including all SNPs.
""",
    ),
    (
        "SNPCallRate.png",
        """
Histogram of the proportion of samples called for a SNP. There is usually a peak at a high value and tails off to the left.
""",
    ),
    (
        "SNPDepthHist.png",
        """
Histogram of mean SNP depth. There are often a few SNPs with extremely high depth, while most SNPs have relatively low depth. 
The SNPdepth.png plot has SNP depth log-transformed to show the distribution more clearly.
""",
    ),
    (
        "SNPDepth.png",
        """
Plot of SNP call rate against (log-transformed) SNP depth. Usually a S-shaped band. 
High depth low call rate SNPs may indicate diverse populations (some SNPs only seen in a subset) (and/or possibly size selection variation?)
""",
    ),
    (
        "X2star-QQ.png",
        """
Quantile-quantile plot of approximate depth-adjusted Hardy-Weinberg test statistic for each SNP. A 1-1 line indicates the theoretical distribution holds. 
A higher sloped straight line suggests some population structure. SNPs that plot higher than a straight line through the majority of SNPs may indicate SNPs that do not behave in a Mendelian fashion.
""",
    ),
    (
        "PlateDepth.png",
        """
Plot of mean sample depth by plate position. Patterns of depth variation may represent problems with sample handling.
""",
    ),
    (
        "PlateInb.png",
        """
Plot of estimated inbreeding by plate position. Patterns of inbreeding variation may represent problems with sample handling.
""",
    ),
    (
        "SubplateDepth.png",
        """
The same as PlateDepth.png but with a different colour gradient for each subplate within the main plate.
""",
    ),
    (
        "SubplateInb.png",
        """
The same as PlateInb.png but with a different colour gradient for each subplate within the main plate.
""",
    ),
]

_KGD_LINKS = [
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

_HAPMAP_FILES = ["HapMap.hmc.txt", "HapMap.fas.txt"]
