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
      url = "github:AgResearch/KGD?ref=refs/tags/v1.4.0";
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
      url = "github:AgResearch/redun.nix?ref=refs/tags/0.32.0-1";
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
            kgd-rPackages = inputs.kgd.packages.${system}.rPackages;
            GUSbase = inputs.GUSbase.packages.${system}.default;
            gquery = inputs.gquery.packages.${system}.default;
            geno-import = inputs.geno-import.packages.${system}.default;
          };

          gquery-env = inputs.gquery.env.${system};

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

          gbs-prism-R-scripts =
            let
              R-with-packages = pkgs.rWrapper.override {
                packages = [ flakePkgs.GUSbase ] ++ flakePkgs.kgd-rPackages;
              };
            in
            pkgs.stdenv.mkDerivation {
              pname = "gbs_prism-R-scripts";
              version = pyproject.project.version;
              src = ./R-scripts;

              nativeBuildInputs = [ pkgs.makeWrapper ];
              buildInputs = [ R-with-packages flakePkgs.kgd-src ];

              dontUnpack = true;
              dontBuild = true;

              installPhase = ''
                runHook preInstall

                mkdir -p $out/bin
                cp $src/* $out/bin
                chmod 755 $out/bin/*

                runHook postInstall
              '';

              postFixup = ''
                wrapProgram $out/bin/run_kgd.R --set KGD_SRC "${flakePkgs.kgd-src}"
              '';
            };

          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);

          gbs-prism = with pkgs;
            python3Packages.buildPythonPackage {
              pname = "gbs-prism";
              version = pyproject.project.version;
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch
                python3Packages.hatchling
              ];

              propagatedBuildInputs = python-dependencies ++ other-dependencies ++ [ gbs-prism-R-scripts ];

              postInstall = ''
                # install config alongside Python package
                mkdir $out/config
                cp config/cluster-executor.{jsonnet,libsonnet} $out/config
              '';
            };

          # The bundle is a minimal derivation with only redun on the path,
          # the main pipeline.py and all the config and context files,
          # with all dependencies picked up via the path set in the redun wrapper.
          gbs-prism-bundle =
            let
              python-with-gbs-prism = pkgs.python3.withPackages (ps: [ gbs-prism ]);
              path-for-gbs-prism = pkgs.lib.makeBinPath ([ python-with-gbs-prism ] ++ gbs-prism.propagatedBuildInputs);
            in
            pkgs.stdenv.mkDerivation {
              pname = "gbs-prism-bundle";
              version = pyproject.project.version;
              src = ./.;

              nativeBuildInputs = [ pkgs.makeWrapper ];

              dontUnpack = true;
              dontBuild = true;

              installPhase = ''
                runHook preInstall

                mkdir $out
                cp $src/pipeline.py $out
                cp -a $src/context $out/context

                # append the context_file in each config so we don't need to pass it on the command line
                for env in dev test prod; do
                  mkdir -p $out/config/redun.$env
                  echo -e "\n[scheduler]\ncontext_file = $out/context/eri-$env.json" | cat $src/config/redun.$env/redun.ini - >$out/config/redun.$env/redun.ini
                done

                # Install just the executables we want to be on the end-user's path.
                mkdir $out/bin
                for prog in gquery gupdate; do
                  ln -s ${python-with-gbs-prism}/bin/$prog $out/bin/$prog
                done
                # Need to wrap redun so it can find its non-Python dependencies, and also
                # so it won't break if someone plays games with PYTHONPATH and LD_LIBRARY_PATH.
                # Note that we need the original $PATH as a suffix, to find e.g. sbatch.
                makeWrapper ${python-with-gbs-prism}/bin/redun $out/bin/redun --prefix PATH : "${path-for-gbs-prism}" --unset PYTHONPATH --unset LD_LIBRARY_PATH

                runHook postInstall
              '';
            };

          # a function from environment name to an attrset containing
          # the environment variables required to run gquery in the given eRI environment
          gbs-prism-env-attrs = env: (gquery-env.attrs env) // {
            CLUSTER_EXECUTOR_CONFIG_PATH = "${gbs-prism}/config";
            GQUERY_ROOT = "\${HOME}/gquery-logs";
            GENO_ROOT = "\${HOME}/geno-logs";
          };

          gbs-prism-bundle-env-attrs = env: (gbs-prism-env-attrs env) // {
            GBS_PRISM = "${gbs-prism-bundle}";
            REDUN_CONFIG = "${gbs-prism-bundle}/config/redun.${env}";
            REDUN_DB_USERNAME = "gbs_prism_redun";
            REDUN_DB_PASSWORD = "unused because Kerberos";
          };

          print-lmod-commands = pkgs.writeShellScriptBin "gbs_prism-print-lmod-commands" ''
            env="$1"
            set -e
            
            ${gquery-env.print-lmod-commands "gbs_prism" gbs-prism-bundle-env-attrs}/bin/gbs_prism-print-lmod-commands "$env"

            cat <<EOF

              execute { cmd="{ test -d \$GQUERY_ROOT || mkdir -p \$GQUERY_ROOT ; } ; { test -d \$GENO_ROOT || mkdir -p \$GENO_ROOT ; }", modeA={"load"} }
            EOF
          '';

          eri-install = pkgs.writeShellScriptBin "eri-install.gbs_prism" (builtins.readFile ./eri/install);

        in
        with pkgs;
        {
          devShells = {
            default = mkShell
              {
                buildInputs =
                  let
                    # for running locally in development we need the gbs_prism depencencies but not gbs-prism-api itself, since we'll pick that up from the working directory using PYTHONPATH
                    python-with-dependencies = (pkgs.python3.withPackages (ps: python-dependencies));

                    # only for development, as in production the scripts are available via the gbs-prism-api package
                    gbs-prism-python-scripts = pkgs.stdenv.mkDerivation {
                      pname = "gbs_prism-python-scripts";
                      version = pyproject.project.version;
                      src = ./src/agr/gbs_prism;

                      nativeBuildInputs = [ pkgs.makeWrapper ];
                      buildInputs = [ python-with-dependencies ];

                      dontUnpack = true;
                      dontBuild = true;

                      installPhase = ''
                        runHook preInstall

                        mkdir -p $out/bin
                        for script in kmer_prism get_reads_tags_per_sample summarise_read_and_tag_counts; do
                          cp $src/$script.py $out/bin/$script
                          chmod 755 $out/bin/$script
                        done

                        runHook postInstall
                      '';
                    };

                  in
                  [
                    bashInteractive
                    hatch
                    python-with-dependencies
                    gbs-prism-R-scripts
                    gbs-prism-python-scripts
                    python3Packages.pytest
                    jsonnet
                  ] ++ other-dependencies;

                shellHook =
                  let
                    gbs-prism-env = env: (gbs-prism-bundle-env-attrs env) //
                      {
                        CLUSTER_EXECUTOR_CONFIG_PATH = "$PWD/config";
                        REDUN_CONFIG = if env == "prod" then "$PWD/config/redun.${env}" else null;
                      };

                    bash-export-env = gquery-env.bash-export-env-attrs "gbs_prism" gbs-prism-env;
                  in
                  ''
                    # for switching GQuery and gbs_prism environments
                    export GBS_PRISM_DEV_ENV=${bash-export-env "dev"}
                    export GBS_PRISM_TEST_ENV=${bash-export-env "test"}
                    export GBS_PRISM_PROD_ENV=${bash-export-env "prod"}

                    # default to dev
                    source $GBS_PRISM_DEV_ENV

                    # enable use of gbs_prism from current directory during development
                    export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                  '';
              };
          };

          packages = {
            # The default package is the unbundled Python package for use in other flakes.
            default = gbs-prism;

            # The package gbs-prism-bundle is referenced by name in the eri/install script, so
            # if you change it here, ensure to change it there too.
            inherit
              gbs-prism
              gbs-prism-bundle;
          };

          apps = {
            eri-install = {
              type = "app";
              program = "${eri-install}/bin/eri-install.gbs_prism";
            };

            # used in eri/install for the module file
            print-lmod-commands = {
              type = "app";
              program = "${print-lmod-commands}/bin/gbs_prism-print-lmod-commands";
            };

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

          # for other flakes to consume the gquery environment
          env = gquery-env // {
            attrs = gbs-prism-env-attrs;
          };
        }
      );
}
