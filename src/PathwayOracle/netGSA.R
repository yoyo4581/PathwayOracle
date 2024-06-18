
# List of packages
packages <- c("netgsa", "data.table", "rgl", "Matrix")
biocPackages <- c("graphite", "genefilter", "RCy3", "org.Hs.eg.db", "annotate")

# Function to install packages if they are not installed
install_packages <- function(packages) {
  for (package in packages) {
    if (!require(package, character.only = TRUE)) {
      install.packages(package)
    }
  }
}

install_BiocPackages <- function(packages) {
  if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
  
  for (package in packages) {
    if (!require(package, character.only = TRUE)) {
      BiocManager::install(package)
    }
  }
}

# Call the function with the list of packages
install_packages(packages)
install_BiocPackages(biocPackages)

library(netgsa)
library(graphite)
library(data.table)
library(genefilter)
library(RCy3)
library(rgl)
library(Matrix)

args<- commandArgs(trailingOnly=TRUE)

#Get the arguments
pathGene <- args[1]
pathGroup <- args[2]
dir_path <- args[3]


x <- read.table(file=pathGene, sep='\t', header=1)
x <- as.matrix(x)

group <- read.table(file=pathGroup, sep='\t', header=FALSE)
# Assuming 'table1D' is your 1D table
group <- as.numeric(unlist(group))

genes <- setNames(gsub(".*:(.*)", "\\1", rownames(x)), gsub("(.*):.*", "\\1", rownames(x)))

library(data.table)


# Construct the file path
file_path <- file.path(dir_path, "edge_list.txt")

# Read the file
edge_listRef <- read.table(file=file_path, sep='\t', header=1)


#create column names for the table
edge_listRef$database<-replicate(nrow(edge_listRef),'kegg')
#convert the base gene source and destination to string
edge_listRef$base_gene_src<-as.character(edge_listRef$base_gene_src)
edge_listRef$base_gene_dest<-as.character(edge_listRef$base_gene_dest)
#convert dataframe to data.table by reference
edge_listRef<-setDT(edge_listRef)

#subset by the genes that are actually in the expression dataset
edge_listSub<-edge_listRef[edge_listRef$base_gene_src%in%genes & edge_listRef$base_gene_dest%in%genes,] #subsetting edge so that it keeps only those in data
edge_listSub

#create list with object names
obEdgList<-list(edgelist=edge_listSub, genes_not_in_dbs=NULL)
class(obEdgList)<-"obtainedEdgeList"


#genes used as rows in the pathway matrix, first used in empty matrix
union_genes<-unique(rownames(x))
union_genes<-as.character(union_genes)
#pathways used as cols in the pathway matrix, first used in empty matrix
union_pathways<-unique(edge_listRef$pathway)

empty_matrix<-matrix(0, nrow=length(union_pathways),
                     ncol=length(union_genes),
                     dimnames = list(union_pathways,
                                     union_genes))


#pathway matrix has ENTREz in colnames and edge dataframe has gene names in ENTREZ.
#for every gene isolate ENTREZ code, look for that gene in the edgelist identify it.
#by row and then identify all pathways involved by using the edgelist.
#occupy the found pathways.
Gene_Path_membership<- function(path_mat, edge_df, unionGenes){
  
  for (idx in 1:length(unionGenes)){
    
    sub_gene<-as.character(substring(union_genes[idx],10,))
    
    rows_found<-which(edge_df$base_gene_src==sub_gene | edge_df$base_gene_dest==sub_gene)
    pathways<-edge_df[rows_found,]$pathway
    path_mat[pathways, union_genes[idx]]<-1
  }
  
  return(path_mat)
  
}


#passes an empty pathway matrix, an edgelist, and genes.
pathway_matFinal<-Gene_Path_membership(empty_matrix, edge_listRef, union_genes)

write.table(pathway_matFinal, "./pathways_mat.csv", append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)



#computes row sums, here we are looking for only genes that entries in the pathway matrix
index<-rowSums(pathway_matFinal)!=0
pathway_matFinal<-pathway_matFinal[index,]

#conduct netgsa obtainEdgeList
network_info <- netgsa::prepareAdjMat(x, group, databases=obEdgList, cluster = TRUE,
                                      file_e = NULL, file_ne = NULL)

        
pathway_tests_rehe <- netgsa::NetGSA(network_info$Adj, x, group, pathway_matFinal,
                                     lklMethod = "REHE", sampling = TRUE,
                                     sample_n = 0.25, sample_p = 0.25)


pathway_results<-pathway_tests_rehe$results[which(pathway_tests_rehe$results$pFdr <= 0.05),c('pathway','pSize','pFdr','teststat')]


gene_frame<-pathway_tests_rehe$graph$gene.tests[which(pathway_tests_rehe$graph$gene.tests$pFdr<=0.05),c('teststat','gene','pFdr')]


library(org.Hs.eg.db)
library(annotate)

gene_frame$gene<-substring(gene_frame$gene,10,)
gene_frame$gene<-getSYMBOL(gene_frame$gene, data='org.Hs.eg')


write.table(gene_frame, "./gene_results.csv", append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)

write.table(pathway_results, "./pathway_results.csv", append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)