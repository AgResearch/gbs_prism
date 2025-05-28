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
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    geno-import = {
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/geno_import?ref=refs/heads/main";
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
            redun = inputs.redun.packages.${system}.default;
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

          python-dependencies = with pkgs.python3Packages;
            [
              biopython
              jinja2
              jsonnet
              pdf2image
              pydantic
              flakePkgs.gquery
              flakePkgs.geno-import
              flakePkgs.redun
              psij-python
              wand
            ];

          other-dependencies = (with flakePkgs; [
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

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              name = "gbs-prism-api";
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch
                python3Packages.hatchling
              ];

              propagatedBuildInputs = python-dependencies;
            };

          gbs-prism-R-scripts =
            let
              R-with-packages = pkgs.rWrapper.override {
                packages = [ flakePkgs.GUSbase ];
              };
            in
            pkgs.stdenv.mkDerivation {
              name = "gbs_prism-R-scripts";
              src = ./R-scripts;

              nativeBuildInputs = [ pkgs.makeWrapper ];
              buildInputs = [ R-with-packages flakePkgs.kgd-src ];

              dontUnpack = true;
              dontBuild = true;

              installPhase = ''
                runHook preInstall

                mkdir -p $out/bin
                ls -l $src
                cp $src/* $out/bin
                chmod 755 $out/bin/*
                ls -l $out/bin

                runHook postInstall
              '';

              postFixup = ''
                wrapProgram $out/bin/run_kgd.R --set KGD_SRC "${flakePkgs.kgd-src}"
              '';
            };

          # for running locally in development we need the gbs_prism depencencies but not gbs-prism-api itself, since we'll pick that up from the working directory using PYTHONPATH
          python-with-dependencies-only = pkgs.python3.withPackages (ps: python-dependencies);
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

          gbs-prism = pkgs.symlinkJoin
            {
              name = "gbs-prism";
              paths = [
                python-with-gbs-prism
                gbs-prism-pipeline
                gbs-prism-R-scripts
              ] ++ other-dependencies;
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
                      name = "gbs-prism-scripts";
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
                  python-with-dependencies-only
                  gbs-prism-R-scripts
                  gbs-prism-scripts
                  python3Packages.pytest
                  jsonnet
                  flakePkgs.seffs
                ] ++ other-dependencies;

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

                  # for postgres database backend, will use the default config in .redun
                  # unless this is defined:
                  # export REDUN_CONFIG="$(pwd)/config/redun.dev"
                  export REDUN_DB_USERNAME="gbs_prism_redun"
                  export REDUN_DB_PASSWORD="unused because Kerberos"
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

