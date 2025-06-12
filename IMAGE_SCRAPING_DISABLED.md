# Image Scraping Disabled During Price Collection

## Changes Implemented:

1. **Modified Chrome Options in scraper.py:**
   - Added --blink-settings=imagesEnabled=false argument
   - Added 'profile.managed_default_content_settings.images': 2 in experimental options
   - Images are now explicitly disabled during regular price scraping

2. **Modified Chrome Options in scraper_async.py:**
   - Same changes as in scraper.py to maintain consistency
   - Images are disabled in the async implementation as well

3. **Created Dedicated Image-Enabled Chrome Driver:**
   - Added get_chrome_driver_with_images() function in image_downloader.py
   - This function creates a Chrome driver with images explicitly enabled

4. **Updated Image Downloading Functions:**
   - Modified all image downloading functions to use the image-enabled driver
   - Image downloading now works independently from price scraping

## Testing Results:

- Regular driver (price scraping): Images detected but not loaded
- Image-enabled driver: Images detected and successfully loaded

## Outcome:

- Price scraping now runs without loading images, improving performance
- Manual image downloading still works through the 'Get Image' button
- Separation of concerns between price scraping and image downloading
