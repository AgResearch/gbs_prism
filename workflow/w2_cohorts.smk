configfile: "config/pipeline_config.yaml"

# temporary import path until library is installed as a Python package
sys.path.append(Path(workflow.basedir).parent.joinpath("src").as_posix())

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')
                    #filename='gbs_prism.log',
                    #filemode='a')
for noisy_module in ['asyncio', 'pulp.apis.core']:
    logging.getLogger(noisy_module).setLevel(logging.WARN)

from config import Config

from agr.util.path import gzipped
from agr.gbs_prism.stage1 import Stage1
from agr.gbs_prism.paths import Paths
from agr.seq.fastq_sample import FastqSample

c = Config(**config)
stage1= Stage1(c.run, c.fastq_link_farm)
paths = Paths(c.postprocessing_root, c.run)

all_cohorts = [cohort for library in stage1.libraries for cohort in stage1.cohorts(library)]
all_fastq_links = set([fastq_link for cohort in all_cohorts for fastq_link in stage1.fastq_links(cohort)])

bwa_mapping_fastq_sample = {cohort:FastqSample(out_dir=paths.gbs.bwa_mapping_dir(cohort), sample_rate=0.00005, minimum_sample_size=150000) for cohort in all_cohorts}

# Ensure we have the directory structure we need in advance
for cohort in all_cohorts:
    paths.make_cohort_dirs(cohort)

rule default:
    input:
        [gzipped(bwa_mapping_fastq_sample[cohort].output(fastq_link)) for cohort in all_cohorts for fastq_link in stage1.fastq_links(cohort)],
    default_target: True

ruleorder: bwa_mapping_fastq_sample
rule bwa_mapping_fastq_sample:
    input:
        fastq_links = all_fastq_links
    output:
        [bwa_mapping_fastq_sample[cohort].output(fastq_link) for cohort in all_cohorts for fastq_link in stage1.fastq_links(cohort)]
    run:
        for cohort in all_cohorts:
            for fastq_link in stage1.fastq_links(cohort):
                bwa_mapping_fastq_sample[cohort].run(fastq_link)

rule gzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}",
               otherwise="/N/A")
    output: "{path}.gz"
    shell: "gzip -k {input}"
