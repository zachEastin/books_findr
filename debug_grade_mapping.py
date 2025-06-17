import json
import requests

# Load grades.json
with open('data/grades.json', 'r') as f:
    grades_data = json.load(f)

# Load books.json
with open('books.json', 'r') as f:
    books_data = json.load(f)

print("=== GRADE ANALYSIS ===")
for grade_name in ['Kindergarten', '4th Grade', '5th Grade', '6th Grade']:
    books_in_grade = grades_data.get(grade_name, [])
    print(f"\n{grade_name}: {len(books_in_grade)} books in grades.json")
    
    # Check how many of these books exist in books.json
    books_with_data = 0
    books_without_data = []
    
    for book_title in books_in_grade[:5]:  # Check first 5 books
        if book_title in books_data:
            books_with_data += 1
        else:
            books_without_data.append(book_title)
    
    print(f"  - Books with metadata in books.json: {books_with_data}/5")
    if books_without_data:
        print(f"  - Books without metadata: {books_without_data}")

# Also check API response
print("\n=== API RESPONSE ===")
try:
    r = requests.get('http://127.0.0.1:5000/api/dashboard-data')
    data = r.json()
    
    if data['success']:
        api_grades = data['data']['books_by_grade']
        for grade_name in ['Kindergarten', '4th Grade', '5th Grade', '6th Grade']:
            books = api_grades.get(grade_name, [])
            print(f"{grade_name}: {len(books)} books in API response")
            if books:
                print(f"  Sample titles: {[book['title'] for book in books[:3]]}")
    else:
        print("API error:", data.get('error'))
except Exception as e:
    print("API call failed:", e)
