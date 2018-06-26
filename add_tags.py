#!/bin/env python


import sys,re,itertools, argparse

def combined_iter(a, b):
    """ this is a generator. Both tag stream are assumed sorted , and we
    just ratchet down then both to yield an added single stream of tags """
    with open(a,"r") as a_stream:
        with open(b,"r") as b_stream:
            streams=[]
            for stream in (a_stream, b_stream):
                a_iter=(record for record in stream)
                a_iter=(re.split("\s+",record.strip().upper()) for record in a_iter)    # parse the 3 elements 
                a_iter=((my_tuple[0], my_tuple[1], my_tuple[2])  for my_tuple in a_iter if len(my_tuple) == 3)  # skip the header and make ints
                streams.append(a_iter)

            (a,b)=streams
            a_rec=a.next()
            b_rec=b.next()
            while True:
                if a is not None and b is not None:
                    if a_rec[0] < b_rec[0]:
                        yield a_rec
                        try: 
                            a_rec=a.next()
                        except StopIteration:
                            a=None
                            
                    elif a_rec[0] == b_rec[0]:
                        yield (a_rec[0], a_rec[1], str(int(a_rec[2]) + int(b_rec[2])))
                        try:
                            a_rec = a.next()
                        except StopIteration:
                            a=None 
                        try:
                            b_rec = b.next()
                        except StopIteration:
                            b=None
                    elif a_rec[0] > b_rec[0]:
                        yield b_rec
                        try: 
                            b_rec = b.next()
                        except StopIteration:
                            b=None

                elif a is not None:
                    yield a_rec
                    a_rec=a.next()
                elif b is not None:
                    yield b_rec
                    b_rec=b.next()
                else:
                    raise StopIteration
                    
                
def get_options():
    description = """
    This takes two tag dump files and combines to make a single tag dump file
    """
    
    long_description = """
add_tags.py /dataset/hiseq/scratch/postprocessing/180611_D00390_0369_ACCJKKANXX.gbs/SQ2708.processed_sample/uneak/annotation/a.tags
/dataset/hiseq/scratch/postprocessing/180611_D00390_0369_ACCJKKANXX.gbs/SQ2708.processed_sample/uneak/annotation/b.tags
    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file_names', type=str, nargs=2, help='list of files to combine')    

    args = vars(parser.parse_args())

    return args


def main():
    args=get_options()

    for record in combined_iter(args['file_names'][0], args['file_names'][1]):
        print "\t".join(record)

    
if __name__ == "__main__":
   main()
        

