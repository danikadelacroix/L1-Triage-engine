"""
rag_pipeline.py — RAG pipeline updated to ingest the NovaTech KB.

Usage (standalone test):
    python rag_pipeline.py
"""

import os
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import OllamaLLM

from config import OLLAMA_MODEL

load_dotenv()

# ── Constants ──────────────────────────────────────────────────────────────────

KB_DIR = "./kb_docs"                  # folder where novatech_kb.txt lives
CHROMA_DIR = "./chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Larger overlap than original (200 → 400) so policy tables don't lose
# their header row when they span a chunk boundary
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 400

# ── Models ─────────────────────────────────────────────────────────────────────

embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
llm = OllamaLLM(model=OLLAMA_MODEL)


# ── Ingestion ──────────────────────────────────────────────────────────────────

def ingest_documents():
    """
    Loads all .txt files from KB_DIR, splits them, embeds, and stores in
    ChromaDB. Safe to re-run — Chroma deduplicates on the persist_directory.

    To prepare the NovaTech KB:
        1. Export novatech_kb.docx as plain text (.txt) — File > Save As > Plain Text
           OR use: python -c "import docx2txt; print(docx2txt.process('novatech_kb.docx'))" > kb_docs/novatech_kb.txt
        2. Place the .txt file in ./kb_docs/
        3. Run: python first_script.py
    """
    os.makedirs(KB_DIR, exist_ok=True)

    loader = DirectoryLoader(
        KB_DIR,
        glob="**/*.txt",
        loader_cls=lambda path: TextLoader(path, encoding="utf-8"),
    )
    docs = loader.load()

    if not docs:
        print(f"⚠️  No .txt files found in {KB_DIR}. "
              "Please export novatech_kb.docx as novatech_kb.txt and place it there.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Split on section/heading boundaries first, then paragraphs, then sentences
        separators=["\n# ", "\n## ", "\n### ", "\n\n", "\n", " "],
    )
    split_docs = splitter.split_documents(docs)
    print(f"📄 Loaded {len(docs)} document(s) → {len(split_docs)} chunks")

    vectorstore = Chroma.from_documents(
        documents=split_docs,
        embedding=embedding_model,
        persist_directory=CHROMA_DIR,
    )
    print(f"✅ ChromaDB updated at {CHROMA_DIR}")
    return vectorstore


# ── Retriever (used by multi_agent.py) ────────────────────────────────────────

def get_retriever():
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embedding_model,
    )
    return vectorstore.as_retriever(search_kwargs={"k": 4})


# ── RAG chain (standalone, for testing) ───────────────────────────────────────

retriever = get_retriever()

prompt_template = """
You are the NovaTech L1 Support Engine — an AI assistant for NovaTech Solutions employees.

Your job is to resolve IT and HR support queries accurately using the company's
official Knowledge Base. Always cite the Policy ID if relevant (e.g. IT-003, HR-001).

Rules:
- Answer only using the provided context. Do not invent policies or URLs.
- If the answer is in the context, be specific: include SLA times, URLs, form names, contact emails.
- If the context does not contain enough information, say: "I don't have enough information
  to resolve this. Please raise a ticket at support.novatech.in or contact helpdesk@novatech.in."
- Keep the response concise and actionable.

Employee Query: {question}

Knowledge Base Context:
{context}
"""

rag_prompt = ChatPromptTemplate.from_template(prompt_template)

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)


# ── Standalone test ────────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     test_queries = [
#         "How do I reset my NovaTech password? I'm locked out.",
#         "I can't connect to the VPN and keep getting an MFA error.",
#         "What is my annual leave entitlement and how do I apply?",
#         "My March salary seems incorrect — who do I contact?",
#         "I want to report my manager for harassment. What do I do?",
#     ]

#     print("\n🔍 RAG Pipeline Test — NovaTech KB\n")
#     print("=" * 60)

#     for query in test_queries:
#         print(f"\n❓ Query: {query}")
#         print(f"💬 Response:\n{rag_chain.invoke(query)}")
#         print("─" * 60)


if __name__ == "__main__":
    test_queries = [
        "How do I reset my NovaTech password? I'm locked out.",
        "I want to report my manager for harassment. What do I do?",
    ]

    print("\n🔍 RAG Pipeline Debugger\n")
    print("=" * 60)

    for query in test_queries:
        print(f"\n❓ Query: {query}")
        
        # 1. TEST THE RETRIEVER (ChromaDB)
        print("\n--- WHAT CHROMADB FOUND (CONTEXT) ---")
        docs = retriever.invoke(query)
        
        if not docs:
            print("❌ ChromaDB found NOTHING. The database is empty or the search failed.")
        else:
            for i, doc in enumerate(docs):
                print(f"\n[Chunk {i+1}]:\n{doc.page_content}")
                print("-" * 40)
        
        # 2. TEST THE LLM (Mistral)
        print("\n--- WHAT MISTRAL ANSWERED ---")
        response = rag_chain.invoke(query)
        print(response)
        print("=" * 60)