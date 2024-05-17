from agr.prism.seq.sequencer_run import SequencerRun
from agr.prism.seq.postprocessor import PostProcessor
from agr.prism.seq.sample_sheet import NovaseqSampleSheet


def write_sample_sheet(sequencer_run: SequencerRun, post_processor: PostProcessor):
    sample_sheet = NovaseqSampleSheet(sequencer_run.sample_sheet_path)
    sample_sheet.write_harmonised(post_processor.sample_sheet_path)
