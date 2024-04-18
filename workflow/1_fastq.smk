configfile: "config/pipeline_config.yaml"

from config import Config
from agr.sequencer_run import SequencerRun
from agr.postprocessor import PostProcessor
from agr.sample_sheet import NovaseqSampleSheet

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
post_processor = PostProcessor(c.postprocessing_root, c.run)

rule default:
    input:
        post_processor.sample_sheet_path
    default_target: True

rule write_sample_sheet:
    output:
        post_processor.sample_sheet_path
    run:
        sequencer_run.await_complete()
        post_processor.ensure_run_dir_exists()

        sample_sheet = NovaseqSampleSheet(sequencer_run.sample_sheet_path)
        sample_sheet.write_harmonised(post_processor.sample_sheet_path)
