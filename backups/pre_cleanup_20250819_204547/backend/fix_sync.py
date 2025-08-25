
# Read the file
with open('integrations/connecteam_sync.py', 'r') as f:
    lines = f.readlines()

# Find and replace the problematic section
for i in range(len(lines)):
    if 'already has active shift, skipping' in lines[i]:
        # Replace lines 354-357 (index 353-356)
        new_code = '''            else:
                # Active shift exists, update clock_out if available
                if shift.clock_out:
                    self.db.execute_query(
                        """
                        UPDATE clock_times
                        SET clock_out = %s,
                            is_active = FALSE,
                            total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                            updated_at = NOW()
                        WHERE employee_id = %s
                        AND DATE(clock_in) = CURDATE()
                        AND clock_out IS NULL
                        LIMIT 1
                        """,
                        (shift.clock_out, shift.clock_out, employee_id)
                    )
                    logger.info(f"Updated clock_out for employee {employee_id}")
                else:
                    logger.info(f"Employee {employee_id} still working")
                return True
'''
        # Replace the 4 lines (else block)
        lines[i-2:i+2] = [new_code]
        break

# Write back
with open('integrations/connecteam_sync.py', 'w') as f:
    f.writelines(lines)

print("Fix applied!")
