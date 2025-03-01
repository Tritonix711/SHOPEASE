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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Directory of this file
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
    # Products table: stores product details
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT NOT NULL, 
                  unit TEXT NOT NULL)''')

    # Transactions table: stores purchase/sale records
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  product_id INTEGER NOT NULL,
                  quantity REAL NOT NULL,
                  price REAL,
                  date TEXT NOT NULL,
                  FOREIGN KEY(product_id) REFERENCES products(id))''')

    # Daily Summaries table: stores daily cash flow summaries
    c.execute('''CREATE TABLE IF NOT EXISTS daily_summaries
                 (date TEXT PRIMARY KEY,
                  cash_in REAL NOT NULL,
                  cash_out REAL NOT NULL,
                  purchase_costs REAL NOT NULL,
                  profit_loss REAL NOT NULL)''')

    # Add indexes for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_transactions_product_date ON transactions(product_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daily_summaries_date ON daily_summaries(date)")
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
        c.execute("INSERT INTO products (name, unit) VALUES (?, ?)", (name.strip(), unit.strip()))
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
        price (float, optional): Total purchase cost for purchases (None for sales).
    """
    try:
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO transactions (product_id, quantity, price, date) VALUES (?, ?, ?, ?)",
                  (product_id, quantity, price, date))
        conn.commit()
        logger.info(f"Added transaction for product_id {product_id}: {quantity} at total cost {price} INR on {date}")
    except sqlite3.Error as e:
        logger.error(f"Error adding transaction for product_id {product_id}: {e}")
        raise

def get_current_quantity(product_id: int) -> float:
    """
    Calculate the current quantity of a product by summing all transactions.
    Args:
        product_id (int): ID of the product.
    Returns:
        float: Current quantity (purchases minus sales), or 0 if no transactions.
    """
    try:
        c.execute("SELECT SUM(quantity) FROM transactions WHERE product_id = ?", (product_id,))
        result = c.fetchone()[0]
        return result if result is not None else 0.0
    except sqlite3.Error as e:
        logger.error(f"Error getting current quantity for product_id {product_id}: {e}")
        raise

def get_last_price_before_date(product_id: int, target_date: Optional[str] = None) -> Optional[float]:
    """
    Get the last total purchase cost of a product on or before a specific date.
    Args:
        product_id (int): ID of the product.
        target_date (str, optional): Date in "YYYY-MM-DD HH:MM:SS" format, defaults to now.
    Returns:
        float: Last total cost, or None if no purchase exists.
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
        list: List of tuples (date, quantity, price) for all purchases, sorted by date, where price is total cost.
    """
    try:
        query = "SELECT date, quantity, price FROM transactions WHERE product_id = ? AND quantity > 0"
        params = [product_id]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date.strftime("%Y-%m-%d 00:00:00"))
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.strftime("%Y-%m-%d 23:59:59"))
        
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
        c.execute("SELECT id FROM products WHERE name = ?", (name.strip(),))
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
        list: List of tuples (transaction_id, product_name, quantity, price, unit, date) for purchases on that date, where price is total cost.
    """
    try:
        start_date = selected_date.strftime("%Y-%m-%d 00:00:00")
        end_date = selected_date.strftime("%Y-%m-%d 23:59:59")
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
        tuple: (bool, str) - (success, message) indicating if deletion succeeded or why it failed.
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
        list: List of tuples (product_name, quantity, price, type) where type is 'purchase' or 'sale', and price is total cost for purchases.
    """
    try:
        start_date = selected_date.strftime("%Y-%m-%d 00:00:00")
        end_date = selected_date.strftime("%Y-%m-%d 23:59:59")
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
        float: Net earnings in INR (negative for net purchase costs, positive for net sales revenue).
    """
    try:
        transactions = get_daily_transactions(selected_date)
        # For purchases, price is the total cost, no multiplication by quantity
        purchase_cost = sum(price for _, quantity, price, trans_type in transactions if trans_type == 'purchase' and price is not None)
        # For sales, price is assumed per-unit (adjust if total cost is needed later)
        sale_revenue = sum(price * abs(quantity) for _, quantity, price, trans_type in transactions if trans_type == 'sale' and price is not None)
        net_earnings = sale_revenue - purchase_cost
        logger.info(f"Calculated daily earnings for {selected_date}: Sales Revenue={sale_revenue}, Purchase Cost={purchase_cost}, Net={net_earnings}")
        return net_earnings
    except Exception as e:
        logger.error(f"Error calculating daily earnings for {selected_date}: {e}")
        raise

