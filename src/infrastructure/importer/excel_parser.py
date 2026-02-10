"""
Excel Parser - Universal Excel/CSV Import
==========================================

Parses any Excel or CSV file and auto-detects customer columns.
Supports .xlsx, .xls, and .csv formats.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re

import pandas as pd

logger = logging.getLogger(__name__)

# Common column name variations for auto-detection
NAME_PATTERNS = ['name', 'customer', 'client', 'full_name', 'fullname', 'customer_name', 'client_name']
PHONE_PATTERNS = ['phone', 'mobile', 'cell', 'telephone', 'contact', 'number', 'phone_number', 'mobile_number', 'whatsapp']
PRODUCT_PATTERNS = ['product', 'item', 'purchase', 'order', 'service', 'product_name', 'item_name', 'purchased']


class ExcelParser:
    """
    Universal Excel/CSV parser with auto-detection of customer columns.
    
    Usage:
        parser = ExcelParser()
        customers = parser.parse("customers.xlsx")
        # Returns: [{"name": "John", "phone": "923001234567", "product": "iPhone"}, ...]
    """
    
    def __init__(self):
        self.detected_columns: Dict[str, str] = {}
    
    def parse(self, file_path: str, sheet_name: Optional[str] = None) -> Tuple[List[Dict], Dict[str, str]]:
        """
        Parse Excel/CSV file and return customer data.
        
        Args:
            file_path: Path to the file (.xlsx, .xls, .csv)
            sheet_name: Optional sheet name for Excel files
            
        Returns:
            Tuple of (customers list, detected column mapping)
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file based on extension
        ext = path.suffix.lower()
        
        try:
            if ext == '.csv':
                df = pd.read_csv(file_path)
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
            else:
                raise ValueError(f"Unsupported file format: {ext}. Use .xlsx, .xls, or .csv")
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            raise
        
        # Clean column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Auto-detect columns
        name_col = self._find_column(df.columns, NAME_PATTERNS)
        phone_col = self._find_column(df.columns, PHONE_PATTERNS)
        product_col = self._find_column(df.columns, PRODUCT_PATTERNS)
        
        self.detected_columns = {
            'name': name_col,
            'phone': phone_col,
            'product': product_col
        }
        
        logger.info(f"Detected columns: {self.detected_columns}")
        
        if not name_col:
            raise ValueError("Could not detect 'Name' column. Please ensure your file has a column with customer names.")
        
        if not phone_col:
            raise ValueError("Could not detect 'Phone' column. Please ensure your file has a column with phone numbers.")
        
        # Extract and clean data
        customers = []
        
        for _, row in df.iterrows():
            name = str(row.get(name_col, '')).strip()
            phone = self._clean_phone(str(row.get(phone_col, '')))
            product = str(row.get(product_col, '')) if product_col else ''
            
            # Skip empty rows
            if not name or name.lower() == 'nan' or not phone:
                continue
            
            # Clean product
            if product.lower() == 'nan':
                product = ''
            
            customers.append({
                'name': name,
                'phone': phone,
                'product': product.strip()
            })
        
        logger.info(f"Parsed {len(customers)} customers from {file_path}")
        return customers, self.detected_columns
    
    def _find_column(self, columns: pd.Index, patterns: List[str]) -> Optional[str]:
        """Find column matching any of the patterns."""
        for col in columns:
            col_lower = col.lower().strip()
            for pattern in patterns:
                if pattern in col_lower or col_lower in pattern:
                    return col
        return None
    
    def _clean_phone(self, phone: str) -> str:
        """
        Clean and normalize phone number.
        Removes spaces, dashes, + signs, and ensures proper format.
        """
        if not phone or phone.lower() == 'nan':
            return ''
        
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'[^\d+]', '', phone.strip())
        
        # Remove leading + if present
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        
        # Remove leading zeros for international format
        if cleaned.startswith('00'):
            cleaned = cleaned[2:]
        
        return cleaned
    
    def get_sheet_names(self, file_path: str) -> List[str]:
        """Get list of sheet names from Excel file."""
        path = Path(file_path)
        if path.suffix.lower() in ['.xlsx', '.xls']:
            xl = pd.ExcelFile(file_path)
            return xl.sheet_names
        return []


def parse_excel(file_path: str, sheet_name: Optional[str] = None) -> List[Dict]:
    """
    Convenience function to parse Excel/CSV file.
    
    Args:
        file_path: Path to the file
        sheet_name: Optional sheet name
        
    Returns:
        List of customer dictionaries
    """
    parser = ExcelParser()
    customers, _ = parser.parse(file_path, sheet_name)
    return customers


if __name__ == "__main__":
    # Test with sample data
    import sys
    if len(sys.argv) > 1:
        customers = parse_excel(sys.argv[1])
        print(f"Found {len(customers)} customers:")
        for c in customers[:5]:
            print(f"  - {c['name']}: {c['phone']} ({c['product']})")
