import os.path
from dataclasses import dataclass
from jinja2 import Environment, PackageLoader, select_autoescape
from typing import Literal, Optional


@dataclass
class BlindAndUnblindDir:
    blind: str
    unblind: str


@dataclass(kw_only=True)
class Row:
    """The target per column."""

    name: Optional[str] = None
    description: Optional[str] = None
    by_column: dict[
        str, Optional[str]
    ]  # for inline kind this is the file content not the path


@dataclass(kw_only=True)
class Section:
    """A section contains multiple rows all of the same kind."""

    name: Optional[str] = None
    named_rows: bool = False
    kind: Literal["image", "link", "inline"]
    rows: list[Row]


@dataclass(kw_only=True)
class Chapter:
    """A chapter is a list of sections for the same columns."""

    name: Optional[str] = None
    columns: list[str]
    sections: list[Section]


@dataclass(kw_only=True)
class Report:
    name: str
    chapters: list[Chapter]


def render_cohorts_report(report: Report, out_path: str):
    env = Environment(
        loader=PackageLoader("agr.gbs_prism"), autoescape=select_autoescape()
    )
    template = env.get_template("report.html.jinja")
    with open(out_path, "w") as out_f:
        _ = out_f.write(template.render(report=report))


# def render_peacock_report(report: Report, out_path: str):
#     env = Environment(
#         loader=PackageLoader("agr.gbs_prism"), autoescape=select_autoescape()
#     )
#     template = env.get_template("peacock_report.html.jinja")
#     with open(out_path, "w") as out_f:
#         _ = out_f.write(
#             template.render(
#                 name=report.name,
#                 cohorts=report.cohorts,
#                 sections=report.sections,
#             )
#         )


def make_cohorts_report(
    title: str,
    cohort_target_dirs: dict[str, BlindAndUnblindDir],
    make_targets_relative_to: Optional[str] = None,
) -> Report:
    """Create report, target dir for a cohort is the one containing KGD as a subdirectory."""
    return Report(
        name=title,
        chapters=[
            Chapter(
                columns=sorted(cohort_target_dirs.keys()),
                sections=[
                    Section(
                        name="KGD (plots)",
                        named_rows=True,
                        kind="image",
                        rows=[
                            Row(
                                name="KGD/%s" % name,
                                by_column={
                                    cohort: _blind_relpath_or_none(
                                        cohort_target_dir,
                                        os.path.join("KGD", name),
                                        make_targets_relative_to,
                                    )
                                    for (
                                        cohort,
                                        cohort_target_dir,
                                    ) in cohort_target_dirs.items()
                                },
                                description=narration,
                            )
                            for (name, narration) in _KGD_PLOTS_WITH_NARRATION
                        ],
                    ),
                    Section(
                        name="KGD (output file links)",
                        kind="link",
                        rows=[
                            Row(
                                by_column={
                                    cohort: _blind_or_unblind_relpath_or_none(
                                        cohort_target_dir,
                                        os.path.join("KGD", name),
                                        make_targets_relative_to,
                                    )
                                    for (
                                        cohort,
                                        cohort_target_dir,
                                    ) in cohort_target_dirs.items()
                                },
                            )
                            for name in _KGD_TEXT_FILES
                        ],
                    ),
                    Section(
                        name="Hapmap files",
                        kind="link",
                        rows=[
                            Row(
                                by_column={
                                    cohort: _unblind_relpath_or_none(
                                        cohort_target_dir,
                                        os.path.join("hapMap", name),
                                        make_targets_relative_to,
                                    )
                                    for (
                                        cohort,
                                        cohort_target_dir,
                                    ) in cohort_target_dirs.items()
                                },
                            )
                            for name in _HAPMAP_FILES
                        ],
                    ),
                ],
            )
        ],
    )


# def make_peacock_report() -> Report:
#     pass


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

_KGD_TEXT_FILES = [
    "GHW05.csv",
    "GHW05-Inbreeding.csv",
    "GHW05-long.csv",
    "GHW05-pca_metadata.tsv",
    "GHW05-pca_vectors.tsv",
    "GHW05-PC.csv",
    "GHW05.RData.blinded",
    "GHW05.vcf",
    "HeatmapOrderHWdgm.05.csv",
    "HeatmapOrderHWdgm.05.csv.blinded",
    "PCG5HWdgm.05.pdf.blinded",
    "SampleStats.csv",
    "SampleStats.csv.blinded",
    "seqID.csv",
    "seqID.csv.blinded",
]

_HAPMAP_FILES = ["HapMap.hmc.txt", "HapMap.fas.txt"]


def _relpath_or_none(path: str, relbase: Optional[str]) -> Optional[str]:
    return os.path.relpath(path, relbase) if os.path.exists(path) else None


def _blind_relpath_or_none(
    cohort_target: BlindAndUnblindDir, target_relpath: str, relbase: Optional[str]
) -> Optional[str]:
    path = os.path.join(cohort_target.blind, target_relpath)
    return _relpath_or_none(path, relbase)


def _unblind_relpath_or_none(
    cohort_target: BlindAndUnblindDir, target_relpath: str, relbase: Optional[str]
) -> Optional[str]:
    path = os.path.join(cohort_target.unblind, target_relpath)
    return _relpath_or_none(path, relbase)


def _blind_or_unblind_relpath_or_none(
    cohort_target: BlindAndUnblindDir,
    annotated_target_relpath: str,
    relbase: Optional[str],
) -> Optional[str]:
    """This is a bit gross, but it looks for a blinded suffix on the path, and in this case uses the blind path."""
    if annotated_target_relpath.endswith(".blinded"):
        target_relpath = annotated_target_relpath.removesuffix(".blinded")
        path = os.path.join(cohort_target.blind, target_relpath)
    else:
        target_relpath = annotated_target_relpath
        path = os.path.join(cohort_target.unblind, target_relpath)

    return _relpath_or_none(path, relbase)
