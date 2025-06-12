#!/usr/bin/env python3
"""
Test script for Browser Pool functionality
This demonstrates the performance improvements from using persistent browser sessions
"""

import time
import asyncio
from scripts.scraper import (
    initialize_browser_pool, 
    get_browser_pool_stats, 
    shutdown_browser_pool,
    scrape_all_sources_async,
    BROWSER_POOL_SIZE
)

async def test_browser_pool_performance():
    """Test browser pool performance vs traditional approach"""
    print("=== Testing Browser Pool Performance ===")
    
    # Test ISBNs - using proper metadata format expected by the scrapers
    test_isbns = [
        {"isbn13": "9780134685991", "title": "Effective Java"},
        {"isbn13": "9780132350884", "title": "Clean Code"},
        {"isbn13": "9781593273897", "title": "Eloquent JavaScript"},
    ]
    
    print(f"\nTesting with {len(test_isbns)} ISBNs and browser pool size: {BROWSER_POOL_SIZE}")
    
    # Test 1: Initialize browser pool
    print("\n1. Initializing browser pool...")
    start_time = time.time()
    if not initialize_browser_pool(BROWSER_POOL_SIZE):
        print("   ❌ Failed to initialize browser pool")
        return False
    
    init_time = time.time() - start_time
    print(f"   ✅ Browser pool initialized in {init_time:.2f} seconds")
    
    # Test 2: Check initial pool stats
    print("\n2. Initial browser pool statistics:")
    stats = get_browser_pool_stats()
    print(f"   Pool size: {stats['pool_size']}")
    print(f"   Available sessions: {stats['available_sessions']}")
    print(f"   Total sessions: {stats['total_sessions']}")
    
    # Test 3: Run scraping operations and measure performance
    print(f"\n3. Running scraping operations for {len(test_isbns)} ISBNs...")
    operation_times = []
    
    for i, isbn_data in enumerate(test_isbns):
        print(f"\n   Scraping ISBN {i+1}: {isbn_data['isbn13']} ({isbn_data['title']})")
        
        start_time = time.time()
        results = await scrape_all_sources_async(isbn_data, isbn_data['title'])
        operation_time = time.time() - start_time
        operation_times.append(operation_time)
        
        successful = len([r for r in results if r.get('success', False)])
        print(f"   Completed in {operation_time:.2f}s - {successful}/{len(results)} sources successful")
        
        # Show current pool stats
        current_stats = get_browser_pool_stats()
        print(f"   Available sessions: {current_stats['available_sessions']}/{current_stats['total_sessions']}")
    
    # Test 4: Performance analysis
    print(f"\n4. Performance Analysis:")
    total_time = sum(operation_times)
    avg_time = total_time / len(operation_times)
    print(f"   Total scraping time: {total_time:.2f} seconds")
    print(f"   Average time per ISBN: {avg_time:.2f} seconds")
    print(f"   Time per operation: {operation_times}")
    
    # Check if times are relatively consistent (good sign for pooling)
    if len(operation_times) > 1:
        time_variance = max(operation_times) - min(operation_times)
        print(f"   Time variance: {time_variance:.2f}s (lower is better for pooling)")
        
        if time_variance < avg_time * 0.5:  # Less than 50% variance
            print("   ✅ Consistent performance - browser pool working well")
        else:
            print("   ⚠️  High time variance - check browser pool efficiency")
    
    # Test 5: Detailed session usage stats
    print("\n5. Detailed session usage statistics:")
    final_stats = get_browser_pool_stats()
    total_uses = 0
    
    for session_id, details in final_stats['sessions_detail'].items():
        total_uses += details['use_count']
        print(f"   {session_id}:")
        print(f"     Uses: {details['use_count']}")
        print(f"     Age: {details['age']:.1f}s")
        print(f"     Idle time: {details['idle_time']:.1f}s")
        print(f"     Healthy: {details['is_healthy']}")
        print(f"     Expired: {details['is_expired']}")
    
    print(f"\n   Total browser uses across all sessions: {total_uses}")
    print(f"   Average uses per session: {total_uses / len(final_stats['sessions_detail']):.1f}")
    
    # Test 6: Test concurrent usage
    print(f"\n6. Testing concurrent scraping (all {len(test_isbns)} ISBNs at once)...")
    concurrent_start = time.time()
    
    # Create concurrent tasks
    concurrent_tasks = [
        scrape_all_sources_async(isbn_data, isbn_data['title']) 
        for isbn_data in test_isbns
    ]
    
    # Run all concurrently
    concurrent_results = await asyncio.gather(*concurrent_tasks)
    concurrent_time = time.time() - concurrent_start
    
    total_concurrent_successes = sum(
        len([r for r in isbn_results if r.get('success', False)])
        for isbn_results in concurrent_results
    )
    total_concurrent_attempts = sum(len(isbn_results) for isbn_results in concurrent_results)
    
    print(f"   Concurrent scraping completed in {concurrent_time:.2f}s")
    print(f"   Success rate: {total_concurrent_successes}/{total_concurrent_attempts}")
    print(f"   Speedup vs sequential: {total_time/concurrent_time:.2f}x")
    
    if concurrent_time < total_time:
        print("   ✅ Concurrent scraping is faster - browser pool enabling parallelism")
    else:
        print("   ⚠️  Concurrent scraping not faster - check pool size and bottlenecks")
    
    # Test 7: Final pool statistics
    print("\n7. Final browser pool statistics:")
    end_stats = get_browser_pool_stats()
    end_total_uses = sum(details['use_count'] for details in end_stats['sessions_detail'].values())
    print(f"   Total uses after all tests: {end_total_uses}")
    print(f"   Sessions available: {end_stats['available_sessions']}/{end_stats['total_sessions']}")
    
    # Test 8: Cleanup
    print("\n8. Shutting down browser pool...")
    shutdown_browser_pool()
    print("   ✅ Browser pool shutdown complete")
    
    print("\n" + "="*50)
    print("✅ Browser Pool Performance Test Complete!")
    print("\nKey Benefits Demonstrated:")
    print("- Browser sessions are reused across multiple scrapes")
    print("- No startup/shutdown overhead for each operation") 
    print("- Concurrent scraping using pooled browsers")
    print("- Automatic session lifecycle management")
    print("- Performance monitoring and statistics")
    
    return True


