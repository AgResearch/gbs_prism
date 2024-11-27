from dataclasses import dataclass
import logging
import os
import tempfile

from agr.util import StdioRedirect
from agr.gquery import GQuery, Predicates

from .enzyme_sub import enzyme_sub_for_uneak
from .gbs_target_spec import Cohort, GbsTargetSpec, CohortTargetSpec
from .paths import GbsPaths
from .types import flowcell_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
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
        return [target for cohort in self._cohorts.values() for target in cohort.paths]

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
                os.symlink(
                    os.path.realpath(fastq_link),
                    os.path.join(
                        self._config.paths.fastq_link_dir(str(cohort_name)),
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
                self._config.paths.fastq_link_dir(str(self._name)), fastq_basename
            )
            for fastq_basename in self._spec.fastq_links.keys()
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

        tag_counts_part1_dir = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                "tagCounts_parts",
                "part1",
            )
        ]

        tassel_stages_done = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)),
                done_file,
            )
            for done_file in [
                "tagCounts.done",
                "mergedTagCounts.done",
                "tagPair.done",
            ]
        ]

        kgd_sample_stats = [
            os.path.join(
                self._config.paths.cohort_dir(str(self._name)), "KGD", "SampleStats.csv"
            )
        ]

        paths = (
            self.local_fastq_links
            + suffixed_targets
            + bwa_sampled
            + bwa_sampled_trimmed
            + bwa_sai
            + bwa_bam
            + bwa_stats
            + tag_counts_part1_dir  # TODO what do we need?
            + tassel_stages_done
            # + kgd_sample_stats
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
