#!/usr/bin/env python3
"""
Warehouse Order Prediction Model v1
Simple, reliable, learns from historical data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import mysql.connector
import json
import logging

# Set up logging
logging.basicConfig(
    filename='predictions.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
