"""Tests for the MGI post-processing path layout.

Stdlib-only, so these run in CI.

The layout dropped `illumina/<platform>/` for a single `mgi/` segment, aligning with
`mgi_prism`, which already writes to `postprocessing/mgi/<flowcell>`.
"""

import os.path

import pytest

from agr.gbs_prism.paths import GbsPaths, Paths, PathsError, SeqPaths

ROOT = "/postprocessing"
RUN = "DL100018469"


@pytest.fixture
def paths():
    return Paths(postprocessing_root=ROOT, run=RUN)


def test_sequencing_output_lives_under_mgi_not_illumina(paths):
    """`illumina/<platform>/` is gone: MGI-only means there is nothing to select."""
    assert paths.mgi_root == os.path.join(ROOT, "mgi")
    assert paths.seq.run_root == os.path.join(ROOT, "mgi", RUN)


def test_paths_takes_no_platform_argument():
    """The Literal["iseq","miseq","novaseq"] argument is gone with the Illumina path."""
    with pytest.raises(TypeError):
        _ = Paths(postprocessing_root=ROOT, run=RUN, platform="novaseq")  # type: ignore[call-arg]


def test_demux_dir_is_per_lane(paths):
    """splitBarcode writes per-sample fastqs plus BarcodeStat.txt into a lane dir."""
    assert paths.seq.demux_dir(1) == os.path.join(
        ROOT, "mgi", RUN, "SampleSheet", "demux", "L01"
    )
    assert paths.seq.demux_dir(4).endswith("L04")


def test_merged_dir_is_per_library(paths):
    """gquery's fastq glob is prefix-anchored, so SQ5420 also matches SQ54201.

    A directory per library means `resolve_fastq_links` sees exactly one candidate by
    construction, and a library-name collision can never write the wrong path into
    gbskeyfilefact.
    """
    assert paths.seq.merged_dir("SQ5420") == os.path.join(
        ROOT, "mgi", RUN, "SampleSheet", "merged", "SQ5420"
    )
    assert paths.seq.merged_dir("SQ5420") != paths.seq.merged_dir("SQ54201")


def test_merged_fastq_honours_the_gquery_contract(paths):
    """Three requirements from Mgi.resolve_fastq_links, all easy to get wrong.

    The name must begin with the library, end in `.fastq.gz` (not MGI's native
    `.fq.gz`), and sit directly in fastq_root rather than in an L0n subdirectory.
    """
    merged = paths.seq.merged_fastq("SQ5420", RUN)

    assert os.path.basename(merged) == "SQ5420_DL100018469.fastq.gz"
    assert os.path.basename(merged).startswith("SQ5420")
    assert merged.endswith(".fastq.gz")
    assert os.path.dirname(merged) == paths.seq.merged_dir("SQ5420")


def test_sample_sheet_is_archived_inside_the_run(paths):
    """The sheet lives outside the run tree and can be edited after the fact.

    Keeping the processed copy in the run makes the report's relative link stay
    inside the tree, and gives the run a durable record. The name matches the
    original because gquery cross-checks the filename stem against [Header] Flowcell.
    """
    archived = paths.seq.archived_sample_sheet(RUN)
    assert archived == os.path.join(ROOT, "mgi", RUN, "DL100018469.csv")


def test_barcode_and_multiqc_custom_dirs(paths):
    assert paths.seq.barcodes_dir == os.path.join(
        ROOT, "mgi", RUN, "SampleSheet", "barcodes"
    )
    assert paths.seq.multiqc_custom_dir == os.path.join(
        ROOT, "mgi", RUN, "SampleSheet", "multiqc_custom"
    )


def test_gbs_paths_are_unchanged(paths):
    """Stage 2's layout is not part of this refactor."""
    assert paths.gbs.run_root == os.path.join(ROOT, "gbs", RUN)
    assert paths.gbs.target_spec_path.endswith("target-spec.json")


def test_tassel3_still_wants_a_directory_called_illumina():
    """Not an Illumina leftover: Tassel3 requires that literal directory name."""
    gbs = GbsPaths(root="/gbs", run=RUN)
    assert gbs.fastq_link_dir("SQ5420.all.deer.PstI", blind=True).endswith("Illumina")


def test_make_run_dirs_creates_the_lane_and_library_directories(tmp_path):
    seq = SeqPaths(str(tmp_path / "mgi" / RUN))
    seq.make_run_dirs(lanes=[1, 2], libraries=["SQ5420", "SQ5421"])

    assert os.path.isdir(seq.demux_dir(1))
    assert os.path.isdir(seq.demux_dir(2))
    assert os.path.isdir(seq.merged_dir("SQ5420"))
    assert os.path.isdir(seq.merged_dir("SQ5421"))
    assert os.path.isdir(seq.barcodes_dir)
    assert os.path.isdir(seq.multiqc_custom_dir)
    assert os.path.isdir(seq.fastqc_dir)


def test_make_run_dirs_creates_the_mgi_root_itself(tmp_path):
    """`mgi/` will not exist the first time any environment runs an MGI run.

    The Illumina version required `illumina/<platform>/` to pre-exist, which was
    invisible only because that directory had been there for years. Renaming the
    segment made it a guaranteed first-run failure in dev, test and prod alike.
    """
    root = str(tmp_path / "postprocessing")
    os.makedirs(root)
    paths = Paths(postprocessing_root=root, run=RUN)

    paths.make_run_dirs(lanes=[1], libraries=["SQ5420"])

    assert os.path.isdir(paths.mgi_root)
    assert os.path.isdir(paths.seq.demux_dir(1))


def test_make_run_dirs_still_refuses_a_postprocessing_root_that_does_not_exist(tmp_path):
    """The guard is worth keeping: it catches a mistyped context before the pipeline
    scatters a tree somewhere wrong. It just has to check the thing that is
    externally provisioned, not the subdirectory we own."""
    paths = Paths(postprocessing_root=str(tmp_path / "typo"), run=RUN)
    with pytest.raises(PathsError):
        paths.make_run_dirs(lanes=[1], libraries=["SQ5420"])
