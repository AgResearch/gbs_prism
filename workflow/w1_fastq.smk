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

from agr.util.path import gunzipped, gzipped
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet
# TODO: use real bclconvert not fake one (fake one is very fast)
#from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import BclConvert
from agr.seq.dedupe import dedupe
from agr.seq.fastqc import fastqc
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.stage1 import Stage1Targets
from agr.gbs_prism.kmer_analysis import run_kmer_analysis
from agr.gbs_prism.kmer_prism import KmerPrism
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import Paths

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
sample_sheet = SampleSheet(sequencer_run.sample_sheet_path, impute_lanes=[1, 2])
paths = Paths(c.postprocessing_root, c.run)
stage1 = Stage1Targets(c.run, sample_sheet, paths.seq)
bclconvert = BclConvert(in_dir=sequencer_run.dir, sample_sheet_path=paths.seq.sample_sheet_path, out_dir=paths.seq.bclconvert_dir)
kmer_sample = FastqSample(sample_rate=0.0002, minimum_sample_size=10000)
kmer_prism = KmerPrism(
    input_filetype="fasta",
    kmer_size=6,
    # this causes it to crash: 😩
    #assemble_low_entropy_kmers=True
)
gbs_keyfiles = GbsKeyfiles(
    sequencer_run=sequencer_run,
    sample_sheet=sample_sheet,
    root=paths.illumina_platform_root,
    out_dir=c.keyfiles_dir,
    fastq_link_farm=c.fastq_link_farm,
    backup_dir=c.gbs_backup_dir)

# Ensure we have the directory structure we need in advance
paths.make_run_dirs()

rule default:
    input:
        stage1.all_bclconvert_fastq_files,
        [gunzipped(fastq_file) for fastq_file in stage1.all_bclconvert_fastq_files],
        stage1.all_fastqc,
        stage1.all_kmer_sampled(kmer_sample.moniker),
        [gzipped(sampled_fastq_file) for sampled_fastq_file in stage1.all_kmer_sampled(kmer_sample.moniker)],
        stage1.all_kmer_analysis(kmer_sample.moniker, kmer_prism.moniker),
        stage1.all_dedupe,
        stage1.all_gbs_keyfiles(c.keyfiles_dir)
    default_target: True

rule write_sample_sheet:
    log: "log/write_sample_sheet"
    output: paths.seq.sample_sheet_path
    run:
        sample_sheet.write(paths.seq.sample_sheet_path)

rule bclconvert:
    input:
        sequencer_run_dir = sequencer_run.dir,
        sample_sheet = paths.seq.sample_sheet_path,
    output:
        [bclconvert.fastq_path(fastq_file) for fastq_file in sample_sheet.fastq_files],
        fastq_complete = bclconvert.fastq_complete_path,
        top_unknown = bclconvert.top_unknown_path,
    log:
        bclconvert_log = bclconvert.log_path
    # TODO:
    #benchmark:
    #    bclconvert_benchmark = bclconvert.benchmark_path
    threads: 36
    resources:
        mem_gb = lambda wildcards, attempt: 128 + ((attempt - 1) * 32),
        time = lambda wildcards, attempt: 480 + ((attempt - 1) * 120),
    run:
        bclconvert.run()
        bclconvert.check_expected_fastq_files(sample_sheet.fastq_files)

ruleorder: fastqc > gunzip
rule fastqc:
    input:
        fastq_file="{path}/bclconvert/{basename}.fastq.gz"
    output:
        fastqc_html="{path}/fastqc_run/fastqc/{basename}_fastqc.html",
        fastqc_zip="{path}/fastqc_run/fastqc/{basename}_fastqc.zip",
    run:
        fastqc(in_path=input.fastq_file, out_dir="%s/fastqc_run/fastqc" % wildcards.path)

ruleorder: sample_for_kmer_analysis > gunzip
rule sample_for_kmer_analysis:
    input:
        fastq_file="{path}/bclconvert/{basename}.fastq.gz"
    output:
        # the ugly name is copied from legacy gbs_prism
        sampled_fastq_file="{path}/kmer_run/fastq_sample/{basename}.fastq.gz.fastq.%s.fastq" % kmer_sample.moniker
    run:
        kmer_sample.run(in_path=input.fastq_file, out_path=output.sampled_fastq_file)

ruleorder: kmer_analysis > gunzip
rule kmer_analysis:
    input:
        fastq_sample="{path}/kmer_run/fastq_sample/{basename}.fastq"
    output:
        kmer_analysis="{path}/kmer_run/kmer_analysis/{basename}.fastq.%s.1" % kmer_prism.moniker
    run:
        run_kmer_analysis(in_path=input.fastq_sample, out_path=output.kmer_analysis, kmer_prism=kmer_prism)

ruleorder: dedupe > gzip > gunzip
rule dedupe:
    input:
        fastq_file="{path}/bclconvert/{basename}.fastq.gz"
    output:
        deduped_fastq_file="{path}/dedupe/{basename}.fastq.gz",
    run:
        dedupe(
            in_path=input.fastq_file,
            out_path=output.deduped_fastq_file,
            tmp_dir="/tmp", # TODO maybe need tmp_dir on large scratch partition
            jvm_args=[]) # TODO fallback to default of 80g which Dedupe uses if we don't override it here

rule gbs_keyfiles:
    input:
        stage1.all_dedupe,
    output:
        stage1.all_gbs_keyfiles(c.keyfiles_dir),
    run:
        gbs_keyfiles.create()

# only for bclconvert output to avoid cyclic graph exception
rule gunzip:
    input:
        branch(lambda wildcards: not wildcards["basename"].endswith(".gz"),
               then="{path}/bclconvert/{basename}.gz",
               otherwise="/N/A")
    output: "{path}/bclconvert/{basename}"
    shell: "gunzip -k {input}"

rule gzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}",
               otherwise="/N/A")
    output: "{path}.gz"
    shell: "gzip -k {input}"

wildcard_constraints:
    sample_rate=r"s\.[0-9]+",
    # a filename with no path component
    basename=r"[^/]+"
