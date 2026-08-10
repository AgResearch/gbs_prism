"""Turn splitBarcode's per-lane BarcodeStat.txt into MultiQC custom content.

Runs in-process rather than as a Slurm job: this is a few thousand lines of text
processing measured in seconds, and queueing it would cost more than doing it.
`mgi_prism` treats the equivalent rule as a `localrule` for the same reason.

The work itself is in `agr.seq.mgi.barcode_stat`, which is stdlib-only and therefore
unit-tested in CI; this module is only the redun wrapper.
"""

import logging

from redun import task, File

from agr.seq.mgi.barcode_stat import write_multiqc_custom_content

logger = logging.getLogger(__name__)


@task()
def barcode_stat_multiqc(
    run: str, barcode_stats: dict[str, File], out_dir: str
) -> list[File]:
    """Write `mgi_demux_lane_mqc.txt` and `mgi_demux_sample_mqc.txt`.

    `barcode_stats` maps lane label (`L01`) to that lane's `BarcodeStat.txt`, so no
    lane name is ever inferred from a path.
    """
    lane_file, sample_file = write_multiqc_custom_content(
        run=run,
        barcode_stats={
            lane: stat_file.path for lane, stat_file in barcode_stats.items()
        },
        out_dir=out_dir,
    )
    return [File(lane_file), File(sample_file)]
