    getCentralDate() {
        // Get current time
        const now = new Date();
        
        // Calculate Central Time offset (UTC-6 for CST, UTC-5 for CDT)
        // During August, it's CDT (UTC-5)
        const utcTime = now.getTime() + (now.getTimezoneOffset() * 60000);
        const centralTime = new Date(utcTime + (3600000 * -5)); // UTC-5 for CDT
        
        // Format as YYYY-MM-DD
        const year = centralTime.getFullYear();
        const month = String(centralTime.getMonth() + 1).padStart(2, '0');
        const day = String(centralTime.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    }
