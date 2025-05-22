{
  description = "Flake for gbs_prism";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    flake-utils.url = "github:numtide/flake-utils";
    bbmap = {
      url = "github:AgResearch/bbmap.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    bcl-convert = {
      url = "github:AgResearch/bcl-convert.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    cutadapt = {
      url = "github:AgResearch/cutadapt.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    tassel3 = {
      url = "github:AgResearch/tassel3/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    kgd = {
      url = "github:AgResearch/KGD?ref=refs/tags/v1.3.1";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    GUSbase = {
      url = "github:tpbilton/GUSbase";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    gquery = {
      # TODO: merge and use main
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/repackaging";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    geno-import = {
      # TODO: merge and use main
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/geno_import?ref=refs/heads/repackaging";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.gquery.follows = "gquery";
    };
    redun = {
      url = "github:AgResearch/redun.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    seffs = {
      url = "github:AgResearch/seffs/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs:
    inputs.flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import inputs.nixpkgs {
            inherit system;
          };

          flakePkgs = {
            bbmap = inputs.bbmap.packages.${system}.default;
            bcl-convert = inputs.bcl-convert.packages.${system}.default;
            cutadapt = inputs.cutadapt.packages.${system}.default;
            tassel3 = inputs.tassel3.packages.${system}.default;
            kgd-src = inputs.kgd.packages.${system}.src;
            GUSbase = inputs.GUSbase.packages.${system}.default;
            gquery = inputs.gquery.packages.${system}.default;
            geno-import = inputs.geno-import.packages.${system}.default;
            seffs = inputs.seffs.packages.${system}.default;
          };

          gquery-export-env = env: inputs.gquery.export-env.${system} env;

          gquery-lmod-setenv = inputs.gquery.apps.${system}.lmod-setenv;

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              name = "gbs-prism-api";
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch
                python3Packages.hatchling
              ];

              propagatedBuildInputs = pipeline-packages;
            };

          wrap-script = attrs: pkgs.stdenv.mkDerivation ({
            nativeBuildInputs = [ pkgs.makeWrapper ];

            dontUnpack = true;
            dontBuild = true;

            installPhase = ''
              mkdir -p $out/bin
              runHook preInstall
              # strip the path and digest, see https://nix.dev/manual/nix/2.25/store/store-path
              basename=$(basename $src | sed -e "s/^[a-z0-9]*-//")
              cp $src $out/bin/$basename
              chmod 755 $out/bin/$basename
              ls -l $out/bin
              runHook postInstall
            '';
          } // attrs);

          run_kgd = wrap-script {
            name = "gbs_prism_kgd";
            src = ./src/run_kgd.R;
            buildInputs = [ flakePkgs.kgd-src ];

            postFixup = ''
              wrapProgram $out/bin/run_kgd.R --set KGD_SRC "${flakePkgs.kgd-src}"
            '';
          };

          R-with-GUSbase = pkgs.rWrapper.override {
            packages = [ flakePkgs.GUSbase ];
          };

          run_GUSbase = wrap-script {
            name = "gbs_prism_GUSbase";
            src = ./src/run_GUSbase.R;
            buildInputs = [ R-with-GUSbase ];
          };

          tag_count_plots = wrap-script {
            name = "gbs_prism_tag_count_plots ";
            src = ./src/tag_count_plots.R;
            buildInputs = [ pkgs.R ];
          };

          barcode_yield_plots = wrap-script {
            name = "gbs_prism_barcode_yield_plots";
            src = ./src/barcode_yields_plots.R;
            buildInputs = [ pkgs.R ];
          };

          redun-with-gbs-prism = inputs.redun.lib.${system}.default {
            propagatedBuildInputs = [ gbs-prism-api ];
          };

          python-with-gbs-prism = pkgs.python3.withPackages (ps: [ gbs-prism-api ]);

          gbs-prism-pipeline = pkgs.symlinkJoin
            {
              name = "gbs-prism-pipeline";
              # the main pipeline.py and all the context files
              paths = [
                (pkgs.writeTextDir "pipeline/pipeline.py" (builtins.readFile ./pipeline.py))
              ] ++ pkgs.lib.attrsets.mapAttrsToList
                (filename: filetype:
                  pkgs.writeTextDir "pipeline/${filename}" (builtins.readFile (./context + "/${filename}"))
                )
                (builtins.readDir ./context);
            };

          gbs-prism-dependencies = pkgs.symlinkJoin
            {
              name = "gbs-prism-dependencies";
              paths = [
                run_kgd
                run_GUSbase
                tag_count_plots
                barcode_yield_plots
              ] ++ (with flakePkgs; [
                bbmap
                bcl-convert
                cutadapt
                tassel3
              ]) ++ (with pkgs; [
                bwa
                samtools
                fastqc
                multiqc
                seqtk
                gzip
                poppler_utils
              ]);
            };

          gbs-prism = pkgs.symlinkJoin
            {
              name = "gbs-prism";
              paths = [
                redun-with-gbs-prism
                python-with-gbs-prism
                gbs-prism-pipeline
                gbs-prism-dependencies
              ];
            };

          eri-install = pkgs.writeShellScriptBin "eri-install.gbs_prism" (builtins.readFile ./eri/install);

        in
        with pkgs;
        {
          devShells = {
            default = mkShell {
              buildInputs =
                let
                  gbs-prism-scripts = pkgs.symlinkJoin
                    {
                      name = "gbs-prism-dependencies";
                      paths = [
                        (pkgs.writeScriptBin "kmer_prism"
                          (builtins.readFile ./src/agr/gbs_prism/kmer_prism.py))
                        (pkgs.writeScriptBin "get_reads_tags_per_sample"
                          (builtins.readFile ./src/agr/gbs_prism/get_reads_tags_per_sample.py))
                        (pkgs.writeScriptBin "summarise_read_and_tag_counts"
                          (builtins.readFile ./src/agr/gbs_prism/summarise_read_and_tag_counts.py))
                      ];
                    };
                in
                [
                  bashInteractive

                  uv
                  postgresql.pg_config # needed for uv to install gquery

                  gbs-prism-dependencies
                  gbs-prism-scripts
                  python3Packages.pytest
                  jsonnet
                  flakePkgs.seffs
                ];

              shellHook =
                let
                  gquery-env = env: pkgs.writeTextFile {
                    name = "gquery-${env}-env";
                    text = gquery-export-env env;
                  };
                in
                ''
                  export REDUN_CONFIG=$(pwd)/.redun
                  # enable use of gbs_prism from current directory during development
                  export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                  ${gquery-export-env "dev"}
                  export GQUERY_ROOT=$HOME/gquery-logs
                  export GENO_ROOT=$HOME/geno-logs
                  export GBS_PRISM_EXECUTOR_CONFIG=$(pwd)/config/eri-executor.jsonnet

                  # for switching GQuery environments
                  export GQUERY_DEV_ENV=${gquery-env "dev"}
                  export GQUERY_TEST_ENV=${gquery-env "test"}
                  export GQUERY_PROD_ENV=${gquery-env "prod"}

                  # use Python from Nix rather than uv
                  export UV_NO_MANAGED_PYTHON=1

                  # TODO grotty hack to get uv run gquery to find libodbc.so.2 and libstdc++.so.6
                  # should be using propagatedBuildInputs
                  # these are available to Python via uv, but we need their propagatedBuildInputs too
                  # gquery
                  # geno-import
                  # except that propagatedBuildInputs don't include the required packages
                  export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${with pkgs; with flakePkgs; lib.makeLibraryPath (
                    gquery.propagatedBuildInputs ++ geno-import.propagatedBuildInputs ++
                    [
                      # TODO: this shouldn't be necessary, as it's in the propagatedBuildInputs for gquery,
                      # but for some reason that comes in as the main gcc package not the -lib package.
                      gcc.cc
                    ])}
                '';
            };
          };

          packages = {
            default = gbs-prism;
          };

          apps = {
            eri-install = {
              type = "app";
              program = "${eri-install}/bin/eri-install.gbs_prism";
            };

            # used in eri/install for the module file
            lmod-setenv = gquery-lmod-setenv;

            # For now we can't clone gquery and geno_import repos in GitHub actions, as they're on Azure DevOps.
            # This may be enough to run useful tests though:
            tests = let test-environment = python3.withPackages (ps: [ ps.pytest ]); in {
              type = "app";
              program = "${writeShellScript "gbs_prism-tests" ''
                export PATH=${pkgs.lib.makeBinPath [test-environment]}
                export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                pytest src
              ''}";
            };
          };
        }
      );
}

