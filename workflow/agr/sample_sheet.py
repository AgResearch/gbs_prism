# sample sheet helpers

import csv
import datetime
import re
from abc import ABC, abstractmethod
from functools import reduce

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
        self.header_records = [ record for record in csv.reader(self.standard_header.splitlines()) ]
        for record in self.header_records:
            if record[0] == 'Date':
                record[1] = record[1]%{"today" : datetime.date.today().strftime("%d/%m/%Y")}

        self.sample_sheet_records = [ record for record in csv.reader(csvpath)]
        self.sample_sheet_numcol = max( (len(record) for record in self.sample_sheet_records ))

        # test if header already present
        self.header_present = reduce(lambda x,y: x or y, [ record[0] == '[Header]' for record in self.sample_sheet_records ] , False)
        self.adapter_config_present = reduce(lambda x,y: x or y, [ record[0] == 'Adapter' for record in self.sample_sheet_records ] , False)

        if self.header_present and not self.adapter_config_present:
            raise Exception(" error , header in the sample sheet supplied does not specify adapter")

    def write_harmonised(self, csvpath: str):
        with open(csvpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)

            # output sample sheet, adding and padding header if necessary
            if not self.header_present:
                for record in self.header_records + self.sample_sheet_records:
                    csvwriter.writerow(record +  (self.sample_sheet_numcol - len(record)) * [""])
            else:
                for record in self.sample_sheet_records:
                    csvwriter.writerow(record)


class NovaseqSampleSheet(SampleSheet):
    def __init__(self, csvpath: str):
        with open(csvpath) as csvfile:
            self.sample_sheet_lines = csvfile.readlines()

    def write_harmonised(self, csvpath: str):
        with open(csvpath, 'w') as csvfile:
            settings_section = False
            for record in self.sample_sheet_lines:
                if re.match(r"\[Settings\]", record, re.IGNORECASE) is not None:
                    settings_section = True
                    csvfile.write(record)
                    continue
                if settings_section:
                    if re.match("Adapter,", record, re.IGNORECASE) is not None:
                        record=re.sub("^Adapter,", "AdapterRead1,", record)
                        settings_section = False
                csvfile.write(record)
