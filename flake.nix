{
  description = "Flake for gbs_prism";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

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
      url = "github:AgResearch/KGD?ref=refs/tags/v1.3.0";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    GUSbase = {
      url = "github:tpbilton/GUSbase";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    gquery = {
      # TODO switch back to main when merged
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/get_genophyle_export";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    geno-import = {
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/geno_import?ref=refs/heads/main";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.gquery.follows = "gquery";
    };
    redun = {
      # TODO reinstate official release when this is fixed and released:
      # https://github.com/insitro/redun/issues/109
      url = "github:AgResearch/redun.nix/redun-console-log";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    seffs = {
      url = "github:AgResearch/seffs/main";
      # TODO revert this to main nixpkgs once we have something newer than 24.05.
      # We do this for now because the Elvish in 24.05 is too old.
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };
  };

  outputs = inputs:
    inputs.flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import inputs.nixpkgs {
            inherit system;
          };

          nixpkgs-unstable = import inputs.nixpkgs-unstable {
            inherit system;
          };

          flakePkgs = {
            bbmap = inputs.bbmap.packages.${system}.default;
            bcl-convert = inputs.bcl-convert.packages.${system}.default;
            cutadapt = inputs.cutadapt.packages.${system}.default;
            tassel3 = inputs.tassel3.packages.${system}.default;
            kgd-src = inputs.kgd.packages.${system}.src;
            GUSbase = inputs.GUSbase.packages.${system}.default;
            gquery-api = inputs.gquery.packages.${system}.api;
            gquery-cli = inputs.gquery.packages.${system}.cli;
            gquery-eri-cli = inputs.gquery.packages.${system}.eri-cli;
            geno-import = inputs.geno-import.packages.${system}.default;
            seffs = inputs.seffs.packages.${system}.default;
          };

          gquery-export-env = env: inputs.gquery.export-env.${system} env;

          gquery-lmod-setenv = inputs.gquery.apps.${system}.lmod-setenv;

          # when using NixOS 24.05 we need this:
          # https://github.com/NixOS/nixpkgs/issues/308121#issuecomment-2289017641
          hatch-fixed = (pkgs.hatch.overrideAttrs (prev: {
            disabledTests = prev.disabledTests ++ [
              "test_field_readme"
              "test_field_string"
              "test_field_complex"
              "test_new_selected_python"
              "test_plugin_dependencies_unmet"
            ];
          }));

          # Wrapped multiqc which ignores PYTHONPATH from the environment.
          # This is required because our Python package dependencies export PYTHONPATH for Python 3.11,
          # which breaks multiqc from nixpkgs-unstable, because that uses Python 3.12.
          # As soon as we switch to a later version of nixpkgs this won't be necessary.
          # Alternatively, and probably anyway, the redun packaging should be improved to not
          # pollute the PYTHONPATH.
          multiqc = pkgs.stdenv.mkDerivation {
            name = "multiqc";
            src = null;
            nativeBuildInputs = [ pkgs.makeWrapper ];
            dontUnpack = true;
            dontBuild = true;

            installPhase = ''
              mkdir -p $out/bin
            '';

            postFixup = ''
              makeWrapper "${nixpkgs-unstable.multiqc}/bin/multiqc" $out/bin/multiqc --unset PYTHONPATH
            '';
          };

          psij-python = with pkgs;
            python3Packages.buildPythonPackage {
              name = "psij";
              src = pkgs.fetchFromGitHub {
                owner = "ExaWorks";
                repo = "psij-python";
                rev = "0.9.9";
                hash = "sha256-eyrkj3hcQCDwtyfzkBfe0j+rHJY4K7QWNF8GRuPlAsM=";
              };

              format = "setuptools";

              # Tests seem to require a network-mounted home directory
              doCheck = false;

              nativeBuildInputs = with python3Packages;
                [
                  setuptools
                ];

              buildInputs = with python3Packages;
                [
                  packaging
                ];

              propagatedBuildInputs = with python3Packages;
                [
                  psutil
                  pystache
                  typeguard
                ];
            };

          pipeline-packages = with pkgs.python3Packages;
            [
              biopython
              jsonnet
              pdf2image
              pydantic
              flakePkgs.gquery-api
              flakePkgs.geno-import
              psij-python
            ];

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              name = "gbs-prism-api";
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch-fixed
                python3Packages.hatchling
              ];

              propagatedBuildInputs = pipeline-packages;
            };

          run_kgd = pkgs.stdenv.mkDerivation {
            name = "gbs_prism_kgd";

            src = ./src/run_kgd.R;

            buildInputs = [ flakePkgs.kgd-src ];
            nativeBuildInputs = [ pkgs.makeWrapper ];

            dontUnpack = true;
            dontBuild = true;

            installPhase = ''
              mkdir -p $out/bin
              runHook preInstall
              cp $src $out/bin/run_kgd.R
              chmod 755 $out/bin/run_kgd.R
              runHook postInstall
            '';

            postFixup = ''
              wrapProgram $out/bin/run_kgd.R --set KGD_SRC "${flakePkgs.kgd-src}"
            '';
          };

          R-with-GUSbase = pkgs.rWrapper.override {
            packages = [ flakePkgs.GUSbase ];
          };

          run_GUSbase =
            pkgs.stdenv.mkDerivation {
              name = "gbs_prism_GUSbase";

              src = ./src/run_GUSbase.R;

              buildInputs = [ R-with-GUSbase ];

              dontUnpack = true;
              dontBuild = true;

              installPhase = ''
                mkdir -p $out/bin
                runHook preInstall
                cp $src $out/bin/run_GUSbase.R
                chmod 755 $out/bin/run_GUSbase.R
                runHook postInstall
              '';
            };

          redun-with-gbs-prism = inputs.redun.lib.${system}.default {
            propagatedBuildInputs = [ gbs-prism-api ];
          };

          python-with-gbs-prism = pkgs.python3.withPackages (ps: [ gbs-prism-api ]);

          # for development, we use a redun with only gquery, and pick up the gbs-prism locally
          redun-with-gquery = inputs.redun.lib.${system}.default {
            propagatedBuildInputs = pipeline-packages;
          };

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
                multiqc
              ] ++ (with flakePkgs; [
                bbmap
                bcl-convert
                cutadapt
                tassel3
              ]) ++ (with pkgs; [
                bwa
                samtools
                fastqc
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
                flakePkgs.gquery-cli
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
                        (pkgs.writeScriptBin "make_cohort_pages"
                          (builtins.readFile ./src/agr/gbs_prism/make_cohort_pages.py))
                      ];
                    };
                in
                [
                  bashInteractive
                  redun-with-gquery
                  gbs-prism-dependencies
                  gbs-prism-scripts
                  python3Packages.pytest
                  jsonnet
                  flakePkgs.seffs
                ];

              shellHook = ''
                export REDUN_CONFIG=$(pwd)/.redun
                # enable use of gbs_prism from current directory during development
                export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                ${gquery-export-env "dev"}
                export GQUERY_ROOT=$HOME/gquery-logs
                export GENO_ROOT=$HOME/geno-logs
                export GBS_PRISM_EXECUTOR_CONFIG=$(pwd)/config/eri-executor.jsonnet
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
          };
        }
      );
}
