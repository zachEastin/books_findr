# Book Image Functionality Documentation

## Overview

This document provides comprehensive information about the book cover image functionality implemented in the Book Price Tracker application. The system automatically downloads and displays book cover images from tracked websites.

## Features

### 1. Image Display in ISBN Cards
- **Location**: Main dashboard (`/`) ISBN cards
- **Size**: 80x120px image containers
- **Behavior**: 
  - Shows book cover when available
  - Displays placeholder icon with "No Image" text when unavailable
  - Shows download buttons when no image exists but price data is available

### 2. Image Download System
- **API Endpoints**:
  - `GET /api/images/<isbn>` - Check existing images for an ISBN
  - `POST /api/images/<isbn>/<source>` - Download image from specific source
  - `POST /api/images/cleanup` - Clean up old image files

- **Supported Sources**:
  - **ChristianBook** (`christianbook`) 
  - **RainbowResource** (`rainbowresource`)
  - **AbeBooks** (`abebooks`)

### 3. Admin Interface Integration
- **Location**: Admin page (`/admin`)
- **Features**:
  - Image placeholders in ISBN list
  - Dropdown download buttons for each source
  - Real-time image loading and display

## Technical Implementation

### File Structure
```
static/
  images/
    books/
      {isbn}_{source}_{hash}.jpg
```

### Image Naming Convention
- Format: `{isbn}_{source}_{hash}.jpg`
- Example: `9781593173357_bookscouter_73cb0884.jpg`
- Hash: First 8 characters of MD5 hash of `{isbn}_{source}`

### Dependencies
- **Required Packages**:
  - `aiohttp` - Async HTTP client for image downloads
  - `selenium` - Web scraping for image extraction
  - `pandas` - Data processing (with string ISBN handling)

## Source-Specific Image Extraction

### BookScouter.com
**Target Element Path**:
```
section.BookDetailsSection_* div.ContentWrapper_* div.BookDetailsContainer_* 
div.BookDetailsWrapper_* div.BookDetailsContentWrapper_* 
div.BookDetailsPreviewShadow_* div[aria-label="Open book image"] 
div.BookAssetWrapper_* span img
```

**Implementation Notes**:
- Uses multiple CSS selectors as fallbacks
- Handles dynamically generated class names
- Extracts image URL from `src` attribute

### ChristianBook.com
**Target Element Path**:
```
div#container div#main-frame div#page-body div#main-content 
div.product-main-content div.CBD-ProductImage div.CBD-ProductImageContainer 
div.CBD-ProductDetailImageWrap div[data-cbd-modalidentifier="slideshow-lightbox-Modal"] img
```

**Implementation Notes**:
- Searches product pages for main product images
- Uses stable CSS selectors based on CBD naming convention

### RainbowResource.com
**Target Element Path**:
```
div.page-wrapper main#maincontent div.columns div.column.main div#results 
div.hawk div.hawk__body div.hawk-results div.hawk-results__listing_type__grid 
div.hawk-results__item a.hawk-item-clickable-area div.hawk-results__item-image img
```

**Price Element Path**:
```
div.hawk-results__item div.hawk-results__priceBox span.special-price
```

**Implementation Notes**:
- **Special Logic**: Selects image from the **lowest-priced** item
- Compares prices across all search results
- Uses regex to extract numeric price values

## API Response Formats

### GET /api/images/{isbn}
```json
{
  "isbn": "9781593173357",
  "images": {
    "bookscouter": {
      "exists": true,
      "path": "static/images/books/9781593173357_bookscouter_73cb0884.jpg",
      "url": "/static/images/books/9781593173357_bookscouter_73cb0884.jpg",
      "size": 15432
    },
    "christianbook": {
      "exists": false
    },
    "rainbowresource": {
      "exists": false
    }
  }
}
```

### POST /api/images/{isbn}/{source}
**Success Response**:
```json
{
  "message": "Image downloaded successfully for 9781593173357 from bookscouter",
  "result": {
    "success": true,
    "isbn": "9781593173357",
    "source": "bookscouter",
    "image_path": "static/images/books/9781593173357_bookscouter_73cb0884.jpg",
    "image_url": "https://example.com/image.jpg"
  }
}
```

