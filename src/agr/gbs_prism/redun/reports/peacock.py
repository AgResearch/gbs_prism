import os.path
from redun import task, File

from agr.util.report import (
    Report,
    Chapter,
    Section,
    Row,
    Inline,
    render_report,
)
from agr.gbs_prism.make_cohort_pages import (
    make_cohort_pages,
)  # TODO remove and its source
from agr.redun.tasks.tags import TAG_READ_STATS

from ..stage1 import Stage1Output
from ..stage2 import Stage2Output, CohortOutput
from ..stage3 import Stage3Output

from .kgd import kgd_plots_section, kgd_links_section, KgdTargets
from .util import image_or_none, link_or_none, row_for_link

redun_namespace = "agr.gbs_prism.reports"


def _kgd_targets(cohort: CohortOutput) -> KgdTargets:
    return KgdTargets(
        kgd_output=cohort.kgd_output,
        kgd_text_files_unblind=cohort.kgd_text_files_unblind,
        hap_map_files_unblind=cohort.hap_map_files_unblind,
    )


@task()
def create_peacock_report(
    title: str,
    stage1: Stage1Output,
    stage2: Stage2Output,
    stage3: Stage3Output,
    out_path: str,
) -> File:
    """Create report, target dir for a cohort is the one containing KGD as a subdirectory."""
    relbase = os.path.dirname(out_path)
    kgd_targets_by_cohort = {
        cohort_name: _kgd_targets(cohort_output)
        for (cohort_name, cohort_output) in stage2.cohorts.items()
    }

    report = Report(
        name=title,
        chapters=[
            Chapter(
                sections=[
                    Section(
                        name="Overview Summaries",
                        named_rows=True,
                        rows=[
                            Row(
                                name="Sample Sheet",
                                target=link_or_none(stage1.sample_sheet, relbase),
                            ),
                            Row(
                                name="bclconvert reports",
                                target=Inline("TODO"),
                            ),
                            Row(
                                name="Cumulative self-relatedness",
                                target=Inline("TODO"),
                            ),
                            Row(
                                name="Tag and Read Counts",
                                target=image_or_none(
                                    stage3.tags_reads_plots.get(TAG_READ_STATS), relbase
                                ),
                            ),
                            Row(
                                name="Tag and Read Counts CV",
                                target=link_or_none(stage3.tags_reads_cv, relbase),
                            ),
                            Row(
                                name="Tag and Read Counts Summary",
                                target=link_or_none(stage3.tags_reads_summary, relbase),
                            ),
                            Row(
                                name="Barcode yield plot",
                                target=image_or_none(
                                    stage3.barcode_yields_plot, relbase
                                ),
                            ),
                            Row(
                                name="Barcode yield summary",
                                target=link_or_none(
                                    stage3.barcode_yield_summary, relbase
                                ),
                            ),
                            Row(
                                name="BWA alignment plot",
                                target=Inline("mapping_stats.jpg TODO"),
                            ),
                            Row(
                                name="BWA alignment summary",
                                target=link_or_none(stage3.bam_stats_summary, relbase),
                            ),
                            Row(
                                name="MULTIQC",
                                target=link_or_none(stage1.multiqc, relbase),
                            ),
                            Row(
                                name="6-mer distributions (raw data)",
                                target=Inline("TODO"),
                            ),
                            Row(
                                name="6-mer distributions (GBS-adapter-trimmed data)",
                                target=Inline("TODO"),
                            ),
                        ],
                    ),
                    Section(
                        name="FASTQC",
                        rows=sorted(
                            [
                                row_for_link(fastqc_output.html, relbase)
                                for fastqc_output in stage1.fastqc
                            ],
                            key=lambda row: row.name if row.name is not None else "",
                        ),
                    ),
                ],
            ),
            Chapter(
                columns=sorted(stage2.cohorts.keys()),
                sections=[
                    kgd_plots_section(kgd_targets_by_cohort, relbase),
                    kgd_links_section(kgd_targets_by_cohort, relbase),
                ],
            ),
        ],
    )
    render_report(report=report, out_path=out_path)

    return File(out_path)
