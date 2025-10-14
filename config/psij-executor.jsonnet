// PSI/J executor configuration, i.e. values which have no effect on pipeline ouput, only performance, etc.
//
// To view the equivalent JSON simply feed this file to jsonnet

local job_prefix = 'gbs_prism.';

local config = import 'psij-executor.libsonnet';

{
  tools: config.tools(job_prefix),
}
