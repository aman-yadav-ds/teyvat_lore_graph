from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_neo4j import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain 
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from langgraph.graph import StateGraph
import os

load_dotenv()

graph = Neo4jGraph(
            url = os.getenv("NEO4J_URI"),
            username = os.getenv("NEO4J_USERNAME"),
            password = os.getenv("NEO4J_PASSWORD")
        )

print(type(graph))