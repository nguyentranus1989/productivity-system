#!/usr/bin/env python3
"""
Non-interactive reconciliation for cron job
Runs 7-day reconciliation automatically
"""

import sys
sys.path.append('/var/www/productivity-system/backend')

from connecteam_reconciliation import ConnecteamReconciliation
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
    reconciler = ConnecteamReconciliation()
    
    print("=" * 60)
    print("AUTOMATED DAILY RECONCILIATION")
    print("=" * 60)
    
    # Show current status
    reconciler.show_current_status()
    
    # Run 7-day reconciliation
    reconciler.reconcile_last_n_days(7)
    
    # Show final status
    print("\nFinal status after reconciliation:")
    reconciler.show_current_status()
