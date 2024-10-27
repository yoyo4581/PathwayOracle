import networkx as nx


def parseOutInfo(gene_names, getGeneInt, getBaseOnto, getOntoNet):

    fullString = ''
    for intX in getGeneInt:
        fullString += f"{intX['gene1']} is a {intX['relat']} of {intX['gene2']} in the {intX['Pathway']} pathway \n"
    
    
    def formatOntoTuples(OntoNet, BaseOnto):
        allTuples = []
        for onto in OntoNet:
            tup1 = onto['fromNodeName']
            tup2 = onto['toNodeName']
            tupComp = (tup1, tup2)
            allTuples.append(tupComp)
    
        for base in BaseOnto:
            tup1 = base['geneName']
            tup2 = base['baseOnto']
            tupComp = (tup1, tup2)
            allTuples.append(tupComp)
    
        return allTuples
    
    edges = formatOntoTuples(OntoNet = getOntoNet, BaseOnto = getBaseOnto)
    
    # Create a directed graph
    G = nx.DiGraph()
    
    G.add_edges_from(edges)
    
    # Function to check if a node links back to all gene nodes
    def links_back_to_all_genes(target_node, gene_names, G):
        for gene in gene_names:
            if not nx.has_path(G, gene, target_node):
                return False
        return True
    
    # Find the ontology node that links back to all other gene nodes
    def find_common_ontology_node(gene_names, G):
        for node in G.nodes:
            if node not in gene_names and links_back_to_all_genes(node, gene_names, G):
                return node
        return None
    
    # Find the common ontology node
    common_node = find_common_ontology_node(gene_names, G)
    fullString += f"The common ontology node is: {common_node} \n"
    
    # Function to find and print paths from gene nodes to the common ontology node
    def find_paths_to_common_node(gene_names, common_node, G):
        paths = {}
        for gene in gene_names:
            if nx.has_path(G, gene, common_node):
                path = nx.shortest_path(G, source=gene, target=common_node)
                paths[gene] = path
        return paths
    
    # Find and print the paths
    paths_to_common_node = find_paths_to_common_node(gene_names, common_node, G)
    
    for gene, path in paths_to_common_node.items():
        if len(path) > 0:
            path_parsed = path[0] + ' is involved in ' + ' which is a subclass of '.join(path[1:])
            fullString += f"Path from {gene} to {common_node}: {path_parsed} \n"

    return fullString
