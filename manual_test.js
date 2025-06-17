// Simple test to manually populate grade containers
console.log('=== Manual Grade Test ===');

// Test data - mimicking what should come from API
const testBookData = {
    title: "Test Book for 4th Grade",
    assigned_grade: "4th Grade",
    isbns: ["1234567890"],
    authors: ["Test Author"],
    best_current_price: 25.99,
    best_price_url: "https://example.com"
};

// Try to find the container
const container = document.getElementById('grade-4-list');
console.log('4th grade container found:', !!container);

if (container) {
    // Manually add a simple test book
    container.innerHTML = `
        <div class="book-card">
            <h5>TEST: ${testBookData.title}</h5>
            <p>This is a test book to verify rendering works</p>
        </div>
    `;
    console.log('Added test content to 4th grade container');
} else {
    console.log('4th grade container not found!');
}

// Check all grade containers
const gradeContainers = [
    'kindergarten-list', 'grade-1-list', 'grade-2-list', 'grade-3-list',
    'grade-4-list', 'grade-5-list', 'grade-6-list'
];

gradeContainers.forEach(id => {
    const el = document.getElementById(id);
    console.log(`${id}: ${el ? 'EXISTS' : 'MISSING'}`);
    if (el) {
        console.log(`  Content length: ${el.innerHTML.length}`);
    }
});
