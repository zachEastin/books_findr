#!/usr/bin/env python3
"""
Simple demonstration of the async scraper functionality
"""

import asyncio
import time
from scripts.scraper import scrape_all_sources_async, scrape_multiple_isbns


async def demo_single_isbn():
    """Demonstrate async scraping for a single ISBN"""
    print("🔍 Demo: Single ISBN Async Scraping")
    print("-" * 40)

    isbn = "9780134685991"  # Effective Java
    print(f"Scraping ISBN: {isbn}")

    start_time = time.time()
    results = await scrape_all_sources_async(isbn)
    end_time = time.time()

    print(f"\n⏱️  Completed in: {end_time - start_time:.2f} seconds")
    print(f"📊 Results from {len(results)} sources:")

    for result in results:
        status = "✅" if result["success"] else "❌"
        if result["success"]:
            print(f"   {status} {result['source']}: ${result['price']:.2f}")
        else:
            print(f"   {status} {result['source']}: {result['notes']}")


async def demo_multiple_isbns():
    """Demonstrate async scraping for multiple ISBNs"""
    print("\n\n📚 Demo: Multiple ISBN Concurrent Scraping")
    print("-" * 45)

    isbns = [
        "9780134685991",  # Effective Java
        "9780132350884",  # Clean Code
        "9780201633610",  # Design Patterns
    ]

    print(f"Scraping {len(isbns)} ISBNs concurrently...")
    for i, isbn in enumerate(isbns, 1):
        print(f"   {i}. {isbn}")

    start_time = time.time()
    results = await scrape_multiple_isbns(isbns, batch_size=2)
    end_time = time.time()

    print(f"\n⏱️  Completed in: {end_time - start_time:.2f} seconds")
    print(f"📊 Total results: {len(results)} from {len(isbns)} ISBNs")

    # Group results by ISBN
    isbn_results = {}
    for result in results:
        isbn = result["isbn"]
        if isbn not in isbn_results:
            isbn_results[isbn] = []
        isbn_results[isbn].append(result)

    # Display results by ISBN
    for isbn, isbn_result_list in isbn_results.items():
        print(f"\n📖 ISBN {isbn}:")
        for result in isbn_result_list:
            status = "✅" if result["success"] else "❌"
            if result["success"]:
                print(f"   {status} {result['source']}: ${result['price']:.2f}")
            else:
                print(f"   {status} {result['source']}: {result['notes']}")


async def demo_performance_comparison():
    """Demonstrate the performance improvement of async vs sequential"""
    print("\n\n⚡ Demo: Performance Comparison")
    print("-" * 35)

    isbn = "9780134685991"  # Effective Java
    print(f"Performance test with ISBN: {isbn}")

    print("\n🐌 Theoretical Sequential Time:")
    print("   - BookScouter: ~8 seconds")
    print("   - Christianbook: ~8 seconds")
    print("   - RainbowResource: ~8 seconds")
    print("   - Total: ~24 seconds")

    print("\n🚀 Actual Concurrent Execution:")
    start_time = time.time()
    results = await scrape_all_sources_async(isbn)
    actual_time = time.time() - start_time

    print(f"   - All sources simultaneously: {actual_time:.2f} seconds")

    theoretical_sequential = 24  # 3 sources × ~8 seconds each
    if actual_time < theoretical_sequential:
        speedup = theoretical_sequential / actual_time
        savings = theoretical_sequential - actual_time
        print(f"\n💨 Performance Improvement:")
        print(f"   - Speedup: {speedup:.1f}x faster")
        print(f"   - Time saved: {savings:.1f} seconds")
    else:
        print(f"\n⚠️  Concurrent execution took longer than expected")
        print(f"   This might be due to network conditions or rate limiting")


async def main():
    """Run all demo functions"""
    print("🚀 Async Book Scraper Demo")
    print("=" * 50)

    try:
        await demo_single_isbn()
        await demo_multiple_isbns()
        await demo_performance_comparison()

        print("\n\n✨ Demo completed successfully!")
        print("\nKey takeaways:")
        print("   • Async scraping enables concurrent execution")
        print("   • Multiple sources scraped simultaneously")
        print("   • Significant performance improvements")
        print("   • Graceful error handling for failed sources")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
