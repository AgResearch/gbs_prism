
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>


/*
* This program simply replaces a hiseq sample sheet via a copy - the only reason for
* this is that the binary has setuid set, so that a standard user can do the replace
*/



typedef struct program_opts {
	char* input_filename;	
	char* output_filename;
} t_program_opts;


int get_program_opts(int argc, char **argv, t_program_opts *program_opts)
{
	char* usage="Usage: %s -i from_file_path -o to_file_path \n";
	int c;

	program_opts->input_filename = "";
	program_opts->output_filename = "";


	opterr = 0;

	while ((c = getopt (argc, argv, "hi:o:")) != -1) {
		switch (c) {
			case 'h':
				fprintf(stderr, usage, argv[0]);
				return 2;
			case 'i':
				program_opts->input_filename = optarg;
				break;
			case 'o':
				program_opts->output_filename = optarg;
				break;
			case '?':
				if (optopt == 's')
					fprintf (stderr, "Option -%c requires an argument.\n", optopt);
				else if (optopt == 'f')
					fprintf (stderr, "Option -%c requires an argument.\n", optopt);
				else if (isprint (optopt))
					fprintf (stderr, "Unknown option `-%c'.\n", optopt);
				else
					fprintf (stderr,"Unknown option character `\\x%x'.\n",optopt);
					return 1;
			default:
				abort ();
		} // switch
   	} // getopt loop


	// do some checks 
	if ( strstr(program_opts->output_filename, "SampleSheet") == NULL ) {
		fprintf(stderr, "sorry - output filename does not look a sample sheet, will not replace\n");
		return 1;		
	}
	if( access( program_opts->input_filename, F_OK ) == -1 ) {
		fprintf(stderr, "input file not found\n");
		return 1;		
	}

  	return 0;
}


int main(int argc, char *argv[])
{
	
	FILE *finput, *foutput;
        int program_opts_result = 0;
        char ch;

	t_program_opts program_opts;
        program_opts_result = get_program_opts(argc, argv, &program_opts);
 	if ( program_opts_result != 0 ){
		// usage message on help is not an error
		return program_opts_result == 2 ? 0 : program_opts_result;
 	} 

        finput=fopen(program_opts.input_filename, "r");
        foutput=fopen(program_opts.output_filename, "w");
        
      
        while ((ch = fgetc(finput)) != EOF) {
        	fputc(ch, foutput);
	}

 
	// clean up and return
	fclose(finput);
        fclose(foutput);

	return 0;
}
