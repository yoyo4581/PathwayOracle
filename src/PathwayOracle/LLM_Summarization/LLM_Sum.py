from langchain.docstore.document import Document
from collections import defaultdict
from typing import Literal
import operator
from typing import Annotated, List, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langchain.chains.combine_documents.reduce import (
            acollapse_docs,
            split_list_of_docs,
        )

from ..db import llm


class LLM_Summ:
    # Map
    token_max = 1000

    map_template = """
    The following are responses from an LLM Agent answering questions about genes specifically to their association with a subject matter: {context}.
    Do the following operations to the document:
    1. Evaluate whether the information provided links the gene to the subject matter directly. If it does not clearly state so.
    2. If the information does link it to the subject matter summarize the information in a clear fashion, it could be useful to understand format of the information and what it means.
        - Function describes all documented specific roles that the gene carries out
        - Genes Involved describes all directly interacting genes with the subject gene.
        - The ontology describes how the subject gene functionally relates to the interacting genes in a biological process.
        - The publication information describes and cites specific publications where the gene is implicated in the subject matter. Maintain the PMID in the summary.
    3. In the event that a gene is relevant, use the publication information to guide your summary response.
    4. In the event that a gene is relevant, provide the expression value in the document metadata to give an evaluation of how differentially expressed it is.
    """

    reduce_template = """
    The following is a set of summaries:
    {docs}
    Your goal is to explain why the gene is implicated with the subject using this information. Thus, break concepts down.

    Only cover genes that demonstrate substantial evidence to be implicated with the subject matter. 
    On relevant genes cover genes they are associated with. 
    A gene's ontology with another gene shows that they are in direct interaction and describes the functional role of that interaction.

    Create a cohesive summary in paragraph format, that is clear and concise.
    When referencing publications mention the findings and how they are relevant to the subject matter.
    
    Do not treat every summary equivocally in terms of focus. Instead focus on the relevant summaries with passing mentions to other genes.
    When publication information is referenced maintain the PMID.
    """

    evaluation_template = """
    You are given a document that includes information about genes and their association with a subject matter.
    Your task is to determine if this document contains substantial conclusive evidence to be considered significant for summarization.
    Be strict in your classification criteria.

    Evaluate the document based on:
    - If there are explicit functional or ontological details or publications linking the gene to the subject matter.

    Return 'retain' if the document should be kept, or 'discard' if it should be ignored.
    Document: {content}
    """

    def __init__(self, groupedDocuments, subject, token_max):
        self.groupedDocuments = self.expressionOrganize(groupedDocuments)
        self.llm = llm
        self.subject = subject
        self.app_big = self.buildSumm()
        self.app_small = self.smallBuild()
        self.token_max = token_max

        
    def expressionOrganize(self, componentDocs):
        
        # Helper function to get the 'Exp' value from a document
        def get_exp_value(doc):
            return doc.metadata.get('Exp', 0)

        # Step 1: Sort the documents inside each subcomponent based on the 'Exp' value
        for component, subcomponents in componentDocs.items():
            for subcomp_key, documents in subcomponents.items():
                # Sort the document list in each subcomponent
                documents.sort(key=get_exp_value, reverse=True)

        # Step 2: Sort the subcomponents based on the maximum 'Exp' value in the documents
        for component, subcomponents in componentDocs.items():
            subcomponets_list = list(subcomponents.items())

            subcomponets_list.sort(key=lambda sc: max(get_exp_value(doc) for doc in sc[1]), reverse=True)

            componentDocs[component] = defaultdict(list, subcomponets_list)

        # Step 3: Sort the components based on the maximum 'Exp' value across their subcomponents
        sorted_components = sorted(
            componentDocs.items(),
            key = lambda comp: max(max(get_exp_value(doc) for doc in sub[1]) for sub in comp[1].items()),
            reverse = True
        )

        componentDocs = defaultdict(list, sorted_components)
        return componentDocs

    def buildSumm(self):

        def length_function(documents: List[Document]) -> int:
            """Get number of tokens for input contents."""
            return sum(llm.get_num_tokens(doc.page_content) for doc in documents)

        map_prompt = ChatPromptTemplate([("human", self.map_template)])
        reduce_prompt = ChatPromptTemplate([("human", self.reduce_template)])

        map_chain = map_prompt | llm | StrOutputParser()
        reduce_chain = reduce_prompt | llm | StrOutputParser()


        class OverallState(TypedDict):
            contents: List[Document]
            summaries: Annotated[list, operator.add]
            collapsed_summaries: List[Document]  # add key for collapsed summaries
            final_summary: str
            retain: bool

        # This will be the state of the node that we will "map" all
        # documents to in order to generate summaries
        class SummaryState(TypedDict):
            content: str

        # Here we generate a summary, given a document
        async def generate_summary(state: SummaryState):
            response = await map_chain.ainvoke(state["content"])
            return {"summaries": [response]}

        # Add node to store summaries for collapsing
        def collect_summaries(state: OverallState):
            return {
                "collapsed_summaries": [Document(summary) for summary in state["summaries"]]
            }

        # Here we define the logic to map out over the documents
        # We will use this an edge in the graph
        def map_summaries(state: OverallState):
            # We will return a list of `Send` objects
            # Each `Send` object consists of the name of a node in the graph
            # as well as the state to send to that node
            return [
                Send("generate_summary", {"content": content}) for content in state["contents"]
            ]

        # A new node to evaluate the significance of each document
        async def evaluate_final_summary(state: OverallState):
            eval_prompt = ChatPromptTemplate([("human", self.evaluation_template)])
            eval_chain = eval_prompt | llm | StrOutputParser()
            
            response = await eval_chain.ainvoke(state["final_summary"])
            print('Significant: ', response.strip().lower())
            if response.strip().lower() == 'retain':
                return {"final_summary": state["final_summary"], "retain": True}
            else:
                return {"final_summary": state['final_summary'], "retain": False}



        # Modify final summary to read off collapsed summaries
        async def generate_final_summary(state: OverallState):
            response = await reduce_chain.ainvoke(state["collapsed_summaries"])
            return {"final_summary": response}


        graph = StateGraph(OverallState)
        graph.add_node("generate_summary", generate_summary)  # same as before
        graph.add_node("collect_summaries", collect_summaries)
        graph.add_node("generate_final_summary", generate_final_summary)
        # Add the new evaluation node to the graph
        graph.add_node("evaluate_final_summary", evaluate_final_summary)


        # Add node to collapse summaries
        async def collapse_summaries(state: OverallState):
            doc_lists = split_list_of_docs(
                state["collapsed_summaries"], length_function, self.token_max
            )
            results = []
            for doc_list in doc_lists:
                results.append(await acollapse_docs(doc_list, reduce_chain.ainvoke))

            return {"collapsed_summaries": results}


        graph.add_node("collapse_summaries", collapse_summaries)


        def should_collapse(
            state: OverallState,
        ) -> Literal["collapse_summaries", "generate_final_summary"]:
            num_tokens = length_function(state["collapsed_summaries"])
            if num_tokens > self.token_max:
                return "collapse_summaries"
            else:
                return "generate_final_summary"


        graph.add_conditional_edges(START, map_summaries, ["generate_summary"])
        graph.add_edge("generate_summary", "collect_summaries")
        graph.add_conditional_edges("collect_summaries", should_collapse)
        graph.add_conditional_edges("collapse_summaries", should_collapse)
        graph.add_edge("generate_final_summary", "evaluate_final_summary")
        graph.add_edge("evaluate_final_summary", END)
        app = graph.compile()

        return app
    
    def smallBuild(self):

        def length_function(documents: List[Document]) -> int:
            """Get number of tokens for input contents."""
            return sum(llm.get_num_tokens(doc.page_content) for doc in documents)

        map_prompt = ChatPromptTemplate([("human", self.map_template)])
        reduce_prompt = ChatPromptTemplate([("human", self.reduce_template)])

        map_chain = map_prompt | llm | StrOutputParser()
        reduce_chain = reduce_prompt | llm | StrOutputParser()


        class OverallState(TypedDict):
            contents: List[Document]
            summaries: List[str]  # Adjusted to List[str] for storing summaries as strings
            collapsed_summaries: List[Document]
            final_summary: str
            retain: bool

        class SummaryState(TypedDict):
            content: str
            retain: bool  # Add retain status to SummaryState


        async def generate_summary(state: SummaryState):
            response = await map_chain.ainvoke(state["content"])
            return {"summaries": [response]}

        def collect_summaries(state: OverallState):
            return {
                "collapsed_summaries": [Document(summary) for summary in state["summaries"]]
            }

        async def evaluate_summary(state: SummaryState):
            
            eval_prompt = ChatPromptTemplate([("human", self.evaluation_template)])
            eval_chain = eval_prompt | llm | StrOutputParser()
            
            response = await eval_chain.ainvoke(state["content"])
            retain_value = response.strip().lower() == 'retain'
            
            return {"retain": retain_value, "content": state["content"]}

        def map_summaries(state: OverallState):
            return [
                Send("evaluate_summary", {"content": content, "retain": None}) for content in state["contents"]
            ]

        async def generate_final_summary(state: OverallState):
            response = await reduce_chain.ainvoke({"docs": state["collapsed_summaries"]})
            return {"final_summary": response, "retain": state['retain']}

        # Add conditional logic after evaluation
        def handle_evaluation(state: SummaryState):
            retain_value = state["retain"]
            
            if not retain_value:
                # If retain is False, terminate early and return the final summary
                return END
            else:
                # If retain is True, continue with summarization
                return "generate_summary"


        async def collapse_summaries(state: OverallState):
            doc_lists = split_list_of_docs(
                state["collapsed_summaries"], length_function, self.token_max
            )
            results = []
            for doc_list in doc_lists:
                results.append(await acollapse_docs(doc_list, reduce_chain.ainvoke))

            return {"collapsed_summaries": results}

        def should_collapse(
            state: OverallState,
        ) -> Literal["collapse_summaries", "generate_final_summary"]:
            num_tokens = length_function(state["collapsed_summaries"])
            if num_tokens > self.token_max:
                return "collapse_summaries"
            else:
                return "generate_final_summary"

        graph_small = StateGraph(OverallState)
        graph_small.add_node("generate_summary", generate_summary)
        graph_small.add_node("collect_summaries", collect_summaries)
        graph_small.add_node("generate_final_summary", generate_final_summary)
        graph_small.add_node("evaluate_summary", evaluate_summary)
        graph_small.add_node("collapse_summaries", collapse_summaries)

        graph_small.add_conditional_edges(START, map_summaries, ["evaluate_summary"])
        graph_small.add_conditional_edges("evaluate_summary", handle_evaluation)
        graph_small.add_edge("generate_summary", "collect_summaries")
        graph_small.add_conditional_edges("collect_summaries", should_collapse)
        graph_small.add_conditional_edges("collapse_summaries", should_collapse)
        graph_small.add_edge("generate_final_summary", END)

        app_small = graph_small.compile()

        return app_small
