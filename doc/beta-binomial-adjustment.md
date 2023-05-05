#Beta-binomial adjustment with Novaseq data

##Introduction
The Novaseq 6000 platform uses patterned flowcells. Some of the reads represent amplified sequences from nearby nanowells that have escaped their original nanowell and deposited in an empty nanowell. This is known as ExAmp (exclusion amplification) duplicaton. There is some discussion [here]( http://core-genomics.blogspot.com/2016/05/increased-read-duplication-on-patterned.html ). This results in non-binomial sampling of a sample’s two alleles (for diploids).

There are two complementary ways of adjusting for this effect:

1. Deduplicate reads from a sequencing lane. This process ensures that only one identical read is retained within a given distance. Currently deduplication is applied with a distance parameter of 2000 (?check).
2. Apply a statistical model that allows greater variance (but same mean) as the binomial model. One such model is the beta-binomial (BB) model with parameters α and β=α (to ensure the probability of sampling a particular allele is 0.5).

##QC pipeline
The QC pipeline is run for each flowcell × species combination. Within the GBS QC pipeline there is a step investigating potential BB adjustments. This is based on there being two lanes of data for each sample, which are assumed independent (in particular, no ExAmp duplicates across the lanes). The results from these analyses are reported in InbCompare.png.

This plot contains inbreeding estimates calculated four different ways:
|Label|Description|
|-----|-----------|
|Combined|Combine SampleID results across lanes & then calculate Inbreeding (binomial model)|
|Combined alpha|Combine SampleID results across lanes & then calculate Inbreeding with a beta-binomial model with the estimated value of α |
|Sampled|Use a single read from each lane (for each SampleID and SNP) and calculate the inbreeding with the binomial model. Any issues about duplication within lane are avoided.|
|Between Lane|Use the relatedness estimate (which does not depend on depth, and therefore on the allele sampling model) for the pair of SampleID results in lanes 1 and 2 to estimate inbreeding (relatedness – 1).|

##Estimating alpha
The α parameter is estimated by comparing the Sampled results with Combined alpha results by finding the value of α that minimizes the sum of squared differences between these estimates. These are the differences from the y=x line in row 3, column 2 of the InbCompare plot. Only samples with specified combined lanes minimum depth (0.1) are used for estimating α.

An alternative would be to use the between lane relatedness instead of the sampled lanes estimates. 

##GBS data analysis workflows
The analysis workflows operate by adjusting result depths to an equivalent depth, i.e. the depth that gives the same P(AA|AB) under the binomial model. Then, for example, depths can be combined across any repeated genotyping of the same individual. The equivalent depths are used in downstream analyses with the binomial model.

`Equivalent depth = -log2 (depth2Kbb(depth, α ))`
(depth2Kbb is a KGD function)

Applying the adjustment for all results from a flowcell is much more efficient (in R) than applying it to each genotype result.

###Pre-calculated α
α values are obtained from a key files. These are combined lanes αs (currently).

1. Combine separate lane data if present in the data.
2. Ascertain the flowcells used and obtain their α.
3. For each flowcell, calculate the equivalent depth for the data from that flowcell. Then use equivalent depths in place of the actual depths for the remainder of the analysis.

###Calculate α within workflow
Assume that we wish to calculate α on a separate lanes basis.
1. Calculate inbreeding using a sampled allele from each lane (for each sample × Flowcell × SNP)
2. For each Novaseq flowcell estimate α by comparing the inbreeding for each sample × lane to the inbreeding for that sample from the previous step (minimize the sums of squared differences)
3. For each flowcell, calculate the equivalent depth for the data from that flowcell. Then use equivalent depths in place of the actual depths for the remainder of the analysis (including combining data from the different lanes of a flowcell).