def estimate_daily_needs(selected_date: date) -> Dict[str, float]:
    """
    Estimate daily product needs based on recent sales and current inventory.
    Returns:
        dict: Mapping of product names to estimated quantities needed (in units).
    """
    try:
        transactions = get_daily_transactions(selected_date)
        needs = {}
        for product_name, quantity, _, trans_type in transactions:
            if trans_type == 'sale':
                needs[product_name] = needs.get(product_name, 0) + abs(quantity)
        for product_id, name, unit in get_all_products():
            current_qty = get_current_quantity(product_id)
            if name in needs and current_qty < needs[name]:
                needs[name] = max(0, needs[name] - current_qty)
            elif name not in needs and current_qty == 0:
                needs[name] = 0.0  # No immediate need if stock exists
        return needs
    except Exception as e:
        logger.error(f"Error estimating daily needs for {selected_date}: {e}")
        raise

def save_daily_summary(selected_date: date, cash_in: float, cash_out: float, purchase_costs: float, profit_loss: float) -> None:
    """
    Save the daily cash flow summary for a specific date.
    Args:
        selected_date (date): Date of the summary.
        cash_in (float): Total cash received.
        cash_out (float): Total cash spent (manual).
        purchase_costs (float): Cost of purchases for the day.
        profit_loss (float): Calculated profit or loss.
    """
    try:
        date_str = selected_date.isoformat()
        cash_in = float(cash_in) if cash_in is not None else 0.0
        cash_out = float(cash_out) if cash_out is not None else 0.0
        purchase_costs = float(purchase_costs) if purchase_costs is not None else 0.0
        profit_loss = float(profit_loss) if profit_loss is not None else 0.0

        c.execute("""
            INSERT OR REPLACE INTO daily_summaries (date, cash_in, cash_out, purchase_costs, profit_loss)
            VALUES (?, ?, ?, ?, ?)
        """, (date_str, cash_in, cash_out, purchase_costs, profit_loss))
        conn.commit()
        logger.info(f"Saved daily summary for {date_str}: Cash In={cash_in}, Cash Out={cash_out}, Purchase Costs={purchase_costs}, Profit/Loss={profit_loss}")
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error saving daily summary for {selected_date}: {e}")
        raise

def get_daily_summary(selected_date: date) -> Optional[Tuple[float, float, float, float]]:
    """
    Retrieve the daily cash flow summary for a specific date.
    Args:
        selected_date (date): Date to retrieve the summary for.
    Returns:
        tuple: (cash_in, cash_out, purchase_costs, profit_loss) or None if no summary exists.
    """
    try:
        date_str = selected_date.isoformat()
        logger.info(f"Querying daily summary for date: {date_str}")
        c.execute("SELECT cash_in, cash_out, purchase_costs, profit_loss FROM daily_summaries WHERE date = ?", (date_str,))
        result = c.fetchone()
        if result:
            return (float(result[0]), float(result[1]), float(result[2]), float(result[3]))
        return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving daily summary for {selected_date}: {e}")
        raise

def delete_daily_summary(selected_date: date) -> Tuple[bool, str]:
    """
    Delete a daily summary and all associated purchase transactions for a specific date.
    Args:
        selected_date (date): Date of the summary to delete.
    Returns:
        tuple: (bool, str) - (success, message) indicating if deletion succeeded or why it failed.
    """
    try:
        date_str = selected_date.isoformat()
        start_date = selected_date.strftime("%Y-%m-%d 00:00:00")
        end_date = selected_date.strftime("%Y-%m-%d 23:59:59")

        # Check if a summary exists
        c.execute("SELECT date FROM daily_summaries WHERE date = ?", (date_str,))
        summary_exists = c.fetchone() is not None

        # Delete purchase transactions for the date (quantity > 0)
        c.execute("DELETE FROM transactions WHERE date BETWEEN ? AND ? AND quantity > 0", (start_date, end_date))
        trans_deleted = c.rowcount

        # Delete the summary
        c.execute("DELETE FROM daily_summaries WHERE date = ?", (date_str,))
        summary_deleted = c.rowcount

        conn.commit()

        if summary_exists or trans_deleted > 0:
            message = f"Daily summary and {trans_deleted} transaction(s) for {date_str} deleted successfully."
            logger.info(message)
            return True, message
        else:
            message = f"No daily summary or transactions found for {date_str}."
            logger.info(message)
            return False, message
    except sqlite3.Error as e:
        logger.error(f"Error deleting daily summary and transactions for {selected_date}: {e}")
        raise

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

# Note: Connection is left open for Streamlit; close manually if needed in other contexts
# conn.close()