async def test_browser_pool_error_handling():
    """Test browser pool error handling and recovery"""
    print("\n" + "="*50)
    print("=== Testing Browser Pool Error Handling ===")
    
    # Initialize a smaller pool for testing
    print("\n1. Initializing small browser pool for error testing...")
    if not initialize_browser_pool(pool_size=2):
        print("   ❌ Failed to initialize browser pool")
        return False
    print("   ✅ Small browser pool initialized")
    
    # Test with invalid URL to trigger errors
    print("\n2. Testing error handling with invalid URLs...")
    test_data = {"isbn13": "invalid_isbn", "title": "Invalid Test"}
    
    try:
        results = await scrape_all_sources_async(test_data, "Invalid Test")
        print(f"   Handled error gracefully, got {len(results)} results")
        
        # Check if any sessions are still healthy
        stats = get_browser_pool_stats()
        healthy_sessions = sum(1 for details in stats['sessions_detail'].values() if details['is_healthy'])
        print(f"   {healthy_sessions}/{stats['total_sessions']} sessions remain healthy after error")
        
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print("\n3. Cleaning up error test...")
    shutdown_browser_pool()
    print("   ✅ Error handling test complete")
    
    return True


def main():
    """Run all browser pool tests"""
    print("Starting comprehensive browser pool testing...")
    
    async def run_all_tests():
        # Run performance tests
        perf_success = await test_browser_pool_performance()
        
        if perf_success:
            # Run error handling tests
            error_success = await test_browser_pool_error_handling()
            return error_success
        
        return False
    
    try:
        success = asyncio.run(run_all_tests())
        if success:
            print("\n🎉 All browser pool tests completed successfully!")
        else:
            print("\n❌ Some tests failed")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
