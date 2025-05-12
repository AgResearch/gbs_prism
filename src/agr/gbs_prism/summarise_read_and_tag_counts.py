#!/usr/bin/env python
import itertools
import argparse
import os
import re
import math
import csv
from functools import reduce

# use an absolute import so we can use this as a standalone script
from agr.gbs_prism.data_prism import from_csv_file


def safe_cv(stddev, mean):
    if mean > 0:
        return 100.0 * stddev / (1.0 * mean)
    else:
        return 0.0


def get_unsummarised(filename):
    """
        parse a CSV file like

        sample	flowcell	lane	sq	tags	reads
    total	C89NRANXX	2	SQ0170		213806472
    good	C89NRANXX	2	SQ0170		201374488
    F1506238	C89NRANXX	2	170	307411	1139674
    F1506739	C89NRANXX	2	170	336999	1502266
    F1506080	C89NRANXX	2	170	301157	1083759
    .
    .
    .
    and return a flat tabular listing of the data which can be input to e.g. R boxplot function.
    """
    print("parsing %s" % filename)
    (tuple_stream, exclusions_stream) = itertools.tee(from_csv_file(filename))

    header = next(tuple_stream)
    if (
        header is None
        or len(header) < 1
        or header[0] is None
        or header[0].lower() != "sample"
    ):
        raise Exception(
            """
%s does not look like a CSV tag count summary - first record should be heading, first column should be sample
first record is :
%s
"""
            % (filename, str(header))
        )

    tuple_stream = filter(
        lambda record: not (
            ((record[0] or "").lower() in ("total", "good", "sample"))
            or (
                re.search(
                    "blank|gbsneg|negative",
                    record[0] or "",
                    re.IGNORECASE,
                )
                is not None
            )
        ),
        tuple_stream,
    )
    exclusions_stream = filter(
        lambda record: (
            ((record[0] or "").lower() in ("total", "good", "sample"))
            or (
                re.search(
                    "blank|gbsneg|negative",
                    record[0] or "",
                    re.IGNORECASE,
                )
                is not None
            )
        ),
        exclusions_stream,
    )

    excluded = list(exclusions_stream)
    print("Excluded the following records : %s" % str(excluded))

    # get the flowcell and SQ names from the "totals" records - also get parent folder name as "cohort"
    flowcell = [record for record in excluded if (record[0] or "").lower() == "total"][
        0
    ][1]
    sq = [record for record in excluded if (record[0] or "").lower() == "total"][0][3]
    cohort = os.path.basename(os.path.dirname(filename))

    tags_reads = list(
        (int(record[4] or 0), int(record[5] or 0), record[1], record[3])
        for record in tuple_stream
    )

    return ((cohort, flowcell, sq, len(tags_reads)), tags_reads)


def get_summary(cohort_tags_reads):

    (cohort_tuple, tags_reads) = cohort_tags_reads
    # print "DEBUG : %s"%str(tags_reads)

    if len(tags_reads) == 0:  
        print(f"Warning: No data in tags_reads for {cohort_tuple}. Returning zero for stats.")
        # If there are no records, return zero for all stats
        return (
            "%s_%s_%s(n=%d)" % cohort_tuple,
            0.0,  # mean_tag_count
            0.0,  # std_tag_count
            0.0,  # cv_tag_count (safe_cv will handle mean=0)
            0,    # min_tag_count
            0,    # max_tag_count
            0.0,  # mean_read_count
            0.0,  # std_read_count
            0.0,  # cv_read_count (safe_cv will handle mean=0)
            0,    # min_read_count
            0     # max_read_count
        )
    
    # calculate mean and standard deviation
    # print "DEBUG : %d"%sum((record[0] for record in tags_reads))
    mean_tag_count = sum((record[0] for record in tags_reads)) / float(len(tags_reads))
    mean_read_count = sum((record[1] for record in tags_reads)) / float(len(tags_reads))
    std_tag_count = math.sqrt(
        reduce(
            lambda x, y: x + y,
            map(
                lambda x: (x - mean_tag_count) ** 2,
                (record[0] for record in tags_reads),
            ),
        )
        / float(len(tags_reads))
    )
    std_read_count = math.sqrt(
        reduce(
            lambda x, y: x + y,
            map(
                lambda x: (x - mean_read_count) ** 2,
                (record[1] for record in tags_reads),
            ),
        )
        / float(len(tags_reads))
    )

    # calculate max and min
    min_tag_count = min((record[0] for record in tags_reads))
    min_read_count = min((record[1] for record in tags_reads))
    max_tag_count = max((record[0] for record in tags_reads))
    max_read_count = max((record[1] for record in tags_reads))

    return (
        "%s_%s_%s(n=%d)" % (cohort_tuple),
        mean_tag_count,
        std_tag_count,
        safe_cv(std_tag_count, mean_tag_count),
        min_tag_count,
        max_tag_count,
        mean_read_count,
        std_read_count,
        safe_cv(std_read_count, mean_read_count),
        min_read_count,
        max_read_count,
    )


