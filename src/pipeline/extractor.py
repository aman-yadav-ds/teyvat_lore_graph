import os
import json
import time
import glob
import re
from langchain_ollama import ChatOllama # CHANGED: Switched from Google to Ollama
from src.utils.neo4j_client import Neo4jClient

class LoreExtractor:
    def __init__(self):
        self.db = Neo4jClient()
        self.db.connect()
        
        # CHANGED: Initialize Local LLM
        # "format": "json" is CRITICAL. It forces the model to only output valid JSON.
        # temperature=0 makes it deterministic (less creative, more precise).
        self.llm = ChatOllama(
            model="qwen2.5:7b", 
            temperature=0,
            format="json" 
        )

    def chunk_text(self, text, chunk_size=6000):
        # CHANGED: Local models have smaller context windows than Gemini.
        # Reduced chunk_size to 6000 chars to be safe for 8k context window.
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    def clean_json_string(self, json_str):
        """Helper to strip markdown if the model adds it despite instructions."""
        json_str = json_str.replace("```json", "").replace("```", "").strip()
        return json_str

    def process_directory(self, dir_path="data/raw"):
        files = glob.glob(os.path.join(dir_path, "*.txt"))
        print(f"📂 Found {len(files)} files. Starting Local Extraction (Qwen 2.5 7B)...")

        for filepath in files:
            filename = os.path.basename(filepath)
            print(f"\n📖 Reading {filename}...")
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                if len(content) < 100: continue

                chunks = self.chunk_text(content)
                print(f"   🧩 Split into {len(chunks)} chunks.")

                for i, chunk in enumerate(chunks):
                    print(f"   🤖 Processing chunk {i+1}/{len(chunks)}...")
                    self.extract_and_upload(chunk, source_file=filename)
                    # No time.sleep() needed! You own the hardware.

            except Exception as e:
                print(f"   ❌ Error processing {filename}: {e}")

    def extract_and_upload(self, text, source_file="Unknown"):
        # SIMPLIFIED PROMPT: Smaller models need less "fluff" and more concrete examples.
        prompt = f"""
        Extract Genshin Impact lore entities and relationships from the text below.
        
        CRITICAL: Output MUST be valid JSON.
        
        Schema:
        {{
            "entities": [
                {{"canonical_name": "Name", "aliases": ["Alias1"], "label": "Type"}}
            ],
            "relationships": [
                {{"source": "Name1", "target": "Name2", "type": "RELATIONSHIP_TYPE"}}
            ]
        }}

        Rules:
        1. Use 'ANCESTOR_OF' (Active voice) instead of 'DESCENDED_FROM'.
        2. Use 'WORSHIPS' (Active voice) instead of 'WORSHIPPED_BY'.
        3. If you see [TABLE_DATA], extract the rows as facts.

        Text:
        {text}
        """

        try:
            response = self.llm.invoke(prompt)
            clean_content = self.clean_json_string(response.content)
            data = json.loads(clean_content)

            # 1. Upload Entities
            count_ent = 0
            for entity in data.get('entities', []):
                if not entity.get('canonical_name'): continue
                
                entity_cypher = """
                MERGE (e:Entity {name: $canonical_name})
                ON CREATE SET e.aliases = $aliases, e.label = $label, e.source_file = $source
                ON MATCH SET e.aliases = apoc.coll.toSet(e.aliases + $aliases)
                """
                entity['source'] = source_file
                self.db.query(entity_cypher, parameters=entity)
                count_ent += 1

            # 2. Upload Relationships
            count_rel = 0
            for rel in data.get('relationships', []):
                if not rel.get('source') or not rel.get('target'): continue
                
                rel_cypher = f"""
                MATCH (a:Entity {{name: $source}})
                MATCH (b:Entity {{name: $target}})
                MERGE (a)-[:{rel['type']}]->(b)
                """
                self.db.query(rel_cypher, parameters=rel)
                count_rel += 1
            
            print(f"      ✅ Extracted {count_ent} entities, {count_rel} relations.")

        except json.JSONDecodeError:
            print(f"      ⚠️ Model failed to generate valid JSON. Skipping chunk.")
        except Exception as e:
            print(f"      ⚠️ Neo4j Error: {e}")

if __name__ == "__main__":
    extractor = LoreExtractor()
    extractor.process_directory()