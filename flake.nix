{
  description = "Flake for gbs_prism";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
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
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    redun = {
      url = "github:AgResearch/redun.nix/nixos-24.05";
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
            gquery-api = inputs.gquery.packages.${system}.api;
            gquery-cli = inputs.gquery.packages.${system}.cli;
            gquery-eri-cli = inputs.gquery.packages.${system}.eri-cli;
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

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              name = "gbs-prism-api";
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch-fixed
                python3Packages.hatchling
              ];

              propagatedBuildInputs = with python3Packages;
                [
                  biopython
                  pdf2image
                  pydantic
                  flakePkgs.gquery-api
                ];
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
            propagatedBuildInputs = with pkgs.python3Packages; [
              biopython
              pdf2image
              pydantic
              flakePkgs.gquery-api
            ];
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
                ];

              shellHook = ''
                # enable use of gbs_prism from current directory during development
                export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                gquery-${gquery-export-env "dev"}
                export GQUERY_ROOT=$HOME/gquery-logs
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
