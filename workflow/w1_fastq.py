from workflow.agr.sequencer_run import SequencerRun
from workflow.agr.postprocessor import PostProcessor
from workflow.agr.sample_sheet import NovaseqSampleSheet

def write_sample_sheet(sequencer_run: SequencerRun, post_processor: PostProcessor):
    sample_sheet = NovaseqSampleSheet(sequencer_run.sample_sheet_path)
    sample_sheet.write_harmonised(post_processor.sample_sheet_path)
