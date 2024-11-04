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

c = Config(**config)
stage1= Stage1(c.run)
paths = Paths(c.postprocessing_root, c.run)

print("libraries: %s" % ",".join(stage1.libraries))
for library in stage1.libraries:
    print("cohorts for library %s: %s" % (library, ",".join(stage1.libraries)))

#bwa_mapping_fastq_sample = {cohort:FastqSample(out_dir=paths.gbs.bwa_mapping_dir(cohort), sample_rate=0.00005, minimum_sample_size=150000) for library in stage1.libraries for cohort in stage1.cohorts(library)}

# Ensure we have the directory structure we need in advance
for library in stage1.libraries:
    for cohort in stage1.cohorts(library):
        paths.make_cohort_dirs(cohort)

rule default:
    input:
        []
        # [bwa_mapping_fastq_sample[cohort].output(fastq_file) for fastq_file in stage1.fastq_files(cohort) for cohort in stage1.cohorts],
    default_target: True

