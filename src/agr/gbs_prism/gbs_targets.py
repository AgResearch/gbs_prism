from dataclasses import dataclass
import logging
import os
import tempfile

from agr.util import StdioRedirect
from agr.util.legacy import sanitised_realpath
from agr.gquery import GQuery, Predicates

from .enzyme_sub import enzyme_sub_for_uneak
from .gbs_target_spec import Cohort, GbsTargetSpec, CohortTargetSpec
from .paths import GbsPaths
from .types import flowcell_id

logger = logging.getLogger(__name__)


@dataclass
class GbsConfig:
    run_name: str
    paths: GbsPaths
    alignment_sample_moniker: str
    aligner: str  # e.g. bwa
    alignment_moniker: str  # e.g. B10


class GbsTargets:
    """Cohorts and post-processing parameters which define the targets for stage 2."""

    def __init__(self, config: GbsConfig, spec: GbsTargetSpec):
        self._config = config
        self._spec = spec
        self._cohorts = dict(
            [
                (
                    cohort_name,
                    CohortTargets(Cohort.parse(cohort_name), self._config, cohort_spec),
                )
                for library_spec in self._spec.libraries.values()
                for (cohort_name, cohort_spec) in library_spec.cohorts.items()
            ]
        )

    @property
    def cohorts(self) -> dict[str, "CohortTargets"]:
        return self._cohorts

    @property
    def paths(self):
        return [
            target for cohort in self._cohorts.values() for target in cohort.paths
        ] + self._global_paths

    @property
    def _global_paths(self):
        return [os.path.join(self._config.paths.run_root, "html", "peacock.html")]

    @property
    def local_fastq_links(self):
        return [
            target
            for cohort in self._cohorts.values()
            for target in cohort.local_fastq_links
        ]

    def make_dirs(self):
        for cohort_name in self._cohorts.keys():
            self._config.paths.make_cohort_dirs(str(cohort_name))

    def create_local_fastq_links(self):
        for cohort_name, spec in self._spec.cohorts.items():
            for fastq_basename, fastq_link in spec.fastq_links.items():
                # create the same links in both blind and unblind directories
                for blind in [False, True]:
                    os.symlink(
                        sanitised_realpath(fastq_link),
                        os.path.join(
                            self._config.paths.fastq_link_dir(
                                str(cohort_name), blind=blind
                            ),
                            fastq_basename,
                        ),
                    )


