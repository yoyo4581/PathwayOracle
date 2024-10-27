from neo4j import GraphDatabase
from langchain.vectorstores.neo4j_vector import Neo4jVector
from transformers import AutoTokenizer, AutoModel
import torch

class BioBertEmbeddings:
    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model

    def embed_query(self, text):
        return self.get_embeddings([text])[0]

    def embed_documents(self, documents):
        return self.get_embeddings(documents)

    def get_embeddings(self, texts):
        inputs = self.tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).detach().numpy()

# Example usage
tokenizer = AutoTokenizer.from_pretrained("dmis-lab/biobert-base-cased-v1.2")
model = AutoModel.from_pretrained("dmis-lab/biobert-base-cased-v1.2")

bio_bert_embeddings = BioBertEmbeddings(tokenizer, model)