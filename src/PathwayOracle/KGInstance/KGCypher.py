# Links User to nodes
linkGenes = """
// Load the genes and pathways from CSV files
WITH $gene_list as gene_list
WITH gene_list, range(0, size(gene_list) -1) as indices
UNWIND indices as idx
MATCH (g:Genes {name: gene_list[idx]}), (u:User {id: $user_id})-[:CREATED]->(i:Instance {instance_id: $instance_id})
MERGE (i)-[l:LINKED_TO {subject: $subject, expression: $gene_exp[idx], significance: $gene_sig[idx], instance_id: $instance_id}]->(g)
RETURN count(l) as linkCount
"""
# Link Instance to nodes, place data in link parameters. Link type is LINKED_TO.
linkPaths = """
// Load the genes and pathways from CSV files
WITH $path_list as path_list
WITH path_list, range(0, size(path_list) -1) as indices
UNWIND indices as idx
MATCH (p:Pathway {name: path_list[idx]}), (u:User {id: $user_id})-[:CREATED]->(i:Instance {instance_id: $instance_id})
MERGE (i)-[l:LINKED_TO {subject: $subject, expression: $path_exp[idx], significance: $path_sig[idx], pSize: $path_size, instance_id: $instance_id}]->(p)
RETURN count(l) as linkCount
"""
# Label relationships between genes nodes linked to instance
linkGeneRelationships = """
WITH $path_list AS path_list
MATCH (i:Instance)-[l:LINKED_TO]->(g:Genes)
MATCH (g)-[r]-(g2:Genes)
MATCH (g2)<-[l2:LINKED_TO]-(i)
WHERE i.instance_id = $instance_id 
    AND l.instance_id = $instance_id 
    AND l2.instance_id = $instance_id 
    AND id(g2) <> id(g) 
    AND r.Pathway IN path_list
SET r.instance_ids = CASE 
                        WHEN $instance_id IN coalesce(r.instance_ids, []) THEN r.instance_ids 
                        ELSE coalesce(r.instance_ids, []) + $instance_id 
                        END
WITH r
WHERE $instance_id IN r.instance_ids
RETURN count(r) AS linkCount
"""
# Label relationships between genes and pathway nodes linked to instance
linkPathRelationships = """
MATCH (i:Instance)-[l:LINKED_TO]->(g:Genes)
MATCH (g)-[b:belongs_to]->(p:Pathway)
MATCH (p)<-[l2:LINKED_TO]-(i)
WHERE i.instance_id = $instance_id
    AND l.instance_id = $instance_id
    AND l2.instance_id = $instance_id
SET b.instance_ids = CASE 
                        WHEN $instance_id IN coalesce(b.instance_ids, []) THEN b.instance_ids 
                        ELSE coalesce(b.instance_ids, []) + $instance_id 
                        END
WITH b
WHERE $instance_id IN b.instance_ids
RETURN count(b) as linkCount
"""
# Label relationships between genes nodes and their function nodes
linkFuncNodes = """
MATCH (i:Instance)-[:LINKED_TO]->(g:Genes)
MATCH (g)-[c:CONTAINS]->(tn:TextNode)
WHERE i.instance_id = $instance_id
SET c.instance_ids = CASE 
                    WHEN $instance_id IN coalesce(c.instance_ids, []) THEN c.instance_ids 
                    ELSE coalesce(c.instance_ids, []) + $instance_id 
                    END
WITH c
WHERE $instance_id IN c.instance_ids
RETURN count(c) as linkCount
"""
# Create a graph projection such that the projection takes into account only linked genes and pathways and their relationships.
# This does not include free-floating genes, or genes that are significant but not linked to significant pathways.
graph_proj = """
// Create a graph projection
CALL gds.graph.project.cypher(
    $graphName,
    'MATCH (i:Instance {instance_id: $instance_id})-[:LINKED_TO {instance_id: $instance_id}]-(n)
        WHERE (n:Genes OR n:Pathway) AND n.name IS NOT NULL
        WITH n
        MATCH (n)-[r]-(m)
        WHERE (m:Genes OR m:Pathway) AND $instance_id IN coalesce(r.instance_ids, [])
        RETURN id(n) AS id',
    'MATCH (n)-[r]-(m)
        WHERE id(n) < id(m) AND (m:Genes OR m:Pathway) AND (n:Genes OR n:Pathway) AND $instance_id IN coalesce(r.instance_ids, [])
        RETURN id(n) AS source, id(m) AS target',
        {parameters: {instance_id: $instance_id}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
"""
# Conduct wcc analysis retaining component nodes and their component number
wcc_analysis = """
CALL gds.wcc.stream($graphName)
YIELD nodeId, componentId
WHERE gds.util.asNode(nodeId).name IS NOT NULL
RETURN gds.util.asNode(nodeId).name AS name, componentId
ORDER BY componentId, name
"""
# Retrieve wcc analysis results.
wcc_summ = """
CALL gds.wcc.stats($graphName)
YIELD componentCount, preProcessingMillis, computeMillis, postProcessingMillis, componentDistribution, configuration
"""