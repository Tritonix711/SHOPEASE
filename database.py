import sqlite3
import os
import shutil
import logging
from datetime import datetime, date
from typing import Tuple, Optional, List, Dict

"""
database.py - Handles database operations for ShopEase, an inventory management app.
Uses SQLite for storage, with dynamic path handling for local development (Windows) 
and Hugging Face Spaces deployment. Includes indexing, data pruning, and backup features
for scalability and reliability. Supports product names and units in English and Bengali (e.g., "Sugar" or "চিনি").
"""

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Determine the database path dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Get the directory of this file
DATA_DIR = os.path.join(BASE_DIR, 'data')              # Local 'data' folder path
DB_PATH = os.path.join(DATA_DIR, 'inventory.db')       # Local database path: ShopEase/data/inventory.db

# Create the 'data' directory if it doesn’t exist (for local use)
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    logger.info(f"Created data directory at {DATA_DIR}")

# Use /data/inventory.db for Hugging Face Spaces, otherwise use local path
if os.path.exists('/data'):  # Check if running on Hugging Face Spaces
    DB_PATH = '/data/inventory.db'
    logger.info("Using Hugging Face Spaces database path: /data/inventory.db")
else:
    logger.info(f"Using local database path: {DB_PATH}")

# Connect to the SQLite database
try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    logger.info("Successfully connected to the database")
except sqlite3.Error as e:
    logger.error(f"Database connection failed: {e}")
    raise