**Error Response**:
```json
{
  "error": "Failed to download image: Invalid image format",
  "result": {
    "success": false,
    "isbn": "9781593173357",
    "source": "bookscouter",
    "error": "Invalid image format"
  }
}
```

## JavaScript Functions

### Frontend Image Loading
```javascript
// Load book image for specific ISBN
async function loadBookImage(isbn, pricesData)

// Download book image for specific ISBN and source  
async function downloadBookImage(isbn, source)

// Admin: Load image for specific ISBN
async function loadImageForISBN(isbn)

// Admin: Download image for specific ISBN and source
async function downloadImage(isbn, source)
```

### UI Integration
- **Materialize Dropdowns**: Used for source selection
- **Toast Notifications**: Provide user feedback during downloads
- **Dynamic Content**: Images and buttons update without page refresh

## Data Requirements

### Price Data Prerequisites
To download images, the system requires:
1. **Valid Price Data**: ISBN must exist in `prices.csv`
2. **URL Field**: Source must have a non-empty URL
3. **Success Status**: Price scraping must have been successful

### Data Type Handling
**Critical**: ISBNs must be loaded as strings in pandas:
```python
df = pd.read_csv(PRICES_CSV, dtype={'isbn': str})
```

**Why**: Prevents ISBN conversion to int64, which breaks filtering.

## Image Validation

### Supported Formats
- **JPEG**: Multiple header variations (`\xff\xd8\xff\xe0`, `\xff\xd8\xff\xe1`, etc.)
- **PNG**: Standard header (`\x89PNG\r\n\x1a\n`)
- **GIF**: Both variants (`GIF87a`, `GIF89a`)
- **WebP**: RIFF container format

### Validation Logic
```python
if len(content) > 1000 and (
    content[:4] in [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xfe'] or
    content[:3] == b'\xff\xd8\xff' or
    content[:8] == b'\x89PNG\r\n\x1a\n' or
    content[:6] in [b'GIF87a', b'GIF89a'] or
    content[:4] == b'RIFF' and content[8:12] == b'WEBP'
):
```

## Common Issues & Solutions

### 1. ISBN Data Type Problems
**Problem**: ISBNs converted to integers, breaking string comparisons
**Solution**: Use `dtype={'isbn': str}` when loading CSV

### 2. Missing Dependencies
**Problem**: `ModuleNotFoundError: No module named 'aiohttp'`
**Solution**: `pip install aiohttp`

### 3. Image Format Validation Failures
**Problem**: Valid images rejected due to strict validation
**Solution**: Enhanced validation to support multiple format variations

### 4. Dynamic CSS Classes
**Problem**: Websites use randomly generated CSS class names
**Solution**: Use partial class matching and multiple fallback selectors

### 5. Proxy/CDN Image URLs
**Problem**: NextJS proxy URLs not downloading properly
**Solution**: Enhanced HTTP client handling and format validation

## Testing

### Manual Testing Commands
```powershell
# Check existing images
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/images/9781593173357" -Method GET

# Download image from specific source
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/images/9781593173357/bookscouter" -Method POST

# Verify file creation
Get-ChildItem "static/images/books/"
```

### Test Data
The system has been tested with:
- ISBN: `9781593173357` (Egermeier's Bible Story Book)
- All three sources: BookScouter, ChristianBook, RainbowResource
- Multiple image formats and URL types

## Future Enhancements

### Potential Improvements
1. **Image Optimization**: Resize images to standard dimensions
2. **Bulk Download**: Download all missing images at once
3. **Image Caching**: Cache images with expiration dates
4. **Alternative Sources**: Add support for additional book retailers
5. **Image Quality**: Prefer higher resolution images when available
6. **Error Recovery**: Retry failed downloads with exponential backoff

### Monitoring
- **Log Files**: Check `logs/scraper.log` for image download activity
- **Storage**: Monitor `static/images/books/` directory size
- **Performance**: Track download success rates by source

## Security Considerations

### File Storage
- Images stored in `static/` directory (publicly accessible)
- Unique filenames prevent conflicts and unauthorized access
- File extension locked to `.jpg` for consistency

### Input Validation
- ISBN format validation in API endpoints
- Source name validation against allowed list
- URL validation before download attempts

### Rate Limiting
Consider implementing rate limiting for image download endpoints to prevent abuse.

---

**Last Updated**: June 10, 2025
**Version**: 1.0
**Status**: Fully Implemented and Tested
