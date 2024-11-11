from functools import cached_property, lru_cache
from typing import Protocol
import logging
import os.path
import re
import tempfile

from agr.util import StdioRedirect, eprint
from agr.gquery import GQuery, GQueryNotFoundException, Predicates

from .exceptions import GbsPrismDataException
from .paths import GbsPaths
from .types import flowcell_id

logger = logging.getLogger(__name__)


class Cohort(object):
    def __init__(self, name: str, run_name: str):
        name_fields = name.split(".")
        assert len(name_fields) == 4, (
            "expected four dot-separated fields in cohort %s" % name
        )
        (self._libname, self._qc_cohort, self._gbs_cohort, self._enzyme) = tuple(
            name_fields
        )

        self._run_name = run_name
        logger.debug("Cohort(%s) object created" % self.name)

    @property
    def libname(self):
        return self._libname

    @property
    def qc_cohort(self):
        return self._qc_cohort

    @property
    def gbs_cohort(self):
        return self._gbs_cohort

    @property
    def enzyme(self):
        return self._enzyme

    @cached_property
    def name(self):
        return "%s.%s.%s.%s" % (
            self.libname,
            self.qc_cohort,
            self.gbs_cohort,
            self.enzyme,
        )

    def _fastq_basenames(self, c: "TargetConfig"):
        return [
            real_basename(fastq_link)
            for fastq_link in self.central_fastq_links(c.fastq_link_farm)
        ]

    @lru_cache
    def local_fastq_links(self, c: "TargetConfig") -> list[str]:
        return [
            os.path.join(c.gbs_paths.fastq_link_dir(self.name), fastq_basename)
            for fastq_basename in self._fastq_basenames(c)
        ]

    @lru_cache
    def targets(self, c: "TargetConfig") -> list[str]:
        """Cohort target paths for SnakeMake."""

        bwa_sampled = [
            os.path.join(
                c.gbs_paths.bwa_mapping_dir(self.name),
                "%s.fastq.%s.fastq" % (fastq_basename, c.bwa_sample_moniker),
            )
            for fastq_basename in self._fastq_basenames(c)
        ]

        bwa_sampled_trimmed = [
            "%s.trimmed.fastq" % sampled.removesuffix(".fastq")
            for sampled in bwa_sampled
        ]

        bwa_aligned = [
            "%s.%s.%s" % (trimmed, bwa_reference_moniker, ext)
            for trimmed in bwa_sampled
            for bwa_reference_moniker in self.bwa_references.keys()
            for ext in ["bam", "stats"]
        ]

        def suffixed_target(suffix: str) -> str:
            # TODO these names are quite clunky, perhaps remove the pointless `run` prefix later
            return "%s/%s.%s.%s" % (
                c.gbs_paths.run_root,
                self._run_name,
                self.name,
                suffix,
            )

        # note that some targets which were previsouly dumped into the filesystem are now simply
        # returned as lists, namely: method, bwa_references
        suffixed_targets = [
            suffixed_target(suffix) for suffix in ["key", "gbsx.key", "unblind.sed"]
        ]

        return (
            self.local_fastq_links(c)
            + suffixed_targets
            + bwa_sampled
            + bwa_sampled_trimmed
            # + bwa_aligned TODO
        )

    def create_local_fastq_links(self, c: "TargetConfig"):
        for fastq_link in self.central_fastq_links(c.fastq_link_farm):
            os.symlink(
                os.path.realpath(fastq_link),
                os.path.join(
                    c.gbs_paths.fastq_link_dir(self.name),
                    real_basename(fastq_link),
                ),
            )

    @lru_cache
    def central_fastq_links(self, fastq_link_farm: str) -> list[str]:
        fcid = flowcell_id(self._run_name)

        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                try:
                    GQuery(
                        task="gbs_keyfile",
                        badge_type="library",
                        predicates=Predicates(
                            flowcell=fcid,
                            enzyme=self.enzyme,
                            gbs_cohort=self.gbs_cohort,
                            columns="fastq_link",
                            noheading=True,
                            distinct=True,
                            fastq_path=fastq_link_farm,
                        ),
                        items=[self.libname],
                    ).run()
                except GQueryNotFoundException:
                    return []
            _ = tmp_f.seek(0)
            return [line.strip() for line in tmp_f.readlines()]

    # no need to dump the method into a file in the filesystem
    @cached_property
    def method(self) -> str:
        fcid = flowcell_id(self._run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self.enzyme,
                        gbs_cohort=self.gbs_cohort,
                        columns="geno_method",
                        distinct=True,
                        noheading=True,
                        no_unpivot=True,
                    ),
                    items=[self.libname],
                ).run()
            _ = tmp_f.seek(0)
            methods = tmp_f.readlines()
            if n_methods := len(methods) != 1:
                raise GbsPrismDataException(
                    "found %d distinct genotyping methods for cohort %s - should be exactly one. Has the keyfile for this cohort been imported ? If so check and change cohort defn or method geno_method col"
                    % (n_methods, self.name)
                )
            return methods[0].strip()

    # just refgenome_bwa_indexes for references.txt
    # no need to dump these into a file in the filesystem
    #
    # IMPORTANT NOTE: the SnakeMake targets are driven by target pathnames. A component of the path
    # is the basename of the bwa reference, which means the full path to the bwa reference must be
    # looked up from the basename, and must therefore be unique.  Non-uniqueness here is a fatal error, and will need to be addressed if in fact it turns out to be a problem.
    @cached_property
    def bwa_references(self) -> dict[str, str]:
        fcid = flowcell_id(self._run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self.enzyme,
                        gbs_cohort=self.gbs_cohort,
                        columns="refgenome_bwa_indexes",
                        noheading=True,
                        distinct=True,
                    ),
                    items=[self.libname],
                ).run()
            _ = tmp_f.seek(0)
            paths = list(
                # ensure uniqueness
                set(
                    [
                        # gquery sometimes spits out empty paths, which we filter out here
                        path
                        for line in tmp_f.readlines()
                        if (path := line.strip())
                    ]
                )
            )
            path_by_moniker = dict([(os.path.basename(path), path) for path in paths])
            assert len(path_by_moniker) == len(
                paths
            ), "uniqueness of basenames in bwa-references for cohort %s: %s" % (
                self.name,
                ", ".join(paths),
            )
            logger.debug(
                "bwa_references_for_cohort(%s): %s" % (self.name, ", ".join(paths))
            )
            return path_by_moniker

    def get_keyfile_for_tassel(self, out_path: str):
        fcid = flowcell_id(self._run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                g = GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self.enzyme,
                        gbs_cohort=self.gbs_cohort,
                        columns="flowcell,lane,barcode,qc_sampleid as sample,platename,platerow as row,platecolumn as column,libraryprepid,counter,comment,enzyme,species,numberofbarcodes,bifo,control,fastq_link",
                    ),
                    items=[self.libname],
                )
                eprint(g)
                g.run()

                # from https://github.com/AgResearch/gbs_prism/blob/dc5a71a6a2c554cd8952614d151a46ddce6892d1/ag_gbs_qc_prism.sh#L252
                enzyme_sub_re = re.compile(r"HpaIII?")  # matches HpaII or HpaIII
                enzyme_sub = "MspI"

            _ = tmp_f.seek(0)
            with open(out_path, "w") as keyfile_f:
                for line in tmp_f:
                    _ = keyfile_f.write(enzyme_sub_re.sub(enzyme_sub, line))

    def get_gbsx_keyfile(self, out_path: str):
        fcid = flowcell_id(self._run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self.enzyme,
                        gbs_cohort=self.gbs_cohort,
                        columns="qc_sampleid as sample,Barcode,Enzyme",
                    ),
                    items=[self.libname],
                ).run()

    def get_unblind_script(self, out_path: str):
        fcid = flowcell_id(self._run_name)
        with open(out_path, "w") as keyfile_f:
            with StdioRedirect(stdout=keyfile_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=self.enzyme,
                        gbs_cohort=self.gbs_cohort,
                        unblinding=True,
                        columns="qc_sampleid,sample",
                        noheading=True,
                    ),
                    items=[self.libname],
                ).run()


def real_basename(symlink: str) -> str:
    return os.path.basename(os.path.realpath(symlink))


class TargetConfig(Protocol):
    fastq_link_farm: str
    gbs_paths: GbsPaths
    bwa_sample_moniker: str
