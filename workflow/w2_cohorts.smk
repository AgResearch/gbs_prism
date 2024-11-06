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
from agr.gbs_prism.stage1 import Stage1Outputs
from agr.gbs_prism.stage2 import Stage2Targets
from agr.gbs_prism.paths import Paths

c = Config(**config)
paths = Paths(c.postprocessing_root, c.run)
stage1= Stage1Outputs(c.run, c.fastq_link_farm)
stage2 = Stage2Targets(stage1, paths.gbs)

# Ensure we have the directory structure we need in advance
stage2.make_dirs()

rule default:
    input:
        [gzipped(fastq_file) for fastq_file in stage2.all_bwa_mapping_sampled],
        stage2.all_bwa_mapping_sampled_trimmed
    default_target: True

rule sample_for_bwa_mapping:
    input:
        stage1.all_fastq_links
    output:
        stage2.all_bwa_mapping_sampled
    run:
        stage2.sample_all_fastq_links_for_bwa_mapping()
        
rule trim_samples_for_bwa_mapping:
    input:
        stage2.all_bwa_mapping_sampled
    output:
        stage2.all_bwa_mapping_sampled_trimmed
    run:
        stage2.trim_all_bwa_mapping_sampled()

rule gzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}",
               otherwise="/N/A")
    output: "{path}.gz"
    shell: "gzip -k {input}"
