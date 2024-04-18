configfile: "config/pipeline_config.yaml"

from config import Config
from agr.sequencer_run import SequencerRun
from agr.postprocessor import PostProcessor

# all the code for our rules is here:
import w1_fastq

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
post_processor = PostProcessor(c.postprocessing_root, c.run)

rule default:
    input: post_processor.sample_sheet_path
    default_target: True

rule write_sample_sheet:
    log: "log/write_sample_sheet"
    output: post_processor.sample_sheet_path
    run:
        w1_fastq.write_sample_sheet(sequencer_run, post_processor)
