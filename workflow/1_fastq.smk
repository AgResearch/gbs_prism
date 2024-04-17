configfile: "config/pipeline_config.yaml"

in_root = config["path"]["in_root"]
out_root = config["path"]["out_root"]
run = config["run"]
run_info_path = os.path.join(in_root, run, "RunInfo.xml")
rta_complete_path = os.path.join(in_root, run, "RTAComplete.txt.oops")

rule await_rta_complete:
  input:
      expand("{run_info_path}", run_info_path=run_info_path)
  run:
      import time
      while not os.path.exists(rta_complete_path):
          print("%s not found, waiting ..." % rta_complete_path, file=sys.stderr)
          time.sleep(10)
