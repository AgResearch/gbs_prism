from functools import cached_property, lru_cache
import os.path
import tempfile

from agr.util import StdioRedirect
from agr.gquery import GQuery, GQueryNotFoundException, Predicates
from agr.seq.sample_sheet import SampleSheet

from .paths import SeqPaths
from .types import flowcell_id, Cohort
from .exceptions import GbsPrismDataException


class Stage1Targets:
    def __init__(self, run_name: str, sample_sheet: SampleSheet, seq_paths: SeqPaths):
        self._run_name = run_name
        self._sample_sheet = sample_sheet
        self._seq_paths = seq_paths

    @property
    def all_bclconvert_fastq_files(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.bclconvert_dir, fastq_file)
            for fastq_file in self._sample_sheet.fastq_files
        ]

    @property
    def all_fastqc(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.fastqc_dir, out_file)
            for fastq_file in self._sample_sheet.fastq_files
            for out_file in [
                "%s%s" % (os.path.basename(fastq_file).removesuffix(".fastq.gz"), ext)
                for ext in ["_fastqc.html", "_fastqc.zip"]
            ]
        ]

    def all_kmer_sampled(self, sample_moniker) -> list[str]:
        return [
            os.path.join(
                self._seq_paths.kmer_fastq_sample_dir,
                "%s.fastq.%s.fastq" % (fastq_file, sample_moniker),
            )
            for fastq_file in self._sample_sheet.fastq_files
        ]

    def all_kmer_analysis(self, sample_moniker, kmer_prism_moniker) -> list[str]:
        return [
            os.path.join(
                self._seq_paths.kmer_analysis_dir,
                "%s.%s.1" % (os.path.basename(kmer_sample), kmer_prism_moniker),
            )
            for kmer_sample in self.all_kmer_sampled(sample_moniker)
        ]

    @property
    def all_dedupe(self) -> list[str]:
        return [
            os.path.join(self._seq_paths.dedupe_dir, fastq_file)
            for fastq_file in self._sample_sheet.fastq_files
        ]

    def all_gbs_keyfiles(self, keyfiles_dir) -> list[str]:
        return [
            os.path.join(keyfiles_dir, "%s.generated.txt" % sample_id)
            for sample_id in self._sample_sheet.gbs_libraries
        ]


class Stage1Outputs(object):
    def __init__(self, run_name: str, fastq_link_farm: str):
        self._run_name = run_name
        self._fastq_link_farm = fastq_link_farm

    @cached_property
    def libraries(self) -> list[str]:
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                try:
                    GQuery(
                        task="lab_report",
                        # Libraries are queried as samples 😩
                        predicates=Predicates(
                            name="illumina_run_details", samples=True
                        ),
                        items=[self._run_name],
                    ).run()
                except GQueryNotFoundException:
                    return []
            _ = tmp_f.seek(0)
            return [line.strip() for line in tmp_f.readlines()]

    @lru_cache
    def cohorts(self, library) -> list[Cohort]:
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                try:
                    GQuery(
                        task="lab_report",
                        # Libraries are queried as samples 😩
                        predicates=Predicates(
                            name="illumina_run_details", cohorts=True, sample_id=library
                        ),
                        items=[self._run_name],
                    ).run()
                except GQueryNotFoundException:
                    return []
            _ = tmp_f.seek(0)
            return [
                Cohort.parse("%s.%s" % (library, cohort_substr.strip()))
                for cohort_substr in tmp_f.readlines()
            ]

    @cached_property
    def all_cohorts(self) -> list[Cohort]:
        return [
            cohort for library in self.libraries for cohort in self.cohorts(library)
        ]

    @lru_cache
    def fastq_links(self, cohort: Cohort) -> list[str]:
        fcid = flowcell_id(self._run_name)

        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                try:
                    GQuery(
                        task="gbs_keyfile",
                        badge_type="library",
                        predicates=Predicates(
                            flowcell=fcid,
                            enzyme=cohort.enzyme,
                            gbs_cohort=cohort.gbs_cohort,
                            columns="lane,fastq_link",
                            noheading=True,
                            distinct=True,
                            fastq_path=self._fastq_link_farm,
                        ),
                        items=[cohort.libname],
                    ).run()
                except GQueryNotFoundException:
                    return []
            _ = tmp_f.seek(0)
            return [line.strip().split("\t")[1] for line in tmp_f.readlines()]

    @cached_property
    def all_fastq_links(self) -> set[str]:
        return set(
            [
                fastq_link
                for cohort in self.all_cohorts
                for fastq_link in self.fastq_links(cohort)
            ]
        )

    # no need to dump the method into a file in the filesystem
    @lru_cache
    def cohort_method(self, cohort: Cohort) -> str:
        fcid = flowcell_id(self._run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=cohort.enzyme,
                        gbs_cohort=cohort.gbs_cohort,
                        columns="geno_method",
                        distinct=True,
                        noheading=True,
                        no_unpivot=True,
                    ),
                    items=[cohort.libname],
                ).run()
            _ = tmp_f.seek(0)
            methods = tmp_f.readlines()
            if n_methods := len(methods) != 1:
                raise GbsPrismDataException(
                    "found %d distinct genotyping methods for cohort %s - should be exactly one. Has the keyfile for this cohort been imported ? If so check and change cohort defn or method geno_method col"
                    % (n_methods, str(cohort))
                )
            return methods[0].strip()

    # just refgenome_bwa_indexes for references.txt
    # no need to dump these into a file in the filesystem
    @lru_cache
    def cohort_bwa_references(self, cohort: Cohort) -> list[str]:
        fcid = flowcell_id(self._run_name)
        with tempfile.TemporaryFile(mode="w+") as tmp_f:
            with StdioRedirect(stdout=tmp_f):
                GQuery(
                    task="gbs_keyfile",
                    badge_type="library",
                    predicates=Predicates(
                        flowcell=fcid,
                        enzyme=cohort.enzyme,
                        gbs_cohort=cohort.gbs_cohort,
                        columns="refgenome_bwa_indexes",
                        noheading=True,
                        distinct=True,
                    ),
                    items=[cohort.libname],
                ).run()
            _ = tmp_f.seek(0)
            return [line.strip() for line in tmp_f.readlines()]
