#########################################################################
# collate tag and read counts , taking into account the novaseq "split lanes" disposition
#########################################################################
import sys
import re
import csv
from redun import task, File
from typing import Literal, TextIO, get_args, Optional, Iterator

from agr.util.table import join_spec, left_join, Joinee, split_column

MACHINES_LITERAL = Literal["novaseq", "hiseq", "miseq", "iseq"]
MACHINES = list(get_args(MACHINES_LITERAL))
DEFAULT_MACHINE = "novaseq"


def _get_reads_tags(
    run: str,
    cohort: str,
    machine: MACHINES_LITERAL,
    tag_counts: TextIO,
) -> Iterator[list[str]]:
    """
    Now returns the reads tags as an iterator, including the header row.
    """
    # e.g.
    # sample,flowcell,lane,sq,tags,reads
    # total,H2TTCDMXY,1,SQ1745,,361922664
    # good,H2TTCDMXY,1,SQ1745,,333623829
    # qc823992-1,H2TTCDMXY,1,1745,129084,626118
    # qc824060-1,H2TTCDMXY,1,1745,36105,91036
    novaseq_counts = {}
    column_headings = None
    flowcell = None
    sq = None
    for record in tag_counts:
        if column_headings is None:
            column_headings = [
                item.lower().strip() for item in re.split(r"\s*,\s*", record.strip())
            ]
            if tuple(column_headings) != (
                "sample",
                "flowcell",
                "lane",
                "sq",
                "tags",
                "reads",
            ):
                raise Exception(
                    "collate_tags_reads.py : heading = %s, did not expect that"
                    % str(column_headings)
                )
            yield ["run", "cohort"] + column_headings
            continue
        fields: list[str] = [
            item.strip() for item in re.split(r"\s*,\s*", record.strip())
        ]
        if len(fields) == 0:
            continue

        if len(fields) != len(column_headings):
            raise Exception(
                "collate_tags_reads.py : wrong number of fields in %s, should match %s"
                % (str(fields), str(column_headings))
            )

        field_dict: dict[str, str] = dict(zip(column_headings, fields))

        if field_dict["sample"] in ("total", "good"):
            continue

        if flowcell is None:
            flowcell = field_dict["flowcell"]
            sq = field_dict["sq"]

        if flowcell != field_dict["flowcell"] or sq != field_dict["sq"]:
            raise Exception(
                "looks like one or more files contains data for more than one flowcell or sq number - this is not supported. First saw %s, then later %s"
                % (
                    str((flowcell, sq)),
                    str((field_dict["flowcell"], field_dict["sq"])),
                )
            )

        if machine == "novaseq":
            # the novaseq tag count file has totals for several "lanes", and we want to collpase these
            novaseq_counts[field_dict["sample"]] = list(
                map(
                    lambda x, y: x + y,
                    [int(field_dict["tags"]), int(field_dict["reads"])],
                    novaseq_counts.get(field_dict["sample"], [0, 0]),
                )
            )
        else:
            yield [
                run,
                cohort,
            ] + [
                field_dict[name]
                for name in (
                    "sample",
                    "flowcell",
                    "lane",
                    "sq",
                    "tags",
                    "reads",
                )
            ]

    if machine == "novaseq":
        for sample in novaseq_counts:
            yield [
                run,
                cohort,
                sample,
                flowcell,
                "1",
                sq,
                str(novaseq_counts[sample][0]),
                str(novaseq_counts[sample][1]),
            ]  # type: ignore[reportReturnType]


