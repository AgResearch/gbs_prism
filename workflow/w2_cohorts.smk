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

from agr.util.path import gzipped, trimmed
from agr.gbs_prism.stage1 import Stage1Outputs
from agr.gbs_prism.stage2 import Stage2Targets
from agr.gbs_prism.paths import Paths
from agr.gbs_prism.types import Cohort
from agr.seq.fastq_sample import FastqSample
from agr.seq.cutadapt import cutadapt

c = Config(**config)
paths = Paths(c.postprocessing_root, c.run)
stage1= Stage1Outputs(c.run, c.fastq_link_farm)
stage2 = Stage2Targets(c.run, stage1, paths.gbs)
bwa_mapping_sample = FastqSample(
    sample_rate=0.00005,
    minimum_sample_size=150000,
)

# Ensure we have the directory structure we need in advance
stage2.make_dirs()

rule default:
    input:
        #[gzipped(fastq_file) for fastq_file in stage2.all_bwa_mapping_sampled],
        stage2.all_bwa_mapping_sampled_trimmed(bwa_mapping_sample.moniker),
        stage2.all_cohort_targets,
    default_target: True

# this links the fastq files for each cohort separately
# so that subsequent dependencies can be properly captured in wildcarded paths
rule cohort_fastq_links:
    input:
        stage1.all_fastq_links
    output:
        stage2.all_cohort_fastq_links
    run:
        stage2.create_all_cohort_fastq_links()


rule sample_for_bwa_mapping:
    input:
        fastq_file="{path}/{cohort}/fastq/{basename}.fastq.gz"
    output:
        # the ugly name is copied from legacy gbs_prism
        sampled_fastq_file="{path}/bwa_mapping/{cohort}/{basename}.fastq.gz.fastq.%s.fastq" % bwa_mapping_sample.moniker
    run:
        bwa_mapping_sample.run(in_path=input.fastq_file, out_path=output.sampled_fastq_file)
        
rule cutadapt:
    input:
        fastq_file="{path}/{basename}.fastq"
    output:
        trimmed_fastq_file="{path}/{basename}.trimmed.fastq"
    run:
        cutadapt(in_path=input.fastq_file, out_path=output.trimmed_fastq_file)

rule keyfile_for_tassel:
    output:
        keyfile = "%s/%s.{cohort}.key" % (paths.gbs.run_root, c.run)
    run:
        stage2.get_keyfile_for_tassel(Cohort.parse(wildcards.cohort), out_path=output.keyfile)

rule gbsx_keyfile:
    output:
        keyfile = "%s/%s.{cohort}.gbsx.key" % (paths.gbs.run_root, c.run)
    run:
        stage2.get_gbsx_keyfile(Cohort.parse(wildcards.cohort), out_path=output.keyfile)

rule unblind_script:
    output:
        script  = "%s/%s.{cohort}.unblind.sed" % (paths.gbs.run_root, c.run)
    run:
        stage2.get_unblind_script(Cohort.parse(wildcards.cohort), out_path=output.script)

rule gzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}",
               otherwise="/N/A")
    output: "{path}.gz"
    shell: "gzip -k {input}"

wildcard_constraints:
    # cohort has four dot-separated components with no slashes, and we're fairly liberal besides that
    cohort=r"[^./]+\.[^./]+\.[^./]+\.[^./]+",
    sample_rate=r"s\.[0-9]+",
    # a filename with no path component
    basename=r"[^/]+"
