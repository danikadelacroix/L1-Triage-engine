
from rag_pipeline import get_retriever
r = get_retriever()
queries = [
    'How do I reset my password?',
    'VPN not connecting MFA error',
    'My salary is incorrect this month',
    'I want to report my manager for harassment',
    'How do I install PyCharm?',
    'What is the escalation path for a Sev-1 incident?'
]
for q in queries:
    print(f'\n>>> QUERY: {q}')
    docs = r.invoke(q)
    for i, d in enumerate(docs):
        # Added source file tracking
        source = d.metadata.get('source', 'Unknown')
        print(f'  [Chunk {i+1} from {source}]')
        print(f'  Content: {d.page_content[:150].strip()}...')
    print('-'*80)
