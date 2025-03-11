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
      hours: 1,
    },
    custom_attributes: customised({
      // all string-valued
      ntasks: '1',
      'cpus-per-task': '1',
      mem: '4G',
    }),
  },
};

local Tassel3Default = ToolDefault {
  java_initial_heap: '512M',
  java_max_heap: '20G',
  job_attributes+: {
    custom_attributes+: customised({
      mem: '20G',
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

    dedupe: ToolDefault {
      java_max_heap: '520G',
      job_attributes+: {
        queue_name: 'hugemem',
        duration: {
          hours: 2,
        },
        custom_attributes+: customised({
          'cpus-per-task': '1',
          mem: '550G',
        }),
      },
    },

    'tassel3-FastqToTagCount': Tassel3Default {
      java_max_heap: '5G',
      job_attributes+: {
        custom_attributes+: customised({
          mem: '5G',
        }),
      },
    },

    'tassel3-MergeTaxaTagCount': Tassel3Default,

    'tassel3-TagCountToTagPair': Tassel3Default,

    'tassel3-TagPairToTBT': Tassel3Default,

    'tassel3-TBTToMapInfo': Tassel3Default,

    'tassel3-MapInfoToHapMap': Tassel3Default,
  },
}
