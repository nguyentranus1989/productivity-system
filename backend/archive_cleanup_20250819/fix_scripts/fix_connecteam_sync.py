#!/usr/bin/env python3
import re

# Read the file
with open('integrations/connecteam_sync.py', 'r') as f:
    content = f.read()

# Fix the duplicate line and undefined variable issue in _sync_clock_time
old_pattern = r"""    def _sync_clock_time\(self, employee_id: int, shift: ConnecteamShift\) -> bool:
        """Sync clock time record from Connecteam shift\. Returns True if updated, False if created\."""
        
        # Convert times for comparison
        clock_in_utc = shift\.clock_in  # Already UTC from Connecteam
        clock_in_utc = shift\.clock_in  # Already UTC from Connecteam
        clock_in_central = self\.convert_to_central\(clock_in_utc\)"""

new_pattern = """    def _sync_clock_time(self, employee_id: int, shift: ConnecteamShift) -> bool:
        """Sync clock time record from Connecteam shift. Returns True if updated, False if created."""
        
        # Convert times for comparison
        clock_in_utc = shift.clock_in  # Already UTC from Connecteam
        clock_out_utc = shift.clock_out if shift.clock_out else None  # Already UTC from Connecteam
        clock_in_central = self.convert_to_central(clock_in_utc)
        clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None"""

# Replace using regex to handle the docstring properly
content = re.sub(
    r'def _sync_clock_time\(self, employee_id: int, shift: ConnecteamShift\) -> bool:.*?clock_in_central = self\.convert_to_central\(clock_in_utc\)',
    '''def _sync_clock_time(self, employee_id: int, shift: ConnecteamShift) -> bool:
        """Sync clock time record from Connecteam shift. Returns True if updated, False if created."""
        
        # Convert times for comparison
        clock_in_utc = shift.clock_in  # Already UTC from Connecteam
        clock_out_utc = shift.clock_out if shift.clock_out else None  # Already UTC from Connecteam
        clock_in_central = self.convert_to_central(clock_in_utc)
        clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None''',
    content,
    flags=re.DOTALL
)

# Write back
with open('integrations/connecteam_sync.py', 'w') as f:
    f.write(content)

print("Fixed connecteam_sync.py - removed duplicate line and added clock_out definitions")
