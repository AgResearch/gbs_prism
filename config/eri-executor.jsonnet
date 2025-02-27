// executor configuration, that is, values which have no effect on pipeline ouput, only performance, etc.
//
// To view the equivalent JSON simply feed this file to jsonnet

local executor = 'slurm';

// custom_attributes need to have an executor prefix, which is done by customised
local customised(attrs) = { [executor + '.' + k]: attrs[k] for k in std.objectFields(attrs) };

local ToolDefault = {
  executor: executor,
  job_prefix: 'playpen.',
  job_attributes: {
    queue_name: 'compute',
    custom_attributes: customised({
      // all string-valued
      ntasks: '1',
      'cpus-per-task': '1',
      mem: '4G',
      // time: '24:00:00', // this is the eRI default
    }),
  },
};

local Tassel3Default = ToolDefault {
  java_initial_heap: '512M',
  java_max_heap: '20G',
  job_attributes+: {
    custom_attributes: customised({
      mem: '20G',
    }),
  },
};

{
  tools: {
    default: ToolDefault,

    dedupe: ToolDefault {
      java_max_heap: '200G',
      job_attributes+: {
        custom_attributes: customised({
          mem: '8G',
        }),
      },
    },

    'tassel3-FastqToTagCount': Tassel3Default {
      java_max_heap: '5G',
      job_attributes+: {
        custom_attributes: customised({
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
