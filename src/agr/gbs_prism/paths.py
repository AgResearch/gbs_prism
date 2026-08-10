import logging
import os.path
from typing import Optional

logger = logging.getLogger(__name__)


class PathsError(Exception):
    def __init__(self, msg: str, e: Optional[Exception] = None):
        self._msg = msg
        self._e = e

    def __str__(self) -> str:
        return "%s: %s" % (self._msg, str(self._e))


def _makedir(path: str):
    if not os.path.isdir(path):
        logger.info("creating %s directory", path)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise PathsError("failed to create %s" % path, e)


class SeqPaths:
    def __init__(self, run_root: str):
        self._run_root = run_root

    @property
    def run_root(self) -> str:
        return self._run_root

    def archived_sample_sheet(self, run: str) -> str:
        """Where the run's own copy of the sample sheet is kept.

        The MGI sheet lives outside the run tree and can be edited after the fact, so
        stage 1 archives the version it actually processed. Named `<flowcell>.csv`
        like the original, both because that is how it is recognised and because
        gquery's `derive_run_name_from_sample_sheet` cross-checks the filename stem
        against `[Header] Flowcell`.

        Note the keyfile import still reads the *original*, so that correcting the
        upstream sheet re-triggers the import rather than being masked by this copy.
        """
        return os.path.join(self._run_root, "%s.csv" % run)

    @property
    def sample_sheet_dir(self) -> str:
        return os.path.join(self._run_root, "SampleSheet")

    @property
    def barcodes_dir(self) -> str:
        """The generated per-lane splitBarcode `-B` files."""
        return os.path.join(self.sample_sheet_dir, "barcodes")

    def demux_dir(self, lane: int) -> str:
        """splitBarcode's output for one lane: per-sample fastqs plus BarcodeStat.txt."""
        return os.path.join(self.sample_sheet_dir, "demux", "L%02d" % lane)

    def merged_dir(self, library: str) -> str:
        """Where a library's lanes are merged into a single fastq.

        One directory **per library**, which is what makes gquery's fastq discovery
        safe: `Mgi.resolve_fastq_links` does a flat `os.listdir` and a
        prefix-anchored `re.match`, so `SQ5420` would also match a neighbouring
        `SQ54201`. Giving each library its own directory means there is exactly one
        candidate by construction, and the "expected exactly one" check cannot be
        satisfied by the wrong file.
        """
        return os.path.join(self.sample_sheet_dir, "merged", library)

    def merged_fastq(self, library: str, flowcell: str) -> str:
        """The merged fastq's full path.

        The name is a hard contract with gquery: it must begin with the library name
        and end in `.fastq.gz` - not MGI's native `.fq.gz`, and not the flowcell-led
        `DL100018469_L01_SQ5420.fq.gz` the sequencer produces, which satisfies none
        of the three requirements.
        """
        return os.path.join(
            self.merged_dir(library), "%s_%s.fastq.gz" % (library, flowcell)
        )

    @property
    def multiqc_custom_dir(self) -> str:
        """MultiQC custom content built from splitBarcode's BarcodeStat.txt.

        MultiQC has no splitBarcode parser, so the demultiplexing stats reach the
        report as custom content rather than through a module.
        """
        return os.path.join(self.sample_sheet_dir, "multiqc_custom")

    @property
    def fastqc_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "fastqc_run", "fastqc")

    @property
    def multiqc_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "multiqc")

    @property
    def kmer_fastq_sample_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "kmer_run", "fastq_sample")

    @property
    def kmer_analysis_dir(self) -> str:
        return os.path.join(self.sample_sheet_dir, "kmer_run", "kmer_analysis")

    def make_run_dirs(self, lanes: list[int], libraries: list[str]):
        """Create the run's output directories.

        Lanes and libraries both come from the sample sheet, because the per-lane
        demux directories and the per-library merge directories cannot be enumerated
        without it.
        """
        _makedir(self.sample_sheet_dir)
        _makedir(self.barcodes_dir)
        _makedir(self.fastqc_dir)
        _makedir(self.multiqc_dir)
        _makedir(self.multiqc_custom_dir)
        _makedir(self.kmer_fastq_sample_dir)
        _makedir(self.kmer_analysis_dir)
        for lane in lanes:
            _makedir(self.demux_dir(lane))
        for library in libraries:
            _makedir(self.merged_dir(library))


