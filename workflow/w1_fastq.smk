configfile: "config/pipeline_config.yaml"

# temporary import path until library is installed as a Python package
sys.path.append(Path(workflow.basedir).parent.joinpath("src").as_posix())

from config import Config
from agr.prism.seq.sequencer_run import SequencerRun
from agr.prism.seq.sample_sheet import NovaseqSampleSheet
from agr.prism.seq.postprocessor import PostProcessor
from agr.prism.seq.bclconvert import BclConvert

# custom rule code lives here:
import w1_fastq

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
sample_sheet = NovaseqSampleSheet(sequencer_run.sample_sheet_path)
post_processor = PostProcessor(c.postprocessing_root, c.run)
bclconvert = BclConvert(sequencer_run.dir, post_processor.sample_sheet_path, post_processor.dir)

rule default:
    input:
        bclconvert.fastq_complete_path
    default_target: True

rule write_sample_sheet:
    log: "log/write_sample_sheet"
    output: post_processor.sample_sheet_path
    run:
        post_processor.ensure_dirs_exist()
        w1_fastq.write_sample_sheet(sequencer_run, post_processor)

rule bclconvert:
    input:
        sequencer_run_dir = sequencer_run.dir,
        sample_sheet = post_processor.sample_sheet_path,
    output:
        [ os.path.join(bclconvert.out_dir, fastq_file) for fastq_file in sample_sheet.fastq_files ],
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
        bclconvert.ensure_dirs_exist()
        bclconvert.run()
        bclconvert.check_expected_fastq_files(sample_sheet.fastq_files)
