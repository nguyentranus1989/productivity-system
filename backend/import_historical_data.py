#!/usr/bin/env python3
import csv
import mysql.connector
from datetime import datetime

config = {
    'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    'port': 25060,
    'user': 'doadmin',
    'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    'database': 'productivity_tracker'
}

conn = mysql.connector.connect(**config)
cursor = conn.cursor()

with open('data/historical_orders.csv', 'r') as file:
    header = file.readline()
    count = 0
    
    for line in file:
        parts = line.strip().split('\t')
        if len(parts) >= 2:
            order_date = parts[0].strip()
            line_items = int(parts[1].strip())
            
            date_obj = datetime.strptime(order_date, '%d-%b-%y')
            
            query = """
                INSERT INTO order_predictions 
                (prediction_date, predicted_orders, actual_orders)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                actual_orders = %s,
                predicted_orders = %s
            """
            
            cursor.execute(query, (date_obj.date(), line_items, line_items, line_items, line_items))
            count += 1

conn.commit()
print(f"Imported {count} records")
cursor.close()
conn.close()
