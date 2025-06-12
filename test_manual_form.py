#!/usr/bin/env python3
"""
Test script to verify the automatic manual form feature works correctly.
This script tests the /api/books endpoint with invalid data to trigger the manual form.
"""

import requests
import json

def test_isbn_search_failure():
    """Test that failed ISBN search returns manual form trigger."""
    print("Testing failed ISBN search...")
    
    # Test with a fake ISBN that should not be found
    fake_isbn = "9999999999999"
    
    response = requests.post('http://127.0.0.1:5000/api/books', 
                           json={
                               'mode': 'isbn',
                               'title': 'Test Book Title',
                               'isbn': fake_isbn,
                               'grade': '3rd Grade'
                           })
    
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('show_manual_form') and data.get('prefill_data'):
            print("✅ ISBN search failure correctly returns manual form trigger")
            print(f"Prefill data: {data['prefill_data']}")
            return True
        else:
            print("❌ ISBN search failure did not return manual form trigger")
            return False
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
        return False

def test_title_author_search_failure():
    """Test that failed title/author search returns manual form trigger."""
    print("\nTesting failed title/author search...")
    
    # Test with a fake title/author that should not be found
    fake_title = "This Book Absolutely Does Not Exist Anywhere"
    fake_author = "Nonexistent Author Person"
    
    response = requests.post('http://127.0.0.1:5000/api/books', 
                           json={
                               'mode': 'title',
                               'title': fake_title,
                               'author': fake_author,
                               'grade': '5th Grade'
                           })
    
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('show_manual_form') and data.get('prefill_data'):
            print("✅ Title/author search failure correctly returns manual form trigger")
            print(f"Prefill data: {data['prefill_data']}")
            return True
        else:
            print("❌ Title/author search failure did not return manual form trigger")
            return False
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
        return False

def main():
    """Run all tests."""
    print("Testing automatic manual form feature...")
    print("=" * 50)
    
    try:
        test1_passed = test_isbn_search_failure()
        test2_passed = test_title_author_search_failure()
        
        print("\n" + "=" * 50)
        if test1_passed and test2_passed:
            print("✅ All tests passed! The automatic manual form feature is working correctly.")
        else:
            print("❌ Some tests failed. Please check the implementation.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask app. Make sure it's running on http://127.0.0.1:5000")
    except Exception as e:
        print(f"❌ Error during testing: {e}")

if __name__ == "__main__":
    main()
