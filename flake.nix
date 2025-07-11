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
          };

          gquery-export-env = env: inputs.gquery.export-env.${system} env;

          gquery-lmod-setenv = inputs.gquery.apps.${system}.lmod-setenv.program;

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

          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              pname = "gbs-prism-api";
              version = pyproject.project.version;
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

          gbs-prism-python = pkgs.python3.withPackages (ps: [ gbs-prism-api ]);

          # create a minimal derivation with only redun on the path,
          # the main pipeline.py and all the config and context files,
          # with all dependencies picked up via the path set in the redun wrapper
          gbs-prism = pkgs.stdenv.mkDerivation rec {
            pname = "gbs_prism";
            version = pyproject.project.version;
            src = ./.;

            nativeBuildInputs = [ pkgs.makeWrapper ];
            buildInputs = [
              gbs-prism-python
              gbs-prism-R-scripts
            ] ++ other-dependencies;

            dontUnpack = true;
            dontBuild = true;

            installPhase = ''
              runHook preInstall

              mkdir $out
              cp $src/pipeline.py $out
              cp -a $src/context $out/context

              mkdir $out/config
              cp $src/config/eri-executor.jsonnet $out/config

              # append the context_file in each config so we don't need to pass it on the command line
              for env in dev test prod; do
                mkdir $out/config/redun.$env
                echo -e "\n[scheduler]\ncontext_file = $out/context/eri-$env.json" | cat $src/config/redun.$env/redun.ini - >$out/config/redun.$env/redun.ini
              done

              # Install just the executables we want to be on the end-user's path.
              mkdir $out/bin
              for prog in gquery gupdate; do
                ln -s ${gbs-prism-python}/bin/$prog $out/bin/$prog
              done
              # Need to wrap redun so it can find its non-Python dependencies, and also
              # so it won't break if someone plays games with PYTHONPATH and LD_LIBRARY_PATH.
              # Note that we need the original $PATH as a suffix, to find e.g. sbatch.
              makeWrapper ${gbs-prism-python}/bin/redun $out/bin/redun --prefix PATH : "${pkgs.lib.makeBinPath buildInputs}" --unset PYTHONPATH --unset LD_LIBRARY_PATH

              runHook postInstall
            '';
          };

          lmod-setenv-script = pkgs.writeShellScriptBin "gbs_prism-lmod-setenv" ''
            env="$1"

            case "$env" in
              dev)
                ${gquery-lmod-setenv} dev
                ;;
              test)
                ${gquery-lmod-setenv} test
                ;;
              prod)
                ${gquery-lmod-setenv} prod
                ;;
              *)
                echo >&2 "usage: gquery-lmod-setenv dev|test|prod"
                exit 1
            esac

            cat <<EOF
              setenv("GBS_PRISM", "${gbs-prism}")
              setenv("GBS_PRISM_EXECUTOR_CONFIG ", "${gbs-prism}/config/eri-executor.jsonnet")
              setenv("REDUN_CONFIG ", "${gbs-prism}/config/redun.$env")
              setenv("REDUN_DB_USERNAME", "gbs_prism_redun")
              setenv("REDUN_DB_PASSWORD", "unused because Kerberos")

              setenv("GQUERY_ROOT", pathJoin(os.getenv("HOME"), "gquery-logs"))
              setenv("GENO_ROOT", pathJoin(os.getenv("HOME"), "geno-logs"))

              execute { cmd="{ test -d \$GQUERY_ROOT || mkdir -p \$GQUERY_ROOT ; } ; { test -d \$GENO_ROOT || mkdir -p \$GENO_ROOT ; }", modeA={"load"} }
            EOF
          '';

          eri-install = pkgs.writeShellScriptBin "eri-install.gbs_prism" (builtins.readFile ./eri/install);

        in
        with pkgs;
        {
          devShells = {
            default = mkShell {
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
                  python-with-dependencies
                  gbs-prism-R-scripts
                  gbs-prism-python-scripts
                  python3Packages.pytest
                  jsonnet
                ] ++ other-dependencies;

              shellHook =
                let
                  gbs-prism-env = env: pkgs.writeTextFile {
                    name = "gbs-prism-${env}-env";
                    text = (if env == "prod" then ''
                      export REDUN_CONFIG="$(pwd)/config/redun.${env}"
                    ''
                    else ''
                      unset REDUN_CONFIG
                    '')
                    + gquery-export-env env;
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

                  # for switching GQuery and gbs_prism environments
                  export GBS_PRISM_DEV_ENV=${gbs-prism-env "dev"}
                  export GBS_PRISM_TEST_ENV=${gbs-prism-env "test"}
                  export GBS_PRISM_PROD_ENV=${gbs-prism-env "prod"}

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
            lmod-setenv = {
              type = "app";
              program = "${lmod-setenv-script}/bin/gbs_prism-lmod-setenv";
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
        }
      );
}