def get_summaries(options):

    header = [
        (
            "flowcell_sq_cohort",
            "mean_tag_count",
            "std_tag_count",
            "cv_tag_count",
            "min_tag_count",
            "max_tag_count",
            "mean_read_count",
            "std_read_count",
            "cv_read_count",
            "min_read_count",
            "max_read_count",
        )
    ]
    summary_iter = (
        get_summary(get_unsummarised(filename)) for filename in options["filenames"]
    )

    # sort by cohort name
    sorted_summary = sorted(summary_iter, key=lambda record: record[0], reverse=True)

    return itertools.chain(header, sorted_summary)


def get_options():
    description = """
    """
    long_description = """
    example:
    ./summarise_read_and_tag_counts.py /dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/SQ1257.all.PstI.PstI/TagCount.csv
    ./summarise_read_and_tag_counts.py -o /dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/html/tags_reads_summary.txt /dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/*/TagCount.csv
    ./summarise_read_and_tag_counts.py -f csv -o /dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/html/tags_reads_summary.csv /dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/*/TagCount.csv 


summarised output looks like 

flowcell_sq_cohort      mean_tag_count  std_tag_count   min_tag_count   max_tag_count   mean_read_count std_read_count  min_read_count  max_read_count
SQ1257.all.PstI.PstI_CE3EWANXX_SQ1257   253258.066845   29503.126706    41196   333481  700922.302139   175178.466915   50064   1315737
SQ1258.all.PstI.PstI_CE3EWANXX_SQ1258   243487.630319   19029.8927137   40472   324748  696395.071809   115029.175347   49835   1314941
SQ1259.all.PstI.PstI_CE3EWANXX_SQ1259   242148.553191   57613.3610063   39672   368608  689894.276596   281653.607972   54937   1606162
SQ1260.all.cattle.PstI_CE3EWANXX_SQ1260 241946.8        44441.8022528   90710   332085  763308.06       275784.635112   170440  1601096

unsummarised output looks like

cohort  tags    reads
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  453504  3152385
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  372649  1970833
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  371581  1716903
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  502575  3584086
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  611153  4530506
SQ1263.all.takahe.PstI-MspI_CE3EWANXX_SQ1263(n=49)  384775  2235164

(and is input to box plot R script) 

OR



   
    """

    parser = argparse.ArgumentParser(
        description=description,
        epilog=long_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = parser.add_argument("filenames", type=str, nargs="+", help="input files")
    _ = parser.add_argument(
        "-o",
        "--output_filename",
        dest="output_filename",
        default="tags_reads_summary.txt",
        type=str,
        help="output file name",
    )
    _ = parser.add_argument(
        "-f",
        "--out_format",
        dest="out_format",
        default="text",
        type=str,
        choices=["text", "csv"],
        help="output format",
    )
    _ = parser.add_argument(
        "-t",
        "--summary_type",
        dest="summary_type",
        default="summarised",
        type=str,
        choices=["summarised", "unsummarised"],
        help="summary type",
    )

    args = vars(parser.parse_args())

    for filename in args["filenames"]:
        if not os.path.isfile(filename):
            raise Exception("error %s not found" % filename)

    return args


def main():
    options = get_options()

    if options["summary_type"] == "summarised":
        if options["out_format"] == "text":
            with open(options["output_filename"], "w") as outfile:
                for summary_record in get_summaries(options):
                    _ = outfile.write(
                        "%s\n" % "\t".join(map(lambda x: str(x), summary_record))
                    )
        elif options["out_format"] == "csv":
            with open(options["output_filename"], "w") as csvfile:
                my_writer = csv.writer(
                    csvfile, quotechar='"', quoting=csv.QUOTE_NONNUMERIC
                )
                for summary_record in get_summaries(options):
                    my_writer.writerow(summary_record)
    else:
        if options["out_format"] == "text":
            with open(options["output_filename"], "w") as outfile:
                _ = outfile.write("%s\n" % "\t".join(("cohort", "tags", "reads")))
                for filename in options["filenames"]:
                    (cohort_tuple, tags_reads_list) = get_unsummarised(filename)
                    for record in tags_reads_list:
                        _ = outfile.write(
                            "%s\n"
                            % "\t".join(
                                ["%s_%s_%s(n=%d)" % (cohort_tuple)]
                                + list(map(lambda x: str(x), record[0:2]))
                            )
                        )

        elif options["out_format"] == "csv":
            with open(options["output_filename"], "w") as csvfile:
                my_writer = csv.writer(
                    csvfile, quotechar='"', quoting=csv.QUOTE_NONNUMERIC
                )
                my_writer.writerow(("cohort", "tags", "reads"))

                for filename in options["filenames"]:
                    (cohort_tuple, tags_reads_list) = get_unsummarised(filename)
                    for record in tags_reads_list:
                        my_writer.writerow(
                            ["%s_%s_%s(n=%d)" % (cohort_tuple)] + list(record[0:2])
                        )

    return


if __name__ == "__main__":
    main()
