#!/usr/bin/env python3
"""
Test script for ChromeDriver session management
"""

import time
from scripts.scraper import initialize_chromedriver_session, get_chrome_driver

def test_chromedriver_session():
    """Test ChromeDriver session initialization and reuse"""
    print("=== Testing ChromeDriver Session Management ===")
    
    # Test 1: Initialize session
    print("\n1. Testing session initialization...")
    result = initialize_chromedriver_session()
    if result:
        print("   ✅ Session initialized successfully")
    else:
        print("   ❌ Session initialization failed")
        return False
    
    # Test 2: Create multiple drivers to test reuse
    print("\n2. Testing driver reuse (creating 3 drivers)...")
    
    times = []
    for i in range(3):
        print(f"   Creating driver {i+1}...")
        start_time = time.time()
        
        try:
            driver = get_chrome_driver()
            driver.get("https://www.google.com")  # Simple page load test
            driver.quit()
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"   Driver {i+1} created and tested in {elapsed:.2f} seconds")
            
        except Exception as e:
            print(f"   ❌ Error with driver {i+1}: {e}")
            return False
    
    # Test 3: Analyze performance
    print(f"\n3. Performance Analysis:")
    print(f"   Average time per driver: {sum(times)/len(times):.2f} seconds")
    print(f"   First driver: {times[0]:.2f}s")
    print(f"   Subsequent drivers: {sum(times[1:])/len(times[1:]):.2f}s average")
    
    if times[0] > sum(times[1:])/len(times[1:]):
        print("   ✅ Performance improved with reuse")
    else:
        print("   ⚠️  No significant performance difference (may be due to caching)")
    
    print("\n✅ All tests completed successfully!")
    return True

if __name__ == "__main__":
    try:
        test_chromedriver_session()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
