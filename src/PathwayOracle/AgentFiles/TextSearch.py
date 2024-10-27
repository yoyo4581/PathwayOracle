from typing import Dict, List

from db import cQueryToServer, queryToServer


def get_user_id() -> int:
    """
    Placeholder for a function that would normally retrieve
    a user's ID
    """
    return 1


def remove_lucene_chars(text: str) -> str:
    """Remove Lucene special characters"""
    special_chars = [
        "+",
        "-",
        "&",
        "|",
        "!",
        "(",
        ")",
        "{",
        "}",
        "[",
        "]",
        "^",
        '"',
        "~",
        "*",
        "?",
        ":",
        "\\",
    ]
    for char in special_chars:
        if char in text:
            text = text.replace(char, " ")
    return text.strip()


def generate_full_text_query(input: str) -> str:
    """
    Generate a full-text search query for a given input string.

    This function constructs a query string suitable for a full-text search.
    It processes the input string by splitting it into words and appending a
    similarity threshold (~0.8) to each word, then combines them using the AND
    operator. Useful for mapping movies and people from user questions
    to database values, and allows for some misspelings.
    """
    full_text_query = ""
    words = [el for el in remove_lucene_chars(input).split() if el]
    for word in words[:-1]:
        full_text_query += f" {word}~0.8 AND"
    full_text_query += f" {words[-1]}~0.8"
    return full_text_query.strip()


candidate_query = """
CALL db.index.fulltext.queryNodes('candidateKey', $fulltextQuery, {limit: $limit})
YIELD node
RETURN coalesce(node.name, node.title) AS candidate,
       [el in labels(node) WHERE el IN ['Genes', 'Pathway'] | el][0] AS label
"""


def get_candidates(input: str, limit: int = 3) -> List[Dict[str, str]]:
    """
    Retrieve a list of candidate entities from database based on the input string.

    This function queries the Neo4j database using a full-text search. It takes the
    input string, generates a full-text query, and executes this query against the
    specified index in the database. The function returns a list of candidates
    matching the query, with each candidate being a dictionary containing their name
    (or title) and label (either 'Person' or 'Movie').
    """
    ft_query = generate_full_text_query(input)
    candidates = cQueryToServer(
        query=candidate_query, parameters={"fulltextQuery": ft_query, "index": type, "limit": limit}
    )
    return candidates

def get_MultCandidates(inputs: List[str], limit: int = 3) -> List[Dict[str, str]]:
    """
    Retrieve a list of candidate entities from database based on the input strings.

    This function queries the Neo4j database using a full-text search. It takes the
    input strings, generates a full-text query for each, and executes these queries
    against the specified index in the database. The function returns a list of candidates
    matching the queries, with each candidate being a dictionary containing their name
    (or title) and label (either 'Genes' or 'Pathway').
    """
    all_candidates = []
    for idx in range(len(inputs)):
        ft_query = generate_full_text_query(inputs[idx])
        print(ft_query)
        candidates = cQueryToServer(
            query=candidate_query, parameters={"fulltextQuery": ft_query, "limit": limit}
        )
        print('candidates', candidates)
        # if there are multiple candidates
        if len(candidates)>1:
            mult_res = {'candidate': [ cand['candidate'] for cand in candidates ], 'label': [cand['label'] for cand in candidates]}
            # checks if the input string is already verbatim found in the multiple candidates
            if inputs[idx] in mult_res['candidate']:
                for cand in candidates:
                    if cand['candidate']==inputs[idx]:
                        all_candidates.append(cand)
            else:
                all_candidates.append(mult_res)
        else:
            all_candidates.extend(candidates)

    print('all_candidates', all_candidates)
    return all_candidates


