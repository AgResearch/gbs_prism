// deployment configuration, that is, values which have no effect on pipeline ouput, only performance, etc.

local ToolDefault = {
  executor: 'slurm',
  job_attributes: {
    queue_name: 'inv-iranui',  // TODO change for eRI
    custom_attributes: {
      // all string-valued
      ntasks: '1',
      'cpus-per-task': '1',
      mem: '4G',
      // time: '24:00:00', // this is the eRI default
    },
  },
};

local Tassel3Default = ToolDefault {
  java_initial_heap: '512M',
  java_max_heap: '20G',
  job_attributes+: {
    custom_attributes+: {
      mem: '20G',
    },
  },
};

{
  tools: {
    dedupe: ToolDefault {
      java_max_heap: '200G',
      job_attributes+: {
        custom_attributes+: {
          mem: '8G',
        },
      },
    },

    FastqToTagCount: Tassel3Default {
      java_max_heap: '5G',
      job_attributes+: {
        custom_attributes+: {
          mem: '5G',
        },
      },
    },

    MergeTaxaTagCount: Tassel3Default,

    TagCountToTagPair: Tassel3Default,

    TagPairToTBT: Tassel3Default,

    TBTToMapInfo: Tassel3Default,

    MapInfoToHapMap: Tassel3Default,
  },
}
