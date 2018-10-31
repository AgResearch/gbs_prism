all: replace_hiseq_samplesheet 

replace_hiseq_samplesheet: replace_hiseq_samplesheet.c
	$(CC) $< $(CFLAGS) $(CPPFLAGS) $(LDFLAGS) $(LDLIBS) $(TARGET_ARCH) -o $@

clean:
		rm -f *.o replace_hiseq_samplesheet 
