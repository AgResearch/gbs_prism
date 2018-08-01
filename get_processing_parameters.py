#!/usr/bin/env python

import os, re, argparse,string, csv, sys, types, subprocess

def get_parameter_dict(filename):
    filestream = file(filename,"r")
    text = filestream.read()
    parameter_dict = eval(text)
    filestream.close()
    return parameter_dict

def get_csv_dict(filename, key_column_name, value_column_name, min_field_count = 1):
    """
    this method picks out a key-value pair of columns from a CSV file, which may have a header section
    """
    with open(filename, 'r') as csvfile:
        csvreader = csv.reader(csvfile)

        # read records until we find a record containin the key - thats assumed to be the
        # section header we are interested in 
        headings = [item.upper() for item in csvreader.next()]

        while key_column_name.upper() not in headings:
            try:
                headings = [item.upper() for item in csvreader.next()]
            except StopIteration:
                raise Exception("get_csv_dict: could not find either %s or %s in %s"%(key_column_name, value_column_name , filename))
                        
        if value_column_name.upper() not in headings:
            raise Exception("error - %s not found in %s"%(value_column_name.upper() , filename))
        key_index = headings.index(key_column_name.upper())
        value_index = headings.index(value_column_name.upper())
        return dict([(record[key_index], record[value_index]) for record in csvreader if len(record) > min_field_count])

def get_value(options):
    all_dict = get_parameter_dict(options["parameter_file"])
    parameter_dict = all_dict[options["parameter_name"]]
    if options["sample"] is None:
        value = parameter_dict
    else:
        value = parameter_dict.get(options["sample"],None)
        # if not found try some other standard forms  
        if value is None:
            # the key supplied may be Sample_[sample_name]
            match = re.search("^Sample_(\S+)$",options["sample"],re.IGNORECASE)
            if match is not None:
                sample_name = match.groups()[0]
                value = parameter_dict.get(sample_name,"")
    if value is None:
        value = ""
    return value 


