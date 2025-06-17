// Debug script to check what's loaded in the browser
console.log('=== Grade Debug Info ===');

// Check if the dashboard data is loaded
if (typeof window.dashboardData !== 'undefined') {
    console.log('Dashboard data exists');
    const grades = window.dashboardData.books_by_grade;
    console.log('Grades available:', Object.keys(grades));
    
    for (let grade of ['4th Grade', '5th Grade', '6th Grade']) {
        if (grades[grade]) {
            console.log(`${grade}: ${grades[grade].length} books`);
            // Check if the container exists
            const container = document.getElementById('grade-4-list'.replace('4', grade.charAt(0)));
            console.log(`Container for ${grade} exists:`, !!container);
            if (container) {
                console.log(`Container innerHTML length: ${container.innerHTML.length}`);
            }
        } else {
            console.log(`${grade}: NOT FOUND in data`);
        }
    }
} else {
    console.log('Dashboard data not loaded yet');
}

// Check if containers exist
const containers = ['grade-4-list', 'grade-5-list', 'grade-6-list'];
containers.forEach(id => {
    const el = document.getElementById(id);
    console.log(`${id} exists:`, !!el);
    if (el) {
        console.log(`${id} innerHTML:`, el.innerHTML.substring(0, 100));
    }
});
