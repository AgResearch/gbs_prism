// executor configuration, that is, values which have no effect on pipeline ouput, only performance, etc.
//
// To view the equivalent JSON simply feed this file to jsonnet

local executor = 'slurm';

// custom_attributes need to have an executor prefix, which is done by customised
local customised(attrs) = { [executor + '.' + k]: attrs[k] for k in std.objectFields(attrs) };

local ToolDefault = {
  executor: executor,
  job_prefix: 'gbs_prism.',
  job_attributes: {
    queue_name: 'compute',
    duration: {
      // fields are Python datetime.timedelta
      // TODO reduce this down again
      hours: 4,
    },
    custom_attributes: customised({
      // all string-valued
      ntasks: '1',
      // TODO bumped up the defaults for tuning resource requirements, need to drop them down again
      'cpus-per-task': '1',
      mem: '1G',
    }),
  },
};

local Tassel3Default = ToolDefault {
  java_initial_heap: '512M',
  java_max_heap: '2G',
  job_attributes+: {
    custom_attributes+: customised({
      'cpus-per-task': '1',
      mem: '2G',
    }),
  },
};

{
  tools: {
    default: ToolDefault,

    bcl_convert: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          'cpus-per-task': '8',
          mem: '50G',
        }),
      },
    },

    fastqc: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          mem: '4G',
        }),
      },
    },

    multiqc: ToolDefault,

    seqtk_sample: ToolDefault,

    kmer_prism: ToolDefault,

    dedupe: ToolDefault {
      java_max_heap: '520G',
      job_attributes+: {
        queue_name: 'hugemem',
        duration: {
          hours: 2,
        },
        custom_attributes+: customised({
          mem: '550G',
        }),
      },
    },

    cutadapt: ToolDefault,

    bwa_aln: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          mem: '8G',
        }),
      },
    },

    bwa_samse: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          mem: '8G',
        }),
      },
    },

    tassel3_FastqToTagCount: Tassel3Default,

    tassel3_MergeTaxaTagCount: Tassel3Default {
      java_max_heap: '32G',
      job_attributes+: {
        custom_attributes+: customised({
          mem: '32G',
        }),
      },
    },

    tassel3_TagCountToTagPair: Tassel3Default,

    tassel3_TagPairToTBT: Tassel3Default {
      java_max_heap: '8G',
      job_attributes+: {
        custom_attributes+: customised({
          mem: '8G',
        }),
      },
    },

    tassel3_TBTToMapInfo: Tassel3Default,

    tassel3_MapInfoToHapMap: Tassel3Default,

    KGD: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          'cpus-per-task': '4',
          mem: '32G',
        }),
      },
    },

    GUSbase: ToolDefault {
      job_attributes+: {
        custom_attributes+: customised({
          mem: '8G',
        }),
      },
    },
  },
}
