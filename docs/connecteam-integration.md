# Connecteam Integration Guide

## Overview
Integration with Connecteam for time clock data and employee management.

## API Configuration

### Required Environment Variables
```
CONNECTEAM_API_KEY=your_api_key
CONNECTEAM_CLOCK_ID=your_clock_id
ENABLE_AUTO_SYNC=true
```

### API Endpoints Used
| Endpoint | Purpose |
|----------|---------|
| `/users` | Employee data |
| `/timeclock/punches` | Clock in/out data |
| `/shifts` | Shift information |

## Employee Mapping

### Smart Mapping Algorithm
The system uses Dice coefficient on bigrams for name similarity matching.

#### How it Works
1. Extracts bigrams (2-character sequences) from names
2. Calculates intersection/union ratio
3. Returns similarity score between 0 and 1

#### Example
```
"John Smith" → bigrams: ["jo", "oh", "hn", "n ", " s", "sm", "mi", "it", "th"]
"John Smyth" → bigrams: ["jo", "oh", "hn", "n ", " s", "sm", "my", "yt", "th"]
Similarity: ~0.72 (HIGH CONFIDENCE)
```

### Confidence Levels
| Level | Score Range | Visual |
|-------|-------------|--------|
| HIGH CONFIDENCE | ≥50% | Green badge |
| POSSIBLE MATCH | 20-50% | Yellow badge |
| BEST AVAILABLE | <20% | Gray badge |

### Verification Workflow
1. System shows best match with confidence level
2. User reviews the suggestion
3. User confirms or manually selects correct match
4. Mapping saved to `employee_podfactory_mapping_v2` table

## Database Schema

### employee_podfactory_mapping_v2
```sql
CREATE TABLE employee_podfactory_mapping_v2 (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    podfactory_email VARCHAR(255),
    podfactory_name VARCHAR(255),
    similarity_score DECIMAL(4,3),
    confidence_level ENUM('HIGH', 'MEDIUM', 'LOW'),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    verified_at TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

### connecteam_shifts
```sql
CREATE TABLE connecteam_shifts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT,
    connecteam_user_id VARCHAR(50),
    clock_in DATETIME,
    clock_out DATETIME,
    total_hours DECIMAL(5,2),
    shift_date DATE,
    synced_at TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

## Sync Schedule
| Job | Frequency | Purpose |
|-----|-----------|---------|
| Shifts sync | Every 5 min | Sync current day clock data |
| Employee sync | Daily 2 AM | Full employee list refresh |

## API Response Examples

### Get Users
```json
{
  "data": [
    {
      "id": "12345",
      "firstName": "John",
      "lastName": "Smith",
      "email": "john.smith@company.com"
    }
  ]
}
```

### Get Punches
```json
{
  "data": [
    {
      "userId": "12345",
      "punchIn": "2025-12-09T08:00:00Z",
      "punchOut": "2025-12-09T16:30:00Z",
      "totalHours": 8.5
    }
  ]
}
```

## Pay Rate Integration (Future)

### Note
Connecteam does not have a direct pay rate API endpoint. Pay rates can be stored using User Custom Fields.

### User Custom Fields API
- Requires Expert plan or higher
- Field types: str, date, directManager, dropdown, number
- Can create custom "pay_rate" field

### Implementation Steps
1. Create custom field for pay rate via Connecteam admin
2. Use Users API to read/write custom field values
3. Store locally for payroll calculations

## Troubleshooting

### Common Issues
| Issue | Cause | Solution |
|-------|-------|----------|
| No matches found | Name format differences | Check for nickname/full name variations |
| Low confidence matches | Special characters | Normalize names before comparison |
| Sync failures | API rate limits | Check Connecteam API quota |

### Logs Location
```
backend/logs/productivity_tracker.log
```

### Debug Commands
```python
# Check sync status
curl http://localhost:5000/api/connecteam/status

# Trigger manual sync
curl http://localhost:5000/api/connecteam/sync
```
