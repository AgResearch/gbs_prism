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

from agr.util.path import gunzipped, gzipped
from agr.seq.sequencer_run import SequencerRun
from agr.seq.sample_sheet import SampleSheet
# TODO: use real bclconvert not fake one (fake one is very fast)
#from agr.seq.bclconvert import BclConvert
from agr.fake.bclconvert import BclConvert
from agr.seq.dedupe import Dedupe
from agr.seq.fastqc import Fastqc
from agr.seq.fastq_sample import FastqSample

from agr.gbs_prism.kmer_analysis import KmerAnalysis
from agr.gbs_prism.kmer_prism import KmerPrism
from agr.gbs_prism.gbs_keyfiles import GbsKeyfiles
from agr.gbs_prism.paths import Paths

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
sample_sheet = SampleSheet(sequencer_run.sample_sheet_path, impute_lanes=[1, 2])
paths = Paths(c.postprocessing_root, c.run)
bclconvert = BclConvert(in_dir=sequencer_run.dir, sample_sheet_path=paths.sample_sheet_path, out_dir=paths.bclconvert_dir)
fastqc = Fastqc(out_dir=paths.fastqc_dir)
kmer_run_fastq_sample = FastqSample(out_dir=paths.kmer_fastq_sample_dir, sample_rate=0.0002, minimum_sample_size=10000)
kmer_prism = KmerPrism(
    input_filetype="fasta",
    kmer_size=6,
    # this causes it to crash: 😩
    #assemble_low_entropy_kmers=True
)
kmer_analysis = KmerAnalysis(out_dir=paths.kmer_analysis_dir, kmer_prism=kmer_prism)
dedupe = Dedupe(out_dir=paths.dedupe_dir,
                tmp_dir="/tmp", # TODO maybe need tmp_dir on large scratch partition
                jvm_args=[]) # TODO fallback to default of 80g which Dedupe uses if we don't override it here
gbs_keyfiles = GbsKeyfiles(
    sequencer_run=sequencer_run,
    sample_sheet=sample_sheet,
    root=paths.root,
    out_dir=c.key_files_dir,
    fastq_link_farm=c.fastq_link_farm,
    backup_dir=c.gbs_backup_dir)

# Ensure we have the directory structure we need in advance
paths.makedirs()

rule default:
    input:
        [bclconvert.fastq_path(fastq_file) for fastq_file in sample_sheet.fastq_files],
        [gunzipped(bclconvert.fastq_path(fastq_file)) for fastq_file in sample_sheet.fastq_files],
        [fastqc.output(fastq_file) for fastq_file in sample_sheet.fastq_files],
        [gzipped(kmer_run_fastq_sample.output(fastq_file)) for fastq_file in sample_sheet.fastq_files],
        [kmer_analysis.output(kmer_run_fastq_sample.output(fastq_file)) for fastq_file in sample_sheet.fastq_files],
        [dedupe.output(fastq_file) for fastq_file in sample_sheet.fastq_files],
        gbs_keyfiles.output()
    default_target: True

rule write_sample_sheet:
    log: "log/write_sample_sheet"
    output: paths.sample_sheet_path
    run:
        sample_sheet.write(paths.sample_sheet_path)

rule bclconvert:
    input:
        sequencer_run_dir = sequencer_run.dir,
        sample_sheet = paths.sample_sheet_path,
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
        fastq_path = bclconvert.fastq_path("{basename}.fastq.gz")
    output:
        fastqc.output("{basename}.fastq.gz"),
    run:
        fastqc.run(input.fastq_path)

ruleorder: kmer_run_fastq_sample > gunzip
rule kmer_run_fastq_sample:
    input:
        fastq_path = bclconvert.fastq_path("{basename}.fastq.gz")
    output:
        kmer_run_fastq_sample.output("{basename}.fastq.gz"),
    run:
        kmer_run_fastq_sample.run(input.fastq_path)

ruleorder: kmer_analysis > gunzip
rule kmer_analysis:
    input:
        fastq_sample = kmer_run_fastq_sample.output("{basename}.fastq.gz")
    output:
        kmer_analysis.output(kmer_run_fastq_sample.output("{basename}.fastq.gz"))
    run:
        kmer_analysis.run(input.fastq_sample)

ruleorder: dedupe > gzip > gunzip
rule dedupe:
    input:
        fastq_path = bclconvert.fastq_path("{basename}.fastq.gz")
    output:
        dedupe.output("{basename}.fastq.gz"),
    run:
        dedupe.run(input.fastq_path)

rule gbs_keyfiles:
    output:
        gbs_keyfiles.output()
    run:
        gbs_keyfiles.create()

rule gunzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}.gz",
               otherwise="/N/A")
    output: "{path}"
    shell: "gunzip -k {input}"

rule gzip:
    input:
        branch(lambda wildcards: not wildcards["path"].endswith(".gz"),
               then="{path}",
               otherwise="/N/A")
    output: "{path}.gz"
    shell: "gzip -k {input}"
