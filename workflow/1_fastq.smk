configfile: "config/pipeline_config.yaml"

from config import Config
from agr.sequencer_run import SequencerRun
from agr.postprocessor import PostProcessor

c = Config(**config)
sequencer_run = SequencerRun(c.seq_root, c.run)
post_processor = PostProcessor(c.postprocessing_root, c.run)

rule await_run_complete:
  output:
      directory(post_processor.run_dir)
  run:
      sequencer_run.await_complete()
      post_processor.create_run_dir()