# Create tables and indexes if they don’t exist
try:
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, unit TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  product_id INTEGER,
                  quantity REAL,
                  price REAL,
                  date TEXT,
                  FOREIGN KEY(product_id) REFERENCES products(id))''')

    # Add index for faster queries on transactions by product_id and date
    c.execute("CREATE INDEX IF NOT EXISTS idx_transactions_product_date ON transactions(product_id, date)")
    conn.commit()
    logger.info("Tables and indexes created/verified successfully")
except sqlite3.Error as e:
    logger.error(f"Error creating tables or indexes: {e}")
    raise

# Database Functions

def add_product(name: str, unit: str) -> None:
    """
    Add a new product to the products table.
    Args:
        name (str): Name of the product (e.g., "Sugar" or "চিনি").
        unit (str): Unit of measurement (e.g., "kg" or "কিলোগ্রাম").
    """
    try:
        c.execute("INSERT INTO products (name, unit) VALUES (?, ?)", (name, unit))
        conn.commit()
        logger.info(f"Added product: {name} with unit {unit}")
    except sqlite3.Error as e:
        logger.error(f"Error adding product {name}: {e}")
        raise

def add_transaction(product_id: int, quantity: float, price: Optional[float] = None) -> None:
    """
    Add a transaction (purchase or sale) to the transactions table.
    Args:
        product_id (int): ID of the product.
        quantity (float): Quantity (positive for purchases, negative for sales).
        price (float, optional): Price per unit for purchases (None for sales).
    """
    try:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO transactions (product_id, quantity, price, date) VALUES (?, ?, ?, ?)",
                  (product_id, quantity, price, date))
        conn.commit()
        logger.info(f"Added transaction for product_id {product_id}: {quantity} at {price} INR on {date}")
    except sqlite3.Error as e:
        logger.error(f"Error adding transaction for product_id {product_id}: {e}")
        raise

def get_current_quantity(product_id: int) -> float:
    """
    Calculate the current quantity of a product by summing all transactions.
    Args:
        product_id (int): ID of the product.
    Returns:
        float: Current quantity, or 0 if no transactions exist.
    """
    try:
        c.execute("SELECT SUM(quantity) FROM transactions WHERE product_id = ?", (product_id,))
        result = c.fetchone()[0]
        return result if result is not None else 0
    except sqlite3.Error as e:
        logger.error(f"Error getting current quantity for product_id {product_id}: {e}")
        raise

def get_last_price_before_date(product_id: int, target_date: Optional[str] = None) -> Optional[float]:
    """
    Get the last purchase price of a product on or before a specific date.
    Args:
        product_id (int): ID of the product.
        target_date (str, optional): Date in "YYYY-MM-DD HH:MM:SS" format, defaults to now.
    Returns:
        float: Last price, or None if no purchase exists.
    """
    try:
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT price FROM transactions WHERE product_id = ? AND quantity > 0 AND price IS NOT NULL AND date <= ? ORDER BY date DESC LIMIT 1",
                  (product_id, target_date))
        result = c.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Error getting last price for product_id {product_id} on {target_date}: {e}")
        raise

def get_last_purchase_date(product_id: int, target_date: Optional[str] = None) -> Optional[str]:
    """
    Get the date of the last purchase for a product on or before a specific date.
    Args:
        product_id (int): ID of the product.
        target_date (str, optional): Date in "YYYY-MM-DD HH:MM:SS" format, defaults to now.
    Returns:
        str: Last purchase date in "YYYY-MM-DD HH:MM:SS" format, or None if no purchase exists.
    """
    try:
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT date FROM transactions WHERE product_id = ? AND quantity > 0 AND date <= ? ORDER BY date DESC LIMIT 1",
                  (product_id, target_date))
        result = c.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Error getting last purchase date for product_id {product_id} on {target_date}: {e}")
        raise

def get_purchase_history(product_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Tuple[str, float, float]]:
    """
    Retrieve the complete purchase history for a product within a specified date range.
    Args:
        product_id (int): ID of the product.
        start_date (date, optional): Start date for the history (defaults to earliest transaction).
        end_date (date, optional): End date for the history (defaults to today).
    Returns:
        list: List of tuples (date, quantity, price) for all purchases, sorted by date.
    """
    try:
        query = "SELECT date, quantity, price FROM transactions WHERE product_id = ? AND quantity > 0"
        params = [product_id]
        
        if start_date:
            query += " AND date >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND date <= ?"
            params.append(f"{end_date} 23:59:59")
        
        query += " ORDER BY date ASC"
        c.execute(query, params)
        return c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving purchase history for product_id {product_id}: {e}")
        raise

def get_all_products() -> List[Tuple[int, str, str]]:
    """
    Retrieve all products from the products table.
    Returns:
        list: List of tuples (id, name, unit) for all products.
    """
    try:
        c.execute("SELECT id, name, unit FROM products")
        return c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving all products: {e}")
        raise

def get_product_id(name: str) -> Optional[int]:
    """
    Get the ID of a product by its name.
    Args:
        name (str): Name of the product (e.g., "Sugar" or "চিনি").
    Returns:
        int: Product ID, or None if not found.
    """
    try:
        c.execute("SELECT id FROM products WHERE name = ?", (name,))
        result = c.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Error getting ID for product {name}: {e}")
        raise

def get_transactions_by_date(selected_date: date) -> List[Tuple[int, str, float, float, str, str]]:
    """
    Retrieve all purchase transactions for a specific date.
    Args:
        selected_date (date): Date object (e.g., from datetime.date).
    Returns:
        list: List of tuples (transaction_id, product_name, quantity, price, unit, date) for purchases on that date.
    """
    try:
        start_date = f"{selected_date} 00:00:00"
        end_date = f"{selected_date} 23:59:59"
        c.execute("SELECT t.id, p.name, t.quantity, t.price, p.unit, t.date FROM transactions t JOIN products p ON t.product_id = p.id WHERE t.quantity > 0 AND t.date BETWEEN ? AND ?",
                  (start_date, end_date))
        return c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving transactions for {selected_date}: {e}")
        raise

def delete_transaction(transaction_id: int) -> Tuple[bool, str]:
    """
    Delete a specific transaction and clean up related products if no transactions remain.
    Args:
        transaction_id (int): ID of the transaction to delete.
    Returns:
        tuple: (bool, str) - (success, message) indicating if deletion succeeded and why.
    """
    try:
        c.execute("SELECT product_id, quantity FROM transactions WHERE id = ?", (transaction_id,))
        trans = c.fetchone()
        if trans:
            product_id, quantity = trans
            current_qty = get_current_quantity(product_id)
            if current_qty - quantity < 0:
                return False, "Cannot delete: would result in negative stock."
            c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            conn.commit()
            logger.info(f"Deleted transaction {transaction_id} for product_id {product_id}")
            # Check if the product has any remaining transactions
            c.execute("SELECT COUNT(*) FROM transactions WHERE product_id = ?", (product_id,))
            if c.fetchone()[0] == 0:
                c.execute("DELETE FROM products WHERE id = ?", (product_id,))
                conn.commit()
                logger.info(f"Cleaned up product_id {product_id} with no remaining transactions")
            return True, "Transaction deleted successfully."
        return False, "Transaction not found."
    except sqlite3.Error as e:
        logger.error(f"Error deleting transaction {transaction_id}: {e}")
        raise

def get_daily_transactions(selected_date: date) -> List[Tuple[str, float, float, str]]:
    """
    Retrieve all transactions (purchases and sales) for a specific date.
    Returns:
        list: List of tuples (product_name, quantity, price, type) where type is 'purchase' or 'sale'.
    """
    start_date = f"{selected_date} 00:00:00"
    end_date = f"{selected_date} 23:59:59"
    try:
        c.execute("""
            SELECT p.name, t.quantity, t.price, 
                   CASE WHEN t.quantity > 0 THEN 'purchase' ELSE 'sale' END as type
            FROM transactions t 
            JOIN products p ON t.product_id = p.id 
            WHERE t.date BETWEEN ? AND ?
        """, (start_date, end_date))
        return c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving daily transactions for {selected_date}: {e}")
        raise

def calculate_daily_earnings(selected_date: date) -> float:
    """
    Calculate daily earnings (sales revenue - purchase costs) for a specific date.
    Returns:
        float: Net earnings in INR (negative for purchase costs, positive for sales revenue).
    """
    transactions = get_daily_transactions(selected_date)
    purchase_cost = sum(price * abs(quantity) for _, quantity, price, trans_type in transactions if trans_type == 'purchase' and price is not None)
    sale_revenue = sum(price * abs(quantity) for _, quantity, price, trans_type in transactions if trans_type == 'sale' and price is not None)
    return sale_revenue - purchase_cost

def estimate_daily_needs(selected_date: date) -> Dict[str, float]:
    """
    Estimate daily product needs based on recent sales and current inventory.
    Returns:
        dict: Mapping of product names to estimated quantities needed (in units).
    """
    transactions = get_daily_transactions(selected_date)
    needs = {}
    for product_name, quantity, _, trans_type in transactions:
        if trans_type == 'sale':
            needs[product_name] = needs.get(product_name, 0) + abs(quantity)
    # Adjust for current inventory to estimate needs
    for product_id, name, unit in get_all_products():
        current_qty = get_current_quantity(product_id)
        if name in needs and current_qty < needs[name]:
            needs[name] = max(0, needs[name] - current_qty)
        elif name not in needs and current_qty == 0:
            needs[name] = 0.0  # No immediate need if stock exists
    return needs

def prune_old_transactions(keep_years: int = 2) -> None:
    """
    Remove transactions older than a specified number of years to manage database size.
    Args:
        keep_years (int): Number of years to retain transactions (default: 2).
    """
    try:
        cutoff_date = datetime.now().replace(year=datetime.now().year - keep_years).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("DELETE FROM transactions WHERE date < ?", (cutoff_date,))
        conn.commit()
        logger.info(f"Pruned transactions older than {keep_years} years (cutoff: {cutoff_date})")
    except sqlite3.Error as e:
        logger.error(f"Error pruning old transactions: {e}")
        raise

def backup_database(backup_path: str = "backup_inventory.db") -> None:
    """
    Create a backup of the current database.
    Args:
        backup_path (str): Path where the backup file will be saved (default: "backup_inventory.db").
    """
    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Backed up database to {backup_path}")
    except OSError as e:
        logger.error(f"Error backing up database: {e}")
        raise

# Close the database connection when the script exits (optional, handled by Streamlit)
# conn.close()