def get_cohort(library_name, run_name):
    """
    database queries are wrapped in scripting mainly for authentication reasons (credentials can be suppied in .pgpass) - 
    also makes the query accessible from shell scripts
    """
    #print "DEBUG run=%s lib=%s"%(run_name, library_name)
    flowcell=None
    cohort_query = [os.path.join(os.environ["GBS_PRISM_BIN"], "get_cohort_count_from_database.sh"), run_name, library_name]
    #print "DEBUG running %s"%str(cohort_query)
    proc = subprocess.Popen(cohort_query, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        raise Exception("Unable to get cohort count from %s - call returned an error"%str(cohort_query))    
    if stdout.strip() not in ["0","1"]:
        # try including flowcell in the query 
        run_tokens = re.split("_", run_name)
        if len(run_tokens) != 4:
            raise Exception("Unable to parse flowcell id from %s"%run_name)
        flowcell = run_tokens[3][1:]
        cohort_query = [os.path.join(os.environ["GBS_PRISM_BIN"], "get_cohort_count_from_database.sh"), run_name, library_name, flowcell]
        proc = subprocess.Popen(cohort_query, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = proc.communicate()
        if proc.returncode != 0:
            raise Exception("Unable to get cohort count from %s - call returned an error"%str(cohort_query))
        #if stdout.strip() not in ["0","1"]:
        #    #raise Exception("Error - found %s cohorts for library %s, run %s, flowcell %s - this is not going to work ! CHECK KEYFILE !!!!!"%(stdout.strip(), library_name, run_name, flowcell))
        #    raise Exception("Error - found %s cohorts for library %s, run %s, flowcell %s - this is not going to work ! CHECK KEYFILE !!!!!"%(stdout.strip(), library_name, run_name, flowcell))
    if stdout.strip() == "0":
        return "undefined"

    # got this far - so get the cohort
    if flowcell is None:
        cohort_query = [os.path.join(os.environ["GBS_PRISM_BIN"], "get_cohort_from_database.sh"), run_name, library_name]
    else:
        cohort_query = [os.path.join(os.environ["GBS_PRISM_BIN"], "get_cohort_from_database.sh"), run_name, library_name, flowcell]
        
    #print "DEBUG running %s"%str(cohort_query)
    proc = subprocess.Popen(cohort_query, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        raise Exception("Unable to get cohort from %s - called returned an error"%str(cohort_query))
    if len(stdout.strip()) <= 1:
        raise Exception("Unable to get a valid looking cohort from %s - called returned <%s>"%(str(cohort_query), stdout.strip()))
    #print "DEBUG - got %s"%stdout.strip()
 
    #return stdout.strip()
    return " ".join( [ item.strip() for item in re.split("\n",stdout.strip()) ] )



def get_bwa_alignment_references(options):
    """
    see e.g. /dataset/hiseq/active/141217_D00390_0214_BC4UEHACXX/SampleProcessing.json
    note that we get alignment references both by sampleid and also sample project - this handles
    both GBS and non GBS outputs. (GBS projects have some "fake" sample projects added by the
    downstream)
    """
    species_references_dict = get_csv_dict(options["species_references_file"],"species","reference genome")
    try:
        sample_sheet_dict = get_csv_dict(options["parameter_file"],"SampleID","Description", 5)
    except:
        sample_sheet_dict = get_csv_dict(options["parameter_file"],"Sample_ID","Description", 5)
        
    try:
        sample_sheet_dict1 = get_csv_dict(options["parameter_file"],"SampleProject","Description", 5)
    except:
        sample_sheet_dict1 = get_csv_dict(options["parameter_file"],"Sample_Project","Description", 5)

    #print "DEBUG1"
    #print sample_sheet_dict
    #print sample_sheet_dict1

    sample_sheet_dict.update(sample_sheet_dict1)
    #print "DEBUG2"    
    #print sample_sheet_dict
        
        

    #print "DEBUG"
    #print sample_sheet_dict

    # parse the run name from the parameter file - e.g. 
    # from /dataset/hiseq/active/150506_D00390_0225_BC6K2RANXX/SampleSheet.csv, get 150506_D00390_0225_BC6K2RANXX
    run_name = os.path.basename(os.path.dirname(options["parameter_file"]))


    # find the nearest match of each sample description  in sample_sheet_dict, in key of species_references_dict
    alignment_references = {}
    
    for sample in sample_sheet_dict:
        # begin long-winded code to do a fuzzymatch on species , between sample-sheet and species-ref-file
        best_reference = ''
        species_score_dict  = dict([(key,0) for key in species_references_dict.keys()])
        #print species_score_dict
        sample_keywords = [item for item in re.split("\s+", re.sub("GBS", " ", re.sub("_"," ", sample_sheet_dict[sample]))) if len(item) > 0]
        if len(sample_keywords) == 0:
            continue
        for species in species_references_dict:
            if len(species.strip()) == 0:
                continue
            #print "DEBUG testing %s, words %s"%(species, str( sample_keywords))
            species_score_dict[species] = [re.search(key_word, species, re.IGNORECASE) for key_word in sample_keywords]
            species_score_dict[species] = len([match for match in species_score_dict[species] if match is not None])
            #print "score: %d"%species_score_dict[species]
        #print species_score_dict
        sorted_species = species_score_dict.keys()
        sorted_species.sort(lambda x,y:cmp(species_score_dict[x], species_score_dict[y]))
        #print species_score_dict
        #print sorted_species 
        if species_score_dict[sorted_species[0]] < species_score_dict[sorted_species[-1]]:
            best_reference = species_references_dict[sorted_species[-1]]
   
        if len(sample.strip()) > 2:
            alignment_references[sample]  = best_reference


    # try looking up the other way for unmatched samples
    #print "DEBUG"
    #print species_references_dict
    for unmatched_sample in [ sample for sample in alignment_references if alignment_references[sample] == ''] :
        for species in species_references_dict:
            if len(species) > 1:
                #print "DEBUG"
                #print "matching " + species + " against " + sample_sheet_dict[unmatched_sample]
                if re.search(species, sample_sheet_dict[unmatched_sample], re.IGNORECASE) is not None:
                    alignment_references[unmatched_sample] = species_references_dict[species]
                    break


    # try looking up the other way for unmatched samples, with all spaces stripped out 
    #print "DEBUG"
    #print species_references_dict
    for unmatched_sample in [ sample for sample in alignment_references if alignment_references[sample] == ''] :
        for species in species_references_dict:
            if len(species) > 1:
                #print "DEBUG"
                #print "matching " + re.sub("\s","",species) + " against " + re.sub("\s","",sample_sheet_dict[unmatched_sample])
                if re.search(re.sub("\s","",species), re.sub("\s","",sample_sheet_dict[unmatched_sample]), re.IGNORECASE) is not None:
                    alignment_references[unmatched_sample] = species_references_dict[species]
                    break                
                

     
    return alignment_references

    
    

 
def get_json(options):
    """
    see e.g. /dataset/hiseq/active/141217_D00390_0214_BC4UEHACXX/SampleProcessing.json
    """
    species_references_dict = get_csv_dict(options["species_references_file"],"species","reference genome")
    try:
        sample_sheet_dict = get_csv_dict(options["parameter_file"],"SampleID","Description", 5)
    except:
        sample_sheet_dict = get_csv_dict(options["parameter_file"],"Sample_ID","Description", 5)
        

    #print "DEBUG"
    #print sample_sheet_dict

    # parse the run name from the parameter file - e.g. 
    # from /dataset/hiseq/active/150506_D00390_0225_BC6K2RANXX/SampleSheet.csv, get 150506_D00390_0225_BC6K2RANXX
    run_name = os.path.basename(os.path.dirname(options["parameter_file"]))


    # find the nearest match of each sample description  in sample_sheet_dict, in key of species_references_dict
    alignment_references = get_bwa_alignment_references(options)
    
    cohorts = {}
    descriptions = open(options["parameter_file"],"r").read()
    try:
        downstream_processing = get_csv_dict( options["parameter_file"],"SampleID","downstream_processing" )
    except:
        downstream_processing = get_csv_dict( options["parameter_file"],"Sample_ID","downstream_processing" )
     
    for sample in sample_sheet_dict:
        if len(sample.strip()) > 2:
            cohorts[sample] = get_cohort(sample, run_name)

    json_dict = {
         "bwa_alignment_reference" : alignment_references,
         "cohorts" : cohorts,
         "descriptions" : descriptions,
         "downstream_processing" : downstream_processing,
         #"blast_database" : "/bifo/active/blastdata/mirror/refseq_genomic",
         #"blast_alignment_parameters" : "-evalue 1.0e-10 -penalty -3 -reward 2 -gapopen 5 -gapextend 2 -word_size 11 -template_type coding_and_optimal -template_length 21 -min_raw_gapped_score 56 -dust '20 64 1' -lcase_masking -soft_masking true",
         #"blast_task" : "dc-megablast",
         "blast_database" : "nt",
         "blast_alignment_parameters" : "-evalue 1.0e-10 -dust '20 64 1'",
         "blast_task" : "blastn",
         "bwa_alignment_parameters" : "-B 10" ,
         "adapter_to_cut" : "AGATCGGAAGAGCGGTTCAGCAGGAATGCCGAGACCGATCTCGTATGCCGTCTTCTGCTT"
    }
     
    return str(json_dict)

def get_options():
    description = """
    """
    long_description = """

example : ./get_processing_parameters.py --parameter_file /dataset/hiseq/active/141217_D00390_0214_BC4UEHACXX/SampleProcessing.json --parameter_name alignment_reference  --sample SQ0018
example : ./get_processing_parameters.py --json_out_file /dataset/hiseq/scratch/postprocessing/170519_D00390_0303_ACA95UANXX.SampleProcessing.json --parameter_file /dataset/hiseq/active/170519_D00390_0303_ACA95UANXX/SampleSheet.csv --species_references_file  /dataset/hiseq/active/sample-sheets/reference_genomes.csv  

"""

    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--parameter_file', dest='parameter_file', default=None, help="name of parameter file (sample sheet csv or sample processing json)", required=True)
    parser.add_argument('--parameter_name', dest='parameter_name', default=None, \
                   choices=["downstream_processing", "bwa_alignment_reference","blast_database","blast_alignment_parameters","blast_task","bwa_alignment_parameters","adapter_to_cut","cohorts"],help="name of parameter")
    parser.add_argument('--sample', dest='sample', default=None, help="sample name")
    parser.add_argument('--species_references_file', dest='species_references_file', default=None, help="a CSV file mapping species to indexed references")
    parser.add_argument('--json_out_file', dest='json_out_file', default=None, help="name of json output file")


    args = vars(parser.parse_args())
    return args

        
    
def main():
    options = get_options()
    if options['parameter_name'] is not None:
        print get_value(options)
    else:
        if options['json_out_file'] is None:
            print get_json(options)
        else:
            with open(options['json_out_file'],"w") as json_out:
                print >> json_out, get_json(options)
        
                                
if __name__ == "__main__":
    main()

    example={
   "alignment_reference": {
      "SQ0018" : "/dataset/mussel_assembly/archive/assemblies/GSM_transcriptome_scaffold.fasta",
      "SQ0028" : "/dataset/mussel_assembly/archive/assemblies/GSM_transcriptome_scaffold.fasta",
      "SQ0024" : "/dataset/AFC_dairy_cows/active/1000_bulls/umd_3_1_reference_1000_bull_genomes.fa",
      "SQ0023" : "/dataset/AFC_dairy_cows/active/1000_bulls/umd_3_1_reference_1000_bull_genomes.fa",
      "SQ0033" : "/dataset/mussel_assembly/archive/assemblies/GSM_transcriptome_scaffold.fasta",
      "SQ0048" : "/dataset/OARv3.0/active/current_version/sheep.v3.0.14th.final.fa",
      "SQ0032" : "",
      "SQ0031" : "/dataset/Salmo_salar_2014/active/ICSASG_v1/Ssa_ASM_3.6.fasta_bwa_0.7.9a"
   },
   "descriptions": """
FCID,Lane,SampleID,SampleRef,Index,Description,Control,Recipe,Operator,SampleProject
C4UEHACXX,1,SQ0018,SQ0018,,GBS_Mussel_ApeKI,N,,Tracey,C4UEHACXX
C4UEHACXX,2,SQ0028,SQ0028,,GBS_Mussel_PstI,N,,Tracey,C4UEHACXX
C4UEHACXX,3,SQ0024,SQ0024,,GBS_Lawson_Cattle62_PstI,N,,Tracey,C4UEHACXX
C4UEHACXX,4,SQ0023,SQ0023,,GBS_Lawson_Cattle63_PstI,N,,Tracey,C4UEHACXX
C4UEHACXX,5,SQ0033,SQ0033,,GBS_Mussel_Pippin_ApeKI,N,,Tracey,C4UEHACXX
C4UEHACXX,6,SQ0048,SQ0048,,GBS_IMF_2bp_Modification,N,,Tracey,C4UEHACXX
C4UEHACXX,7,SQ0032,SQ0032,,GBS_Ryegrass_Endophyte_ApeKI,N,,Tracey,C4UEHACXX
C4UEHACXX,8,SQ0031,SQ0031,,GBS_Salmon_HalfVol_ApeKI,N,,Tracey,C4UEHACXX
#_IEMVERSION_3_TruSeq LT,,,,,,,,,
   """
}

