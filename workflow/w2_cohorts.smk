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

from agr.gbs_prism.stage1 import Stage1
from agr.gbs_prism.paths import Paths
from agr.seq.fastq_sample import FastqSample

c = Config(**config)
stage1= Stage1(c.run, c.fastq_link_farm)
paths = Paths(c.postprocessing_root, c.run)

all_cohorts = [cohort for library in stage1.libraries for cohort in stage1.cohorts(library)]

bwa_mapping_fastq_sample = {cohort:FastqSample(out_dir=paths.gbs.bwa_mapping_dir(cohort), sample_rate=0.00005, minimum_sample_size=150000) for cohort in all_cohorts}

# Ensure we have the directory structure we need in advance
for cohort in all_cohorts:
    paths.make_cohort_dirs(cohort)

# TODO remove
for cohort in all_cohorts:
    print("cohort: %s" % cohort)
    fastq_files = stage1.fastq_files(cohort)
    print("fastq_files for cohort %s: %s" % (cohort, ",".join(fastq_files)))
    # for fastq_file in fastq_files:
    #     bwa_mapping_sample = bwa_mapping_fastq_sample[cohort].output(fastq_file)
    #     print("bwa_mapping sample for %s: %s" (fastq_file, bwa_mapping_sample))



rule default:
    input:
        [bwa_mapping_fastq_sample[cohort].output(fastq_file) for cohort in all_cohorts for fastq_file in stage1.fastq_files(cohort)],
    default_target: True

