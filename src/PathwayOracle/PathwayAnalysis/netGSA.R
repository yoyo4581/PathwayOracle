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
fileDir <- args[3]
writeDir <- args[4]


x <- read.table(file=pathGene, sep='\t', header=1)
x <- as.matrix(x)
print(paste(dim(x), "Gene Expression Data Matrix dimensions"))

group <- read.table(file=pathGroup, sep='\t', header=TRUE)
# Assuming 'table1D' is your 1D table
group <- as.numeric(unlist(group))
print(paste(length(group), "Number of samples"))

genes <- setNames(gsub(".*:(.*)", "\\1", rownames(x)), gsub("(.*):.*", "\\1", rownames(x)))

library(data.table)

# Construct the file path
file_path <- file.path(fileDir, "edge_list.txt")

# Read the file
edge_listRef <- read.table(file=file_path, sep='\t', header=1)
head(edge_listRef)


#create column names for the table
edge_listRef$database<-replicate(nrow(edge_listRef),'kegg')
#convert the base gene source and destination to string
edge_listRef$base_gene_src<-as.character(edge_listRef$base_gene_src)
edge_listRef$base_gene_dest<-as.character(edge_listRef$base_gene_dest)
#convert dataframe to data.table by reference
edge_listRef<-setDT(edge_listRef)

#subset by the genes that are actually in the expression dataset
edge_listSub<-edge_listRef[edge_listRef$base_gene_src%in%genes & 
                             edge_listRef$base_gene_dest%in%genes,] #subsetting edge so that it keeps only those in data

print(paste("Subset by genes in Expression dataset",dim(edge_listSub)))
print(paste("All edges",dim(edge_listRef)))

#create list with object names
obEdgList<-list(edgelist=edge_listSub, genes_not_in_dbs=NULL)
class(obEdgList)<-"obtainedEdgeList"

obEdgList

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
dim(pathway_matFinal)

#computes row sums, here we are looking for only pathways that have genes in them
index<-rowSums(pathway_matFinal)!=0
pathway_matFinal<-pathway_matFinal[index,]
dim(pathway_matFinal)

#removes genes that are not involved in a pathway from the pathway matrix.
index_genes<-colSums(pathway_matFinal)!=0
pathway_matFinal<-pathway_matFinal[,index_genes]
print(paste("Processed pathway matrix: ",dim(pathway_matFinal)))

genes_inpathways<-colnames(pathway_matFinal)

#------------------- Cleaned gene expression data matrix-----------------
x<-x[rownames(x)%in%genes_inpathways,]



#conduct netgsa obtainEdgeList
network_info <- netgsa::prepareAdjMat(x, group, databases=obEdgList, cluster=TRUE,
                                      file_e = NULL, file_ne = NULL)



pathway_tests_rehe <- netgsa::NetGSA(network_info$Adj, x, group, pathway_matFinal,
                                     lklMethod = "REHE", sampling = TRUE,
                                     sample_n = 0.25, sample_p = 0.25)

pathway_results<-pathway_tests_rehe$results[which(pathway_tests_rehe$results$pFdr <= 0.05),c('pathway','pSize','pFdr','teststat')]
pathway_results_unref <- pathway_tests_rehe$results[, c('pathway', 'pSize', 'pFdr', 'teststat')]


print(paste("Processed Results: ",dim(pathway_tests_rehe$results)))

gene_frame<-pathway_tests_rehe$graph$gene.tests[ ,c('teststat','gene','pFdr')]

library(org.Hs.eg.db)
library(annotate)

gene_frame$gene<-substring(gene_frame$gene,10,)
gene_frame$gene<-getSYMBOL(gene_frame$gene, data='org.Hs.eg')

makePathwayEdges <- function (gene_edges, pathway_gene_map) 
{
  . <- frequency <- base_gene_src <- base_gene_dest <- i.pathway <- gene <- src_pathway <- dest_pathway <- NULL
  res <- gene_edges[pathway_gene_map, .(frequency, base_gene_src, 
                                        base_gene_dest, src_pathway = i.pathway), on = .(base_gene_src = gene), 
                    allow.cartesian = TRUE, nomatch = 0L][pathway_gene_map, 
                                                          .(frequency, base_gene_src, base_gene_dest, src_pathway, 
                                                            dest_pathway = i.pathway), on = .(base_gene_dest = gene), 
                                                          allow.cartesian = TRUE, nomatch = 0L]
  return(list(edges_all = res, edges_pathways = res[src_pathway != 
                                                      dest_pathway, .(weight_sum = sum(frequency)), by = .(src_pathway, 
                                                                                                           dest_pathway)]))
}


createPathwayEdges<-function (x, graph_layout = NULL, rescale_node = c(2, 10), rescale_label = c(0.5, 
                                                                             0.6), ...) 
{
  edges_pathways_list <- makePathwayEdges(x$graph$edgelist, 
                                          x$graph$pathways)
  edges_pathways <- edges_pathways_list[["edges_pathways"]]
  edges_all <- edges_pathways_list[["edges_all"]]
  write.table(edges_pathways, file.path(writeDir, "./pathway_edges.csv"),
   append = FALSE, sep=",", row.names = FALSE, col.names = TRUE)
}


createPathwayEdges(pathway_tests_rehe)

gene_frame_unref <- gene_frame
gene_frame_ref <- gene_frame[which(gene_frame$pFdr <= 0.1), ]

edge_listRef$base_gene_src <- getSYMBOL(edge_listRef$base_gene_src, data='org.Hs.eg')
edge_listRef$base_gene_dest <- getSYMBOL(edge_listRef$base_gene_dest, data='org.Hs.eg')

write.table(gene_frame_ref, file.path(writeDir,"./gene_results.csv"), append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)

write.table(pathway_results, file.path(writeDir,"./pathway_results.csv"), append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)

write.table(pathway_results_unref, file.path(writeDir,"./pathway_results_unref.csv"), append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)

write.table(gene_frame_unref, file.path(writeDir,"./gene_results_unref.csv"), append = FALSE, sep = ",",
            row.names = FALSE, col.names = TRUE)

write.table(edge_listRef, file.path(writeDir,"./gene_edge_list.csv"), append = FALSE, sep= ",", 
            row.names=FALSE, col.names = TRUE)