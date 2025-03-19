#!/usr/bin/env python

#########################################################################
# ramify a custom keyfile into different libraries to prep for demultiplexing
# safely (check for name collisions) merge the count files from different libraries into a single folder
#########################################################################
import argparse
import sys
import os
import re
import itertools

from agr.util.path import symlink

BARCODE_LENGTH = 10


def _get_options():
    description = """
    """
    long_description = """

check whether a GBS (tassel3) keyfile contains multiple flowcell-library-fastqfile combinations, if so need to demultiplex each combination separately
the ramify_tassel_keyfile.py script will set up a tassel demultiplexing environment in subfolders of tagCounts_parts. These will be called e.g.
tagCounts_parts/part_NNN
where NNN is 1,2,... 
so the structure will be
tagCounts_parts/part<digest>/tagCounts
                        /key
                        /Illumina

examples:

/dataset/gseq_processing/active/bin/gbs_prism/ramify_tassel_keyfile.py -t ramify -o /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts_parts --sub_tassel_prefix part /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/key/sample_info.key

# merge the outputs into the top level folder
/dataset/gseq_processing/active/bin/gbs_prism/ramify_tassel_keyfile.py -t merge_results
-o  /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts_parts
-m /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts
--sub_tassel_prefix part /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/key/sample_info.key

# get merged tag counts 
/dataset/gseq_processing/active/bin/gbs_prism/ramify_tassel_keyfile.py -t merge_counts
-o  /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/tagCounts_parts
--sub_tassel_prefix part /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/test_custom_demultiplex/MspI-ApeKI/key/sample_info.key


"""

    parser = argparse.ArgumentParser(
        description=description,
        epilog=long_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = parser.add_argument("keyfile", type=str, nargs=1, help="keyfile to ramify")
    _ = parser.add_argument(
        "-t",
        "--task",
        dest="task",
        required=False,
        type=str,
        choices=["ramify", "merge_results", "merge_counts"],
        default="exclude_tiles",
        help="what you want to get / do",
    )
    _ = parser.add_argument(
        "-o",
        "--output_folder",
        dest="output_folder",
        type=str,
        default=None,
        help="output folder",
    )
    _ = parser.add_argument(
        "-m",
        "--merge_folder",
        dest="merge_folder",
        type=str,
        default=None,
        help="merge folder",
    )
    _ = parser.add_argument(
        "-p",
        "--sub_tassel_prefix",
        dest="sub_tassel_prefix",
        type=str,
        default="part",
        required=False,
        help="min pass filter",
    )

    args = vars(parser.parse_args())

    if not os.path.exists(args["keyfile"][0]):
        print("keyfile %(keyfile)s does not exist" % args)
        sys.exit(1)
    else:
        if not os.path.isfile(os.path.realpath(args["keyfile"][0])):
            print("keyfile %(keyfile)s is not a file " % args)
            sys.exit(1)

    return args


def ramify(keyfile: str, output_folder: str, sub_tassel_prefix: str) -> int:
    """
    typical keyfile looks like

    iramohio-01$ head /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/bee_SQ1793_SQ1794/sample_info.key
    flowcell        lane    barcode sample  platename       row     column  libraryprepid   counter comment enzyme  species numberofbarcodes        bifo    control fastq_link
    HN7WGDRXY       1       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
    HN7WGDRXY       2       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz
    HN7WGDRXY       1       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
    HN7WGDRXY       2       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz

    Returns number of parts, usually 1.
    """

    # read keyfile into array of tuples and get heading
    # bail out if do not see columns called flowcell, lane, libraryprepid and fastq_link
    print("ramifying keyfile %s" % keyfile)
    with open(keyfile, "r") as instream:
        records = [re.split("\t", record.strip()) for record in instream]
        print("read %d keyfile records" % len(records))

        header = [item.strip().lower() for item in records[0]]
        indexes = {}
        for fieldname in ("flowcell", "lane", "libraryprepid", "fastq_link"):
            if fieldname not in header:
                raise Exception(
                    "ramify_tassel_keyfile : could not find '%s' in header - unable to ramify keyfile (header contains : %s)"
                    % (fieldname, str(header))
                )
            else:
                indexes[fieldname] = header.index(fieldname)

        # sort the keyfile array
        print("sorting keyfile")
        sorted_records = sorted(
            records[1:],
            key=lambda record: (
                record[indexes["flowcell"]],
                record[indexes["libraryprepid"]],
            ),
        )

        # set up an iterator, grouping by flowcell and libraryprepid
        print("analysing keyfile")
        sub_file_iter = itertools.groupby(
            sorted_records,
            lambda rec: (rec[indexes["flowcell"]], rec[indexes["libraryprepid"]]),
        )

        # for each group, create the sub-folder structure and write the sub-key-file
        part_number = 1
        for flowcell_lib_tuple, record_iter in sub_file_iter:
            # sub-folder structure
            part_folder = os.path.join(
                output_folder,
                "%s%d" % (sub_tassel_prefix, part_number),
            )
            key_folder = os.path.join(part_folder, "key")
            tag_folder = os.path.join(part_folder, "tagCounts")
            illumina_folder = os.path.join(part_folder, "Illumina")
            for folder_name in (part_folder, key_folder, tag_folder, illumina_folder):
                if not os.path.isdir(folder_name):
                    os.mkdir(folder_name)
                if not os.path.isdir(folder_name):
                    raise Exception("unable to create folder %s" % folder_name)

            # write keyfile and also validate the number of distinct lanes and fastq file in each group is the same, and create the
            # links to fastq
            lanes = set()
            fastq_files = set()
            sub_key_file_name = os.path.join(
                key_folder, "%s_%s.keyfile" % flowcell_lib_tuple
            )
            with open(sub_key_file_name, "w") as key_out:
                print("\t".join(header), file=key_out)
                for record in record_iter:
                    print("\t".join(record), file=key_out)
                    lanes.add(record[indexes["lane"]])
                    fastq_files.add(record[indexes["fastq_link"]])
                if len(lanes) != len(fastq_files):
                    raise Exception(
                        "lanes .v. fastq links mismatch : %s versus %s"
                        % (str(list(lanes)), str(list(fastq_files)))
                    )

                for link in fastq_files:
                    if not os.path.exists(
                        os.path.join(key_folder, os.path.basename(link))
                    ):
                        symlink(
                            link,
                            os.path.join(illumina_folder, os.path.basename(link)),
                            force=True,
                        )

            part_number += 1

        num_parts = part_number - 1
        print("wrote out %d partial keyfiles and supporting folders " % num_parts)
        return num_parts


def merge_results(output_folder: str, merge_folder: str, sub_tassel_prefix: str):
    """
    typical keyfile looks like

    iramohio-01$ head /dataset/gseq_processing/itmp/Gqueries/uneak_kgd/bee_SQ1793_SQ1794/sample_info.key
    flowcell        lane    barcode sample  platename       row     column  libraryprepid   counter comment enzyme  species numberofbarcodes        bifo    control fastq_link
    HN7WGDRXY       1       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
    HN7WGDRXY       2       AACAGTC 957001  JCM.4464        A       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz
    HN7WGDRXY       1       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_1_fastq.txt.gz
    HN7WGDRXY       2       GAGAATC 957002  JCM.4464        B       1       1793                    MspI-ApeKI      BEE     81                      /dataset/hiseq/active/fastq-link-farm/SQ1793_HN7WGDRXY_s_2_fastq.txt.gz

    """

    # list the subfolders of the out folder, that are folders and match the expected name
    print("merging demultiplexing from %s to %s" % (output_folder, merge_folder))
    part_folders = os.listdir(output_folder)
    part_folders = [
        os.path.join(output_folder, content)
        for content in part_folders
        if re.match(sub_tassel_prefix, content) is not None
    ]
    part_folders = [folder for folder in part_folders if os.path.isdir(folder)]

    print("folders to merge from : %s" % str(part_folders))

    # create shortcuts to the count files in the main output and detect name collisions
    unique_count_files = set()
    for part_folder in part_folders:
        count_files = [
            count_file
            for count_file in os.listdir(os.path.join(part_folder, "tagCounts"))
            if re.search(r"\.cnt$", count_file) is not None
        ]
        for count_file in count_files:
            base = os.path.basename(count_file)
            if base in unique_count_files:
                raise Exception(
                    "error - encountered two copies of %s - bailing out, please check sample sheets and keyfiles"
                    % base
                )
            unique_count_files.add(base)
            target = os.path.join(merge_folder, base)
            source = os.path.join(part_folder, "tagCounts", base)
            symlink(source, target, force=True)


def merge_counts(output_folder: str, sub_tassel_prefix: str):
    # based on /dataset/gseq_processing/active/bin/gbs_prism/get_reads_tags_per_sample.py

    outline = ""

    print("sample,flowcell,lane,sq,tags,reads")

    part_folders = os.listdir(output_folder)
    part_folders = [
        os.path.join(output_folder, content)
        for content in part_folders
        if re.match(sub_tassel_prefix, content) is not None
    ]
    part_folders = [folder for folder in part_folders if os.path.isdir(folder)]

    for part_folder in part_folders:
        fastq_stdout_files = [
            stdout_file
            for stdout_file in os.listdir(part_folder)
            if re.search(r"\.FastqToTagCount\.stdout$", stdout_file) is not None
        ]
        if len(fastq_stdout_files) != 1:
            raise Exception(
                "could not find exactly one FastqToTagCount.stdout file in %s"
                % part_folder
            )

        with open(os.path.join(part_folder, fastq_stdout_files[0])) as stdout_in:
            cellline = ""  # overwritten by first line match
            for line in stdout_in:
                line = line.strip()
                if "Reading FASTQ file:" in line:
                    line = line.split("/")
                    line = line[-1]
                    line = line.split("_")
                    sq = line[0].replace("SQ00", "")
                    flowcell = line[1]
                    lane = line[3]
                    cellline = "%s,%s,%s" % (flowcell, lane, sq)
                elif "Total number of reads in lane" in line:
                    line = line.split("=")
                    total_line = "total,%s,,%s" % (cellline, line[-1])
                    print(total_line)
                elif "Total number of good barcoded reads" in line:
                    line = line.split("=")
                    good_line = "good,%s,,%s" % (cellline, line[-1])
                    print(good_line)
                    cellline = ""
                    total_line = ""
                    good_line = ""
                elif "will be output to" in line:
                    sample = line.split("tagCounts/")[-1]
                    sampleID = sample.split("_")[0]
                    flowcell = sample.split("_")[1]
                    lane = sample.split("_")[2]
                    sq = sample.split("_")[3]
                    outline = "%s,%s,%s,%s" % (sampleID, flowcell, lane, sq)
                elif not outline == "":
                    line = line.split()
                    outline += ",%s,%s" % (line[1], line[6])
                    print(outline)
                    outline = ""
                else:
                    pass


def _main():
    options = _get_options()

    if options["task"] == "ramify":
        _ = ramify(
            keyfile=options["keyfile"][0],
            output_folder=options["output_folder"],
            sub_tassel_prefix=options["sub_tassel_prefix"],
        )
    elif options["task"] == "merge_results":
        merge_results(
            output_folder=options["output_folder"],
            merge_folder=options["merge_folder"],
            sub_tassel_prefix=options["sub_tassel_prefix"],
        )
    elif options["task"] == "merge_counts":
        merge_counts(
            output_folder=options["output_folder"],
            sub_tassel_prefix=options["sub_tassel_prefix"],
        )


if __name__ == "__main__":
    sys.exit(_main())
