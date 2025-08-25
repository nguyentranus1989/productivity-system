#!/usr/bin/env python3
"""
Non-interactive reconciliation for cron job
Uses the FIXED auto_reconciliation.py
"""

import sys
sys.path.append('/var/www/productivity-system/backend')

from auto_reconciliation import AutoFixReconciliation
import logging

# Setup logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/connecteam_reconciliation.log'),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    print("=" * 60)
    print("AUTOMATED DAILY RECONCILIATION")
    print("=" * 60)
    
    reconciler = AutoFixReconciliation()
    reconciler.auto_reconcile(days_back=7)
    
    print("Reconciliation complete!")
