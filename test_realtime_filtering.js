// Test script to verify real-time filtering works
// Open browser console and paste this code to test

console.log('Testing Books Findr real-time filtering...');

// Wait for data to load
setTimeout(() => {
    console.log('Testing search and filter functionality...');
    
    // Test 1: Check if global variables exist
    console.log('1. Checking global variables:');
    console.log('   allBooksData:', typeof allBooksData, allBooksData?.length || 0, 'books');
    console.log('   currentFilters:', typeof currentFilters, currentFilters);
    
    // Test 2: Check if filter functions exist
    console.log('2. Checking filter functions:');
    console.log('   setGradeFilter:', typeof setGradeFilter);
    console.log('   setPriceFilter:', typeof setPriceFilter);
    console.log('   toggleFilter:', typeof toggleFilter);
    console.log('   applyFilters:', typeof applyFilters);
    
    // Test 3: Check if DOM elements exist
    console.log('3. Checking DOM elements:');
    const searchInput = document.getElementById('book-search-input');
    const gradeFilter = document.getElementById('grade-filter-text');
    const priceFilter = document.getElementById('price-filter-text');
    console.log('   Search input:', !!searchInput);
    console.log('   Grade filter text:', !!gradeFilter);
    console.log('   Price filter text:', !!priceFilter);
    
    // Test 4: Count total book cards
    const allCards = document.querySelectorAll('.book-card-container');
    const hiddenCards = document.querySelectorAll('.book-card-container.filter-hidden');
    console.log('4. Book cards:');
    console.log('   Total cards:', allCards.length);
    console.log('   Hidden cards:', hiddenCards.length);
    console.log('   Visible cards:', allCards.length - hiddenCards.length);
    
    // Test 5: Try search filter
    if (searchInput && typeof applyFilters === 'function') {
        console.log('5. Testing search filter...');
        const originalValue = searchInput.value;
        
        // Simulate typing in search box
        searchInput.value = 'harry';
        searchInput.dispatchEvent(new Event('input'));
        
        setTimeout(() => {
            const hiddenAfterSearch = document.querySelectorAll('.book-card-container.filter-hidden');
            console.log('   After searching "harry":');
            console.log('   Hidden cards:', hiddenAfterSearch.length);
            console.log('   Visible cards:', allCards.length - hiddenAfterSearch.length);
            
            // Reset search
            searchInput.value = originalValue;
            searchInput.dispatchEvent(new Event('input'));
            
            console.log('✅ Real-time filtering test complete!');
        }, 100);
    }
    
    // Test 6: Try grade filter
    if (typeof setGradeFilter === 'function') {
        console.log('6. Testing grade filter...');
        setTimeout(() => {
            setGradeFilter('1st Grade');
            
            setTimeout(() => {
                const hiddenAfterGrade = document.querySelectorAll('.book-card-container.filter-hidden');
                console.log('   After filtering "1st Grade":');
                console.log('   Hidden cards:', hiddenAfterGrade.length);
                console.log('   Visible cards:', allCards.length - hiddenAfterGrade.length);
                
                // Reset filter
                setGradeFilter('');
                console.log('✅ Grade filter test complete!');
            }, 100);
        }, 500);
    }
    
}, 3000); // Wait 3 seconds for data to load

console.log('Test script loaded. Results will appear in 3 seconds...');
