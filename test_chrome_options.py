from scripts.scraper import get_chrome_driver
from scripts.image_downloader import get_chrome_driver_with_images
import time

def test_image_loading(url):
    # Test regular Chrome driver
    print(f"Testing regular Chrome driver with {url} (should have images disabled):")
    driver = get_chrome_driver()
    driver.get(url)
    time.sleep(3)
    image_count_regular = driver.execute_script("return document.images.length")
    image_loaded_regular = driver.execute_script("""
        const images = Array.from(document.images);
        if (images.length === 0) return false;
        return images.some(img => img.complete && img.naturalHeight > 0);
    """)
    print(f"Regular driver image elements: {image_count_regular}")
    print(f"Regular driver has loaded images: {image_loaded_regular}")
    driver.quit()

    # Test image-enabled Chrome driver
    print(f"\nTesting image-specific Chrome driver with {url} (should have images enabled):")
    driver_with_images = get_chrome_driver_with_images()
    driver_with_images.get(url)
    time.sleep(3)
    image_count_enabled = driver_with_images.execute_script("return document.images.length")
    image_loaded_enabled = driver_with_images.execute_script("""
        const images = Array.from(document.images);
        if (images.length === 0) return false;
        return images.some(img => img.complete && img.naturalHeight > 0);
    """)
    print(f"Image-enabled driver image elements: {image_count_enabled}")
    print(f"Image-enabled driver has loaded images: {image_loaded_enabled}")
    driver_with_images.quit()

test_image_loading("https://www.google.com")
print("\nTest completed")
