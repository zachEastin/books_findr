"""
Performance Test for BooksFindr UI Optimizations
Tests the /api/dashboard-data endpoint performance and overall responsiveness
"""

import time
import requests
import json
from pathlib import Path

def test_dashboard_api_performance():
    """Test the performance of the new dashboard API endpoint"""
    url = "http://127.0.0.1:5000/api/dashboard-data"
    
    print("Testing Dashboard API Performance...")
    print("=" * 50)
    
    # Warm up request
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return
    except requests.ConnectionError:
        print("Error: Could not connect to Flask app. Make sure it's running on localhost:5000")
        return
    
    # Performance test
    times = []
    for i in range(10):
        start_time = time.time()
        response = requests.get(url)
        end_time = time.time()
        
        if response.status_code == 200:
            request_time = (end_time - start_time) * 1000  # Convert to milliseconds
            times.append(request_time)
            print(f"Request {i+1}: {request_time:.2f}ms")
        else:
            print(f"Request {i+1}: FAILED (status {response.status_code})")
    
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print("\nPerformance Summary:")
        print(f"Average response time: {avg_time:.2f}ms")
        print(f"Minimum response time: {min_time:.2f}ms")
        print(f"Maximum response time: {max_time:.2f}ms")
        
        # Check data quality
        final_response = requests.get(url)
        if final_response.status_code == 200:
            data = final_response.json()
            if data.get('success'):
                dashboard_data = data.get('data', {})
                total_books = dashboard_data.get('total_books', 0)
                books_by_grade = dashboard_data.get('books_by_grade', {})
                
                print(f"\nData Quality Check:")
                print(f"Total books loaded: {total_books}")
                print(f"Grade categories: {len(books_by_grade)}")
                
                # Count books per grade
                for grade, books in books_by_grade.items():
                    if books:
                        print(f"  {grade}: {len(books)} books")
                
                # Check for required fields in sample book
                sample_book = None
                for grade, books in books_by_grade.items():
                    if books:
                        sample_book = books[0]
                        break
                
                if sample_book:
                    print(f"\nSample book data quality:")
                    required_fields = ['title', 'assigned_grade', 'isbns']
                    optional_fields = ['best_current_price', 'authors', 'icon_url', 'sources']
                    
                    for field in required_fields:
                        if field in sample_book:
                            print(f"  ✓ {field}: {type(sample_book[field])}")
                        else:
                            print(f"  ✗ {field}: MISSING")
                    
                    for field in optional_fields:
                        if field in sample_book:
                            print(f"  • {field}: {type(sample_book[field])}")

def measure_page_load_time():
    """Measure basic page load time"""
    print("\n" + "=" * 50)
    print("Testing Page Load Performance...")
    print("=" * 50)
    
    url = "http://127.0.0.1:5000/"
    
    times = []
    for i in range(5):
        start_time = time.time()
        response = requests.get(url)
        end_time = time.time()
        
        if response.status_code == 200:
            request_time = (end_time - start_time) * 1000
            times.append(request_time)
            print(f"Page load {i+1}: {request_time:.2f}ms")
        else:
            print(f"Page load {i+1}: FAILED (status {response.status_code})")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"\nAverage page load time: {avg_time:.2f}ms")

def test_data_size():
    """Check the size of data being transferred"""
    print("\n" + "=" * 50)
    print("Testing Data Transfer Size...")
    print("=" * 50)
    
    url = "http://127.0.0.1:5000/api/dashboard-data"
    
    response = requests.get(url)
    if response.status_code == 200:
        data_size = len(response.content)
        print(f"Dashboard API response size: {data_size:,} bytes ({data_size/1024:.2f} KB)")
        
        # Check compression
        headers = {'Accept-Encoding': 'gzip, deflate'}
        compressed_response = requests.get(url, headers=headers)
        if compressed_response.status_code == 200:
            compressed_size = len(compressed_response.content)
            compression_ratio = (1 - compressed_size/data_size) * 100 if data_size > 0 else 0
            print(f"Compressed size: {compressed_size:,} bytes ({compressed_size/1024:.2f} KB)")
            print(f"Compression ratio: {compression_ratio:.1f}%")

if __name__ == "__main__":
    print("BooksFindr Performance Test")
    print("=" * 50)
    print("Make sure the Flask app is running on localhost:5000")
    print("")
    
    test_dashboard_api_performance()
    measure_page_load_time()
    test_data_size()
    
    print("\n" + "=" * 50)
    print("Performance test completed!")
    print("=" * 50)