class CohortTargets:
    def __init__(self, name: Cohort, config: GbsConfig, spec: CohortTargetSpec):
        self._name = name
        self._spec = spec
        self._config = config

    @property
    def local_fastq_links(self) -> list[str]:
        return [
            os.path.join(
                self._config.paths.fastq_link_dir(str(self._name), blind=blind),
                fastq_basename,
            )
            for fastq_basename in self._spec.fastq_links.keys()
            for blind in [False, True]
        ]

    @property
    def paths(self) -> list[str]:
        """Cohort target paths for SnakeMake."""

        bwa_sampled = [
            os.path.join(
                self._config.paths.bwa_mapping_dir(str(self._name)),
                "%s.fastq.%s.fastq"
                % (fastq_basename, self._config.alignment_sample_moniker),
            )
            for fastq_basename in self._spec.fastq_links.keys()
        ]

        bwa_sampled_trimmed = [
            "%s.trimmed.fastq" % sampled.removesuffix(".fastq")
            for sampled in bwa_sampled
        ]

        bwa_bam = [
            "%s.bwa.%s.%s.bam"
            % (trimmed, bwa_reference_moniker, self._config.alignment_moniker)
            for trimmed in bwa_sampled_trimmed
            for bwa_reference_moniker in self._spec.alignment_references.keys()
        ]

        bwa_sai = ["%s.sai" % bam_file.removesuffix(".bam") for bam_file in bwa_bam]

        bwa_stats = ["%s.stats" % bam_file.removesuffix(".bam") for bam_file in bwa_bam]

        def suffixed_target(suffix: str) -> str:
            # TODO these names are quite clunky, perhaps remove the pointless `run` prefix later
            return "%s/%s.%s.%s" % (
                self._config.paths.run_root,
                self._config.run_name,
                self._name,
                suffix,
            )

        # note that some targets which were previsouly dumped into the filesystem are now simply
        # returned as lists, namely: method, bwa_references
        suffixed_targets = [
            suffixed_target(suffix) for suffix in ["key", "gbsx.key", "unblind.sed"]
        ]

        # blind targets are those with a qc- ID in place of a sample ID.
        # and are kept separated in a `blind` subdirectory of the cohort
        blind_targets = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                "blind",
                target,
            )
            for target in [
                "tagCounts_parts/part1",
                "tagCounts.done",
                "mergedTagCounts.done",
                "tagPair.done",
                "tagsByTaxa.done",
                "mapInfo.done",
                "hapMap.done",
                "TagCount.csv",
                "KGD/SampleStats.csv",
                "KGD/GUSbase_comet.jpg",
            ]
        ]

        tags_summary_targets = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                target,
            )
            for target in [
                "tags_reads_summary.txt",
                "tags_reads_cv.txt",
            ]
        ]

        unblinded_targets = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                target,
            )
            for target in
            # from unblind script
            [
                "TagCount.csv",
                # "TagCountsAndSampleStats.csv",
                # TODO soon
                # "%s.KGD_tassel3.KGD.stdout" % self._name,
                # "KGD/GHW05.csv",
                # "KGD/GHW05-Inbreeding.csv",
                # "KGD/GHW05-long.csv",
                # "KGD/GHW05-PC.csv",
                # "KGD/HeatmapOrderHWdgm.05.csv",
                # "KGD/SampleStats.csv",
                # "KGD/SampleStatsRawCombined.csv",
                # "KGD/SampleStatsRaw.csv",
                # "KGD/seqID.csv",
                # "KGD/GHW05-pca_metadata.tsv",
                # "KGD/GHW05-pca_vectors.tsv",
                # "KGD/GHW05.vcf",
                # "hapMap/HapMap.hmc.txt",
                # "hapMap/HapMap.hmp.txt",
                # TODO later
                # "blast/locus*.txt",
                # "blast/locus*.dat",
                # "blast/taxonomy*.txt",
                # "blast/taxonomy*.dat",
                # "blast/frequency_table.txt",
                # "blast/information_table.txt",
                # TODO when we have cohort kmer_analysis:
                # "kmer_analysis/*.txt",
                # "kmer_analysis/*.dat",
                # "allkmer_analysis/*.txt",
                # "allkmer_analysis/*.dat",
            ]
        ]

        other_targets = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                target,
            )
            for target in ["dedupe_summary.txt"]
        ]

        paths = (
            self.local_fastq_links
            + suffixed_targets
            + bwa_sampled
            + bwa_sampled_trimmed
            + bwa_sai
            + bwa_bam
            + bwa_stats
            + blind_targets
            + tags_summary_targets
            + unblinded_targets
            # + other_targets
        )
        # logger.debug("targets for cohort %s:\n%s" % (self._name, "\n".join(paths)))
        return paths

    def get_keyfile_for_tassel(self, out_path: str):
        fcid = flowcell_id(self._config.run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                g = GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self._name.enzyme,
                        gbs_cohort=self._name.gbs_cohort,
                        columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link",
                    ),
                    items=[self._name.libname],
                )
                logger.info(g)
                g.run()

            _ = tmp_f.seek(0)
            with open(out_path, "w") as keyfile_f:
                for line in tmp_f:
                    _ = keyfile_f.write(enzyme_sub_for_uneak(line))

    def get_gbsx_keyfile(self, out_path: str):
        fcid = flowcell_id(self._config.run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self._name.enzyme,
                        gbs_cohort=self._name.gbs_cohort,
                        columns="qc_sampleid as sample,Barcode,Enzyme",
                    ),
                    items=[self._name.libname],
                ).run()

    def get_unblind_script(self, out_path: str):
        fcid = flowcell_id(self._config.run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self._name.enzyme,
                        gbs_cohort=self._name.gbs_cohort,
                        unblinding=True,
                        columns="qc_sampleid,sample",
                        noheading=True,
                    ),
                    items=[self._name.libname],
                ).run()
