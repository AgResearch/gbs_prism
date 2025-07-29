// executor configuration, that is, values which have no effect on pipeline ouput, only performance, etc.
//
// This file should be imported by cluster-executor.jsonnet

// custom_attributes need to have an executor prefix, which is done by customised
local customised(executor, attrs) = { [executor + '.' + k]: attrs[k] for k in std.objectFields(attrs) };

local tool_default(job_prefix, executor) = {
  executor: executor,
  job_prefix: job_prefix,
  job_attributes: {
    queue_name: 'compute',
    duration: {
      // fields are Python datetime.timedelta
      // TODO reduce this down again
      hours: 4,
    },
    custom_attributes: customised(executor, {
      // all string-valued
      ntasks: '1',
      // TODO bumped up the defaults for tuning resource requirements, need to drop them down again
      'cpus-per-task': '1',
      mem: '1G',
    }),
  },
};

local tassel3_default(job_prefix, executor) = tool_default(job_prefix, executor) {
  java_initial_heap: '512M',
  java_max_heap: '2G',
  job_attributes+: {
    custom_attributes+: customised(executor, {
      'cpus-per-task': '1',
      mem: '4G',
    }),
  },
};

{
  tools(job_prefix, executor='slurm')::
    {
      default: tool_default(job_prefix, executor),

      bcl_convert: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            'cpus-per-task': '8',
            mem: '50G',
          }),
        },
      },

      fastqc: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            mem: '4G',
          }),
        },
      },

      multiqc: tool_default(job_prefix, executor),

      seqtk_sample: tool_default(job_prefix, executor),

      kmer_prism: tool_default(job_prefix, executor),

      dedupe: tool_default(job_prefix, executor) {
        java_max_heap: '520G',
        job_attributes+: {
          queue_name: 'hugemem',
          duration: {
            hours: 2,
          },
          custom_attributes+: customised(executor, {
            'cpus-per-task': '6',
            mem: '550G',
          }),
        },
      },

      cutadapt: tool_default(job_prefix, executor),

      bwa_aln: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            mem: '8G',
          }),
        },
      },

      bwa_samse: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            // very short running jobs require more frequent sampling to measure resource usage,
            // but this comes with a cost, so should be only a temporary setting
            // 'acctg-freq': '1',
            mem: '8G',
          }),
        },
      },

      tassel3_FastqToTagCount: tassel3_default(job_prefix, executor) {
        java_max_heap: '4G',
        job_attributes+: {
          custom_attributes+: customised(executor, {
            mem: '4G',
          }),
        },
      },

      tassel3_MergeTaxaTagCount: tassel3_default(job_prefix, executor) {
        java_max_heap: '32G',
        job_attributes+: {
          duration: {
            // because one of these exceeded 4 hours 🤷
            hours: 8,
          },
          custom_attributes+: customised(executor, {
            mem: '32G',
          }),
        },
      },

      tassel3_TagCountToTagPair: tassel3_default(job_prefix, executor),

      tassel3_TagPairToTBT: tassel3_default(job_prefix, executor) {
        java_max_heap: '8G',
        job_attributes+: {
          custom_attributes+: customised(executor, {
            mem: '8G',
          }),
        },
      },

      tassel3_TBTToMapInfo: tassel3_default(job_prefix, executor),

      tassel3_MapInfoToHapMap: tassel3_default(job_prefix, executor),

      KGD: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            'cpus-per-task': '4',
            mem: '32G',
          }),
        },
      },

      GUSbase: tool_default(job_prefix, executor) {
        job_attributes+: {
          custom_attributes+: customised(executor, {
            mem: '8G',
          }),
        },
      },
    },
}