class GbsPaths:
    def __init__(self, root: str, run: str):
        self._root = root
        self._run_root = os.path.join(root, run)

    @property
    def root(self) -> str:
        return self._root

    @property
    def run_root(self) -> str:
        return self._run_root

    @property
    def report_dir(self) -> str:
        return os.path.join(self._run_root, "html")

    @property
    def target_spec_path(self) -> str:
        return os.path.join(self._run_root, "target-spec.json")

    def cohort_dir(self, cohort_name: str) -> str:
        return os.path.join(self._run_root, cohort_name)

    def cohort_blind_dir(self, cohort_name: str) -> str:
        return os.path.join(self.cohort_dir(cohort_name), "blind")

    def fastq_link_dir(self, cohort_name: str, blind=False) -> str:
        """
        Directory of links to fastq files for the cohort, needs to match Tassel3 expectation.

        Because of the separate blind and unblind phases, and Tassel3's need for the local Illumina directory,
        which means one is needed in the blind subdirectory, two identical link dirs are maintained.
        """
        return (
            os.path.join(self.cohort_blind_dir(cohort_name), "Illumina")
            if blind
            else os.path.join(self.cohort_dir(cohort_name), "fastq")
        )

    def bwa_mapping_dir(self, cohort_name: str) -> str:
        return os.path.join(self._run_root, "bwa_mapping", cohort_name)

    def make_cohort_dirs(self, cohort_name: str):
        _makedir(self.bwa_mapping_dir(cohort_name))
        _makedir(self.fastq_link_dir(cohort_name))
        _makedir(self.fastq_link_dir(cohort_name, blind=True))


class Paths:
    """Post-processing layout for an MGI run.

    `postprocessing_root/mgi/<run>`, dropping the `illumina/<platform>/` pair of
    segments the Illumina pipeline used. With MGI-only there is no second platform to
    parameterise over, so the `platform` argument is gone rather than gaining an
    `"mgi"` member - and this aligns with `mgi_prism`, which already writes to
    `postprocessing/mgi/<flowcell>`.
    """

    def __init__(self, postprocessing_root: str, run: str):
        self._postprocessing_root = postprocessing_root
        self._mgi_root = os.path.join(postprocessing_root, "mgi")
        self._seq_paths = SeqPaths(run_root=os.path.join(self._mgi_root, run))

        self._gbs_root = os.path.join(postprocessing_root, "gbs")
        self._gbs_paths = GbsPaths(root=self._gbs_root, run=run)

    @property
    def mgi_root(self) -> str:
        return self._mgi_root

    @property
    def seq(self) -> SeqPaths:
        return self._seq_paths

    @property
    def gbs(self) -> GbsPaths:
        return self._gbs_paths

    def make_run_dirs(self, lanes: list[int], libraries: list[str]):
        # Assert the *externally provisioned* root, then create our own subtree. The
        # guard is there to catch a mistyped postprocessing_root before the pipeline
        # scatters a tree somewhere wrong; asserting `mgi/` instead would make the
        # first MGI run in every environment fail, since nothing else creates it.
        if not os.path.isdir(self._postprocessing_root):
            raise PathsError("no such directory %s" % self._postprocessing_root)
        _makedir(self._mgi_root)
        self._seq_paths.make_run_dirs(lanes=lanes, libraries=libraries)

    def make_cohort_dirs(self, cohort_name: str):
        if not os.path.isdir(self._gbs_root):
            raise PathsError("no such directory %s" % self._gbs_root)
        self._gbs_paths.make_cohort_dirs(cohort_name)