def _collate_tags_reads(
    run: str,
    cohort: str,
    machine: MACHINES_LITERAL,
    tag_counts: TextIO,
    out_path: Optional[str] = None,
):
    with open(out_path, "w") if out_path is not None else sys.stdout as out_f:
        reads_tags = _get_reads_tags(
            run=run, cohort=cohort, machine=machine, tag_counts=tag_counts
        )
        # skip header since we added one
        _ = next(reads_tags)
        for record in reads_tags:
            print("\t".join(record), file=out_f)
            # e.g.
            # run cohort sample flowcell, dummy_lane, sq, tags, reads
            # 211217_A01439_0043_BH2TTCDMXY   SQ1744.all.PstI-MspI.PstI-MspI  qc823603-1      H2TTCDMXY       1       1744    196401  2251079
            # 211217_A01439_0043_BH2TTCDMXY   SQ1744.all.PstI-MspI.PstI-MspI  qc823505-1      H2TTCDMXY       1       1744    1611    2485
            # 211217_A01439_0043_BH2TTCDMXY   SQ1744.all.PstI-MspI.PstI-MspI  qc823524-1      H2TTCDMXY       1       1744    167460  930628
            # 211217_A01439_0043_BH2TTCDMXY   SQ1744.all.PstI-MspI.PstI-MspI  qc823648-1      H2TTCDMXY       1       1744    137904  1415198
            # 211217_A01439_0043_BH2TTCDMXY   SQ1744.all.PstI-MspI.PstI-MspI  qc823502-1      H2TTCDMXY       1       1744    134157  1357268


@task()
def collate_tags_reads(
    run: str,
    cohort: str,
    tag_counts: File,
    out_path: str,
    machine: MACHINES_LITERAL = DEFAULT_MACHINE,
) -> File:
    with open(tag_counts.path, "r") as tag_counts_f:
        _collate_tags_reads(
            run=run,
            cohort=cohort,
            machine=machine,
            tag_counts=tag_counts_f,
            out_path=out_path,
        )
    return File(out_path)


def _collate_tags_reads_kgdstats(
    reads_tags: Iterator[list[str]],
    kgd_stats: Iterator[list[str]],
    keyfile: Iterator[list[str]],
    out_path: Optional[str] = None,
):
    # kgd_stats seqID column needs to be split into qc_sampleid and kgd_moniker
    # "qc959031-1_merged_2_0_X4",0.79488779198855,2.51852395544709
    kgd_stats_header = next(kgd_stats)
    kgd_stats_split = split_column(
        column="seqID",
        new_columns=["qc_sampleid", "kgd_moniker"],
        # qc_sampleid is everything before the first underscore; kgd_moniker is the original, including the qc_sampleid prefix
        splitter=lambda s: [s.split("_", 1)[0], s],
        header=kgd_stats_header,
        rows=kgd_stats,
    )

    spec = join_spec(
        [
            Joinee(
                key_name="sample",
                header=next(reads_tags),
                columns=[
                    "run",
                    "cohort",
                    "sample",
                    "flowcell",
                    "sq",
                    "tags",
                    "reads",
                ],
                renames={
                    "sample": "qc_sampleid",
                },
            ),
            Joinee(
                key_name="qc_sampleid",
                header=next(kgd_stats_split),
                columns=[
                    "kgd_moniker",
                    "callrate",
                    "sampdepth",
                ],
            ),
            Joinee(
                key_name="sample",
                header=next(keyfile),
                columns=[
                    "row",
                    "column",
                ],
            ),
        ]
    )
    with open(out_path, "w") if out_path is not None else sys.stdout as out_f:
        csv_writer = csv.writer(out_f)
        for row in left_join(spec, [reads_tags, kgd_stats_split, keyfile]):
            csv_writer.writerow(row)


@task()
def collate_tags_reads_kgdstats(
    run: str,
    cohort: str,
    tag_counts: File,
    kgd_stats: Optional[File],
    keyfile_for_tassel: File,
    out_path: str,
    machine: MACHINES_LITERAL = DEFAULT_MACHINE,
) -> Optional[File]:
    if kgd_stats is None:
        return None
    else:
        with open(tag_counts.path, "r") as tag_counts_f:
            with open(kgd_stats.path, "r") as kgd_stats_f:
                with open(keyfile_for_tassel.path, "r") as keyfile_f:
                    reads_tags = _get_reads_tags(
                        run=run,
                        cohort=cohort,
                        machine=machine,
                        tag_counts=tag_counts_f,
                    )
                    kgd_stats_rows = csv.reader(kgd_stats_f)
                    keyfile_rows = csv.reader(keyfile_f, delimiter="\t")
                    _collate_tags_reads_kgdstats(
                        reads_tags=reads_tags,
                        kgd_stats=kgd_stats_rows,
                        keyfile=keyfile_rows,
                        out_path=out_path,
                    )
        return File(out_path)
