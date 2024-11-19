configfile: "config/pipeline_config.yaml"

# temporary import path until library is installed as a Python package
sys.path.append(Path(workflow.basedir).parent.joinpath("src").as_posix())

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')
                    #filename='gbs_prism.log',
                    #filemode='a')
for noisy_module in ['asyncio', 'pulp.apis.core', 'urllib3']:
    logging.getLogger(noisy_module).setLevel(logging.WARN)

from config import Config

from agr.util.path import gzipped, trimmed
from agr.gbs_prism.gbs_target_spec import read_gbs_target_spec
from agr.gbs_prism.gbs_targets import GbsConfig, GbsTargets
from agr.gbs_prism.paths import Paths
from agr.seq.fastq_sample import FastqSample
from agr.seq.cutadapt import cutadapt
from agr.seq.bwa import Bwa

c = Config(**config)
paths = Paths(c.postprocessing_root, c.run)
bwa_sample = FastqSample(
    sample_rate=0.00005,
    minimum_sample_size=150000,
)
bwa = Bwa(barcode_len=10)
gbs_config = GbsConfig(
    run_name=c.run,
    paths=paths.gbs,
    alignment_sample_moniker=bwa_sample.moniker,
    aligner="bwa",
    alignment_moniker=bwa.moniker)
gbs_target_spec = read_gbs_target_spec(paths.gbs.target_spec_path)
from pprint import pp
pp("gbs_target_spec: %s" % gbs_target_spec)
gbs_targets = GbsTargets(gbs_config, gbs_target_spec)

# Ensure we have the directory structure we need in advance
gbs_targets.make_dirs()

rule default:
    input:
        #[gzipped(fastq_file) for fastq_file in gbs_targets.all_bwa_sampled],
        gbs_targets.paths,
    default_target: True

# this links the fastq files for each cohort separately
# so that subsequent dependencies can be properly captured in wildcarded paths
rule cohort_fastq_links:
    output:
        gbs_targets.local_fastq_links
    run:
        gbs_targets.create_local_fastq_links()


rule sample_for_bwa:
    input:
        fastq_file="{path}/{cohort}/fastq/{basename}.fastq.gz"
    output:
        # the ugly name is copied from legacy gbs_prism
        sampled_fastq_file="{path}/bwa_mapping/{cohort}/{basename}.fastq.gz.fastq.%s.fastq" % bwa_sample.moniker
    run:
        bwa_sample.run(in_path=input.fastq_file, out_path=output.sampled_fastq_file)
        
rule cutadapt:
    input:
        fastq_file="{path}/{basename}.fastq"
    output:
        trimmed_fastq_file="{path}/{basename}.trimmed.fastq"
    run:
        cutadapt(in_path=input.fastq_file, out_path=output.trimmed_fastq_file)

rule bwa_aln:
    input:
        fastq_file="{path}/{cohort}/{basename}.trimmed.fastq"
    output:
        sai_file="{path}/{cohort}/{basename}.trimmed.fastq.bwa.{reference_genome}.%s.sai" % bwa.moniker,
    run:
        cohort_spec = gbs_target_spec.cohorts[wildcards.cohort]
        bwa_reference = cohort_spec.alignment_references[wildcards.reference_genome]
        bwa.aln(in_path=input.fastq_file, out_path=output.sai_file, reference=bwa_reference)

rule bwa_samse:
    input:
        fastq_file="{path}/{cohort}/{basename}.trimmed.fastq",
        sai_file="{path}/{cohort}/{basename}.trimmed.fastq.bwa.{reference_genome}.%s.sai" % bwa.moniker,
    output:
        bam_file="{path}/{cohort}/{basename}.trimmed.fastq.bwa.{reference_genome}.%s.bam" % bwa.moniker,
    run:
        cohort_spec = gbs_target_spec.cohorts[wildcards.cohort]
        bwa_reference = cohort_spec.alignment_references[wildcards.reference_genome]
        bwa.samse(sai_path=input.sai_file, fastq_path=input.fastq_file, out_path=output.bam_file, reference=bwa_reference)

rule bam_stats:
    input:
        bam_file="{path}/{basename}.bam"
    output:
        stats_file="{path}/{basename}.stats"
    shell:
        "samtools flagstat {input.bam_file} >{output.stats_file}"

rule keyfile_for_tassel:
    output:
        keyfile = "%s/%s.{cohort}.key" % (paths.gbs.run_root, c.run)
    run:
        cohort = gbs_targets.cohorts[wildcards.cohort]
        cohort.get_keyfile_for_tassel(out_path=output.keyfile)

rule gbsx_keyfile:
    output:
        keyfile = "%s/%s.{cohort}.gbsx.key" % (paths.gbs.run_root, c.run)
    run:
        cohort = gbs_targets.cohorts[wildcards.cohort]
        cohort.get_gbsx_keyfile(out_path=output.keyfile)

rule unblind_script:
    output:
        script  = "%s/%s.{cohort}.unblind.sed" % (paths.gbs.run_root, c.run)
    run:
        cohort = gbs_targets.cohorts[wildcards.cohort]
        cohort.get_unblind_script(out_path=output.script)

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
    # a reference genome is essentially the basename of the file we use
    reference_genome=r"[^/]+",
    sample_rate=r"s\.[0-9]+",
    # a filename with no path component
    basename=r"[^/]+"
