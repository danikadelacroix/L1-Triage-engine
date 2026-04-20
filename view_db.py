from database import get_all_complaints
import json

complaints = get_all_complaints()

print(f"Found {len(complaints)} tickets in the database.\n")
print("=" * 60)

for row in complaints:
    print(f"🎫 TICKET ID: {row['id']}")
    print(f"⚠️ COMPLAINT: {row['complaint_text']}")
    print(f"🤖 CATEGORY: {row['category']} | PRIORITY: {row['priority']} | ESCALATED: {row['escalated']}")
    
    # The resolution is stored as a JSON string, let's format it nicely
    try:
        res = json.loads(row['resolution'])
        print(f"\n✅ AI SUMMARY: {res.get('summary')}")
        print("🛠️ IMMEDIATE ACTIONS:")
        for action in res.get('immediate_actions', []):
            print(f"  - {action}")
    except:
        print(f"\n✅ AI RESOLUTION: {row['resolution']}")
        
    print("=" * 60)