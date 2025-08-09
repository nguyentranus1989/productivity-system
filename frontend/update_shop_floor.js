// Find and replace the leaderboard display section
const fs = require('fs');
const content = fs.readFileSync('shop-floor.html', 'utf8');

// Replace slice(0, 5) with no slice - show all
const updated = content.replace(
    /leaderboard\.slice\(0, \d+\)/g,
    'leaderboard'
);

fs.writeFileSync('shop-floor.html', updated);
console.log('Updated shop floor to show ALL clocked-in employees');
