import requests
import json

# Test the API endpoint
try:
    r = requests.get('http://127.0.0.1:5000/api/dashboard-data')
    data = r.json()
    
    if data['success']:
        grades = data['data']['books_by_grade']
        print("All grades with book counts:")
        for grade, books in sorted(grades.items()):
            print(f"{grade}: {len(books)} books")
            
        print("\nDetailed check for missing grades:")
        for grade in ['4th Grade', '5th Grade', '6th Grade']:
            books = grades.get(grade, [])
            print(f"\n{grade}: {len(books)} books")
            if books:
                print("  Sample books:")
                for book in books[:3]:
                    print(f"    - {book['title']}")
    else:
        print("API returned error:", data.get('error'))
        
except Exception as e:
    print("Error:", e)

# Also check the grades.json file directly
print("\n" + "="*50)
print("Direct from grades.json:")
with open('data/grades.json', 'r') as f:
    grades_json = json.load(f)
    
for grade in ['4th Grade', '5th Grade', '6th Grade']:
    books = grades_json.get(grade, [])
    print(f"\n{grade}: {len(books)} books")
    if books:
        print("  Sample books:")
        for book in books[:3]:
            print(f"    - {book}")
