# sample sheet helpers

import csv
import datetime
import re
from abc import ABC, abstractmethod
from enum import Enum
from functools import reduce
from typing import Optional


class SampleSheet(ABC):
    @abstractmethod
    def write_harmonised(self, csvpath: str):
        pass


class HiseqSampleSheet(SampleSheet):
    standard_header = """
[Header],,,,,,,,,,,,,
IEMFileVersion,4,,,,,,,,,,,,
Date,%(today)s,,,,,,,,,,,,
Workflow,GenerateFASTQ,,,,,,,,,,,,
Application,HiSeq FASTQ Only,,,,,,,,,,,,
Assay,TruSeq HT,,,,,,,,,,,,
Description,,,,,,,,,,,,,
Chemistry,Amplicon,,,,,,,,,,,,
,,,,,,,,,,,,,
[Reads],,,,,,,,,,,,,
101,,,,,,,,,,,,,
,,,,,,,,,,,,,
[Settings],,,,,,,,,,,,,
ReverseComplement,0,,,,,,,,,,,,
Adapter,AGATCGGAAGAGCACACGTCTGAACTCCAGTCA,,,,,,,,,,,,
AdapterRead2,AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT,,,,,,,,,,,,
[Data],,,,,,,,,,,,,
    """

    def __init__(self, csvpath: str):
        self.csvpath = csvpath
        self._read()

    def _read(self):
        self.header_records = [
            record for record in csv.reader(self.standard_header.splitlines())
        ]
        for record in self.header_records:
            if record[0] == "Date":
                record[1] = record[1] % {
                    "today": datetime.date.today().strftime("%d/%m/%Y")
                }

        self.sample_sheet_records = [record for record in csv.reader(self.csvpath)]
        self.sample_sheet_numcol = max(
            (len(record) for record in self.sample_sheet_records)
        )

        # test if header already present
        self.header_present = reduce(
            lambda x, y: x or y,
            [record[0] == "[Header]" for record in self.sample_sheet_records],
            False,
        )
        self.adapter_config_present = reduce(
            lambda x, y: x or y,
            [record[0] == "Adapter" for record in self.sample_sheet_records],
            False,
        )

        if self.header_present and not self.adapter_config_present:
            raise Exception(
                " error , header in the sample sheet supplied does not specify adapter"
            )

    def write_harmonised(self, csvpath: str):
        with open(csvpath, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)

            # output sample sheet, adding and padding header if necessary
            if not self.header_present:
                for record in self.header_records + self.sample_sheet_records:
                    csvwriter.writerow(
                        record + (self.sample_sheet_numcol - len(record)) * [""]
                    )
            else:
                for record in self.sample_sheet_records:
                    csvwriter.writerow(record)


class SequencingType(Enum):
    SINGLE_END = 1
    PAIRED_END = 2


class NovaseqSampleSheet(SampleSheet):
    def __init__(
        self,
        csvpath: str,
        sequencing_type: SequencingType = SequencingType.PAIRED_END,
        impute_lanes: Optional[list[str]] = None,
    ):
        self.csvpath = csvpath
        self._read()
        self._fastq_files = self._get_fastq_filenames(sequencing_type, impute_lanes)

    @property
    def fastq_files(self):
        return self._fastq_files

    def _read(self):
        with open(self.csvpath) as csvfile:
            self.sample_sheet_lines = csvfile.readlines()

    def write_harmonised(self, csvpath: str):
        with open(csvpath, "w") as csvfile:
            settings_section = False
            for record in self.sample_sheet_lines:
                if re.match(r"\[Settings\]", record, re.IGNORECASE) is not None:
                    settings_section = True
                    csvfile.write(record)
                    continue
                if settings_section:
                    if re.match("Adapter,", record, re.IGNORECASE) is not None:
                        record = re.sub("^Adapter,", "AdapterRead1,", record)
                        settings_section = False
                csvfile.write(record)

    def _get_fastq_filenames(
        self,
        sequencing_type: SequencingType,
        impute_lanes: Optional[list[str]],
    ) -> set[str]:
        """
        parse the Sample sheet and construct expected fastq filenames
        """

        seen_data = False
        header_fields = None
        sample_dict = {}
        predicted_files = set()
        s_number = 0

        for record in self.sample_sheet_lines:
            # [Data],,,,,,,,,,,
            # Lane,Sample_ID,Sample_Name,Sample_Plate,Sample_Well,Index_Plate_Well,I7_Index_ID,index,I5_Index_ID,index2,Sample_Project,Description
            # 1,P628_2,P628_2,NS0035,A1,A5,S769,TCCTCATG,S519,AGGTGTAC,Pestivirus_MethySeq,Pestivirus_MethySeq
            # 1,P726_3,P726_3,NS0035,B1,B5,S752,AGGATAGC,S544,AACCTTGG,Pestivirus_MethySeq,Pestivirus_MethySeq
            #
            # generates P628_2_S1_L001_R1_001.fastq.gz etc.
            fields = re.split(",", record.strip())
            if not seen_data and fields[0] == "[Data]":
                seen_data = True
                continue

            if seen_data:
                if header_fields is None:
                    header_fields = [
                        item.lower() for item in re.split(",", record.strip())
                    ]
                    s_number += 1
                else:
                    if len(fields[0].strip()) == 0:
                        break
                    if fields[0][0] == "[":
                        break
                    if "lane" in header_fields:
                        (ilane, isample) = (
                            header_fields.index("lane"),
                            header_fields.index("sample_id"),
                        )
                        (lane, sample) = (int(fields[ilane]), fields[isample])
                    else:
                        isample = header_fields.index("sample_id")
                        (lane, sample) = (1, fields[isample])  # default lane to 1

                    if sample not in sample_dict:
                        sample_dict[sample] = s_number
                        s_number += 1

                    if impute_lanes is None:
                        R1_filename = "%s_S%d_L%03d_R1_001.fastq.gz" % (
                            sample,
                            sample_dict[sample],
                            lane,
                        )
                        R2_filename = "%s_S%d_L%03d_R2_001.fastq.gz" % (
                            sample,
                            sample_dict[sample],
                            lane,
                        )

                        predicted_files.add(R1_filename)

                        if sequencing_type == SequencingType.PAIRED_END:
                            predicted_files.add(R2_filename)

                    else:
                        for lane in impute_lanes:
                            R1_filename = "%s_S%d_L%03d_R1_001.fastq.gz" % (
                                sample,
                                sample_dict[sample],
                                int(lane),
                            )
                            R2_filename = "%s_S%d_L%03d_R2_001.fastq.gz" % (
                                sample,
                                sample_dict[sample],
                                int(lane),
                            )

                            predicted_files.add(R1_filename)

                            if sequencing_type == SequencingType.PAIRED_END:
                                predicted_files.add(R2_filename)

        return predicted_files
