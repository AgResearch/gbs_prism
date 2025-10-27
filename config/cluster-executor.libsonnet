// executor configuration, that is, values which have no effect on pipeline ouput, only performance, etc.
//
// This file should be imported by cluster-executor.jsonnet

local executor = 'slurm';

// custom_attributes need to have an executor prefix, which is done by customised
local customised(attrs) = { [executor + '.' + k]: attrs[k] for k in std.objectFields(attrs) };

local tool_default(job_prefix) = {
  executor: executor,
  job_prefix: job_prefix,
  job_attributes: {
    queue_name: 'compute',
    duration: {
      hours: 6,
    },
    custom_attributes: customised({
      ntasks: '1',
      'cpus-per-task': '4',
      mem: '8G',
    }),
  },
};

local tassel3_default(job_prefix) = tool_default(job_prefix) {
  java_initial_heap: '512M',
  java_max_heap: '2G',
  job_attributes+: {
    custom_attributes+: customised({
      'cpus-per-task': '1',
      mem: '4G',
    }),
  },
};

{
  customised:: customised,

  tools(job_prefix)::
    {
      default: tool_default(job_prefix),

      bcl_convert: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            'cpus-per-task': '16',
            mem: '50G',
          }),
        },
      },

      fastqc: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            'cpus-per-task': '8',
            mem: '8G',
          }),
        },
      },

      multiqc: tool_default(job_prefix),

      seqtk_sample: tool_default(job_prefix),

      kmer_prism: tool_default(job_prefix),

      dedupe: tool_default(job_prefix) {
        java_max_heap: '380G',
        job_attributes+: {
          queue_name: 'hugemem',
          duration: {
            hours: 6,
          },
          custom_attributes+: customised({
            'cpus-per-task': '6',
            mem: '400G',
          }),
        },
      },

      cutadapt: tool_default(job_prefix),

      bwa_aln: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            mem: '8G',
          }),
        },
      },

      bwa_samse: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            mem: '8G',
          }),
        },
      },

      tassel3_FastqToTagCount: tassel3_default(job_prefix) {
        java_max_heap: '4G',
        job_attributes+: {
          custom_attributes+: customised({
            mem: '6G',
          }),
        },
      },

      tassel3_MergeTaxaTagCount: tassel3_default(job_prefix) {
        java_max_heap: '32G',
        job_attributes+: {
          duration: {
            hours: 12,
          },
          custom_attributes+: customised({
            mem: '34G',
          }),
        },
      },

      tassel3_TagCountToTagPair: tassel3_default(job_prefix),

      tassel3_TagPairToTBT: tassel3_default(job_prefix) {
        java_max_heap: '8G',
        job_attributes+: {
          custom_attributes+: customised({
            mem: '10G',
          }),
        },
      },

      tassel3_TBTToMapInfo: tassel3_default(job_prefix),

      tassel3_MapInfoToHapMap: tassel3_default(job_prefix),

      KGD: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            'cpus-per-task': '4',
            mem: '32G',
          }),
        },
      },

      GUSbase: tool_default(job_prefix) {
        job_attributes+: {
          custom_attributes+: customised({
            mem: '8G',
          }),
        },
      },
    },
}
