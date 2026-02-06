import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.neo4j_client import Neo4jClient

class LoreExtractor:
    def __init__(self):
        self.db = Neo4jClient()
        self.db.connect()
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    def extract_and_upload(self, text):
        prompt = f"""
        Analyze the text below and extract Genshin Impact lore relationships.
        Return a JSON object with "entities" and "relationships".

        1. "entities": A list of unique characters/locations.
           - "canonical_name": The most common/official name (e.g., "King Deshret").
           - "aliases": A list of OTHER names used in the text (e.g., ["Al-Ahmar", "The Scarlet King"]).
           - "label": The type (e.g., "Person", "God", "Location").

        2. "relationships": A list of connections.
           - "source": The CANONICAL name of the first entity.
           - "target": The CANONICAL name of the second entity.
           - "type": The relationship type (in SCREAMING_SNAKE_CASE, e.g., "ALLIED_WITH").

        RULES FOR RELATIONSHIPS:
        1. **Direction Matters**: The "source" is the ACTOR or the CHILD. The "target" is the RECEIVER or PARENT.
        2. **Descendants**: If X is descended from Y, then Source=X, Target=Y, Type=DESCENDED_FROM.
        3. **Locations**: If X is trapped in Y, then Source=X, Target=Y, Type=TRAPPED_IN.
        4. **Creation**: If X created Y, then Source=X, Target=Y, Type=CREATED.
        
        CRITICAL RULES FOR RELATIONSHIPS:
        1. **Active Voice Only**: Do not use passive relationships like "descended_from" or "worshipped_by".
        2. **Ancestry**: ALWAYS use "ANCESTOR_OF" instead of "descended_from".
           - Direction must be: (Parent/Ancestor) -> (Child/Descendant)
           - WRONG: (Candace)-[DESCENDED_FROM]->(Deshret)
           - RIGHT: (King Deshret)-[ANCESTOR_OF]->(Candace)
           - RIGHT: (King Deshret)-[ANCESTOR_OF]->(Aaru Village Residents)
        3. **Worship**: Use "WORSHIPS".
           - Text: "Eremites worship him." -> (Eremites)-[WORSHIPS]->(Deshret)
        4. **Traps**: Use "TRAPPED_IN".
           - Text: "Faruzan was trapped in ruins." -> (Faruzan)-[TRAPPED_IN]->(Ruins)
        
        EXAMPLES:
        - Text: "Diluc is the son of Crepus."
          Result: {{"source": "Diluc", "target": "Crepus", "type": "CHILD_OF"}}
        - Text: "Jean was healed by Barbara."
          Result: {{"source": "Barbara", "target": "Jean", "type": "HEALED"}}
        - Text: "The Traveler was trapped in the Abyss."
          Result: {{"source": "Traveler", "target": "Abyss", "type": "TRAPPED_IN"}}

        Text to Analyze: 
        {text}
        """

        response = self.llm.invoke(prompt)

        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_content)

        print(f"Processing {len(data['entities'])} entities...")
        for entity in data['entities']:
            entity_cypher = f"""
            MERGE (e:Entity {{name: $canonical_name}})
            ON CREATE SET
                e.aliases = $aliases,
                e.label = $label
            ON MATCH SET
                e.aliases = apoc.coll.toSet(e.aliases + $aliases)
            """
            self.db.query(entity_cypher, parameters=entity)

        print(f"Processing {len(data['relationships'])} relationships...")
        for rel in data['relationships']:
            rel_cypher = f"""
            MERGE (a:Entity {{name: $source}})
            MERGE (b:Entity {{name: $target}})
            MERGE (a)-[r:{rel['type']}]->(b)
            """

            self.db.query(rel_cypher, parameters=rel)
        print(f"Successfully uploaded {len(data['entities'])} entities and {len(data['relationships'])} relationships.")

if __name__ == "__main__":
    extractor = LoreExtractor()
    with open("data/raw/lore.txt", "r") as f:
        content = f.read()
    extractor.extract_and_upload(content)